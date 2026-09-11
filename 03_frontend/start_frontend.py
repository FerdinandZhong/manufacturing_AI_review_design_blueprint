"""One Workbench application: static React + streaming proxy + loopback API."""
import os
import sys
import time
import atexit
import subprocess
from pathlib import Path

PROJECT_ROOT = str(Path(__file__).resolve().parents[1]) if '__file__' in globals() else os.getcwd()
FRONTEND_DIR = os.path.join(PROJECT_ROOT, '03_frontend')
DIST_DIR = os.path.join(FRONTEND_DIR, 'dist')
sys.path.insert(0, os.path.join(PROJECT_ROOT, '02_backend'))
_backend_proc = None


def _env_int(*names, default):
    for name in names:
        raw = os.environ.get(name)
        if raw and raw.strip():
            port = int(raw)
            if not 1 <= port <= 65535:
                raise ValueError(f'{name} must be a valid TCP port')
            return port
    return default


def _bind_host():
    # Workbench's application proxy reaches the engine loopback listener.
    return '127.0.0.1' if os.getenv('CDSW_APP_PORT') or Path.home() == Path('/home/cdsw') else '0.0.0.0'


def _stop_backend():
    global _backend_proc
    if _backend_proc and _backend_proc.poll() is None:
        _backend_proc.terminate()
        try:
            _backend_proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            _backend_proc.kill()
            _backend_proc.wait(timeout=5)
    _backend_proc = None


def _wait_for_backend(port, timeout=30):
    import urllib.request
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if _backend_proc is not None and _backend_proc.poll() is not None:
            raise RuntimeError('Backend exited during startup; inspect the application logs')
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/api/health', timeout=2) as response:
                if response.status == 200:
                    return
        except OSError:
            pass
        time.sleep(0.5)
    raise RuntimeError('Backend readiness timed out')


def _start_backend(port):
    global _backend_proc
    import socket
    # Fail instead of accidentally connecting to another app's backend.
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', port))
    env = os.environ.copy()
    env['BACKEND_PORT'] = str(port)
    env.pop('CDSW_APP_PORT', None)
    _backend_proc = subprocess.Popen([sys.executable, os.path.join(PROJECT_ROOT, '02_backend/start_backend.py')],
                                     env=env, cwd=PROJECT_ROOT)
    try:
        _wait_for_backend(port)
    except Exception:
        _stop_backend()
        raise


def check_artifacts():
    from common.config import get_config, get_db_path
    cfg = get_config()
    def rooted(path):
        return Path(path) if os.path.isabs(path) else Path(PROJECT_ROOT) / path
    required = [Path(DIST_DIR) / 'index.html', Path(get_db_path()),
                rooted(cfg.get('ml', {}).get('model_dir', 'models')) / 'risk_model.pkl',
                rooted(cfg.get('ml', {}).get('model_dir', 'models')) / 'risk_meta.json',
                rooted(cfg.get('data', {}).get('kb_dir', 'data/kb')) / 'assets.lance']
    raw = rooted(cfg.get('source', {}).get('csv_dir', 'data/raw'))
    required += [raw / (name + '.csv') for name in ('programs', 'requirements', 'design_specs', 'bom_items', 'suppliers', 'test_plans')]
    missing = [str(p) for p in required if not p.exists()]
    if missing:
        raise RuntimeError('Missing prepared artifacts: ' + ', '.join(missing) + '. Run cai_integration/prepare_application.py first.')


def create_app(backend_port):
    import asyncio
    from contextlib import asynccontextmanager
    import httpx
    from fastapi import FastAPI, Request
    from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    @asynccontextmanager
    async def lifespan(app):
        _start_backend(backend_port)
        try:
            async with httpx.AsyncClient(base_url=f'http://127.0.0.1:{backend_port}',
                                         timeout=httpx.Timeout(10, read=None), follow_redirects=False) as client:
                app.state.backend = client
                yield
        finally:
            _stop_backend()

    app = FastAPI(title='Vehicle NPI Platform', lifespan=lifespan, docs_url=None, openapi_url=None)
    hop = {'host', 'content-length', 'transfer-encoding', 'connection', 'keep-alive', 'upgrade', 'content-encoding'}

    @app.api_route('/api/{path:path}', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'OPTIONS'])
    async def proxy_api(path: str, request: Request):
        if _backend_proc is None or _backend_proc.poll() is not None:
            return JSONResponse({'detail': 'Backend unavailable'}, status_code=503)
        headers = {k: v for k, v in request.headers.items() if k.lower() not in hop}
        url = '/api/' + path + ('?' + request.url.query if request.url.query else '')
        client = app.state.backend
        req = client.build_request(request.method, url, content=await request.body(), headers=headers)
        try:
            response = await client.send(req, stream=True)
        except httpx.HTTPError:
            return JSONResponse({'detail': 'Backend connection failed'}, status_code=502)
        response_headers = {k: v for k, v in response.headers.items() if k.lower() not in hop}
        if 'text/event-stream' in response.headers.get('content-type', ''):
            response_headers.update({'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'})
        async def stream():
            try:
                async for chunk in response.aiter_raw():
                    yield chunk
            finally:
                await response.aclose()
        return StreamingResponse(stream(), status_code=response.status_code, headers=response_headers)

    assets = os.path.join(DIST_DIR, 'assets')
    if os.path.isdir(assets):
        app.mount('/assets', StaticFiles(directory=assets), name='assets')
    root = Path(DIST_DIR).resolve()

    @app.get('/{full_path:path}')
    async def serve_react(full_path: str):
        target = (root / full_path).resolve()
        if target.is_relative_to(root) and target.is_file():
            return FileResponse(target, headers={'Cache-Control': 'no-cache, must-revalidate'})
        return FileResponse(root / 'index.html', headers={'Cache-Control': 'no-cache, must-revalidate'})
    return app


def _run_uvicorn(app, host, port):
    """Run Uvicorn from a process or from a notebook with an active event loop.

    ``uvicorn.run`` owns the asyncio loop and therefore raises when called from
    a Jupyter/CML notebook cell whose loop is already running. In that case the
    server gets its own loop in a dedicated thread; normal CLI launches retain
    Uvicorn's standard foreground behavior.
    """
    import asyncio
    import threading
    import uvicorn

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        uvicorn.run(app, host=host, port=port)
        return

    config = uvicorn.Config(app, host=host, port=port)
    server = uvicorn.Server(config)
    failures = []

    def serve():
        try:
            server.run()
        except BaseException as exc:  # propagate startup failures to the caller
            failures.append(exc)

    thread = threading.Thread(target=serve, name='npi-uvicorn', daemon=False)
    thread.start()
    try:
        thread.join()
    except KeyboardInterrupt:
        server.should_exit = True
        thread.join(timeout=10)
        if thread.is_alive():
            server.force_exit = True
            thread.join()
    if failures:
        raise failures[0]


def main():
    mode = os.getenv('NPI_APP_MODE') or (sys.argv[1] if len(sys.argv) > 1 else 'prod')
    port = _env_int('CDSW_APP_PORT', 'FRONTEND_PORT', default=8100)
    backend = _env_int('BACKEND_PORT', default=7078)
    if port == backend:
        raise ValueError('Application and backend ports must differ')
    if mode == 'dev':
        _start_backend(backend)
        try:
            subprocess.run(['npx', 'vite', '--port', str(port), '--host', _bind_host()], cwd=FRONTEND_DIR, check=True)
        finally:
            _stop_backend()
    else:
        check_artifacts()
        _run_uvicorn(create_app(backend), host=_bind_host(), port=port)


if __name__ == '__main__':
    assert os.path.isabs(PROJECT_ROOT)
    atexit.register(_stop_backend)
    main()
