"""Real stdio tool calls against a temporary HTTP API and temporary ops DB."""
import asyncio
import json
import os
from pathlib import Path
import socket
import sys
import threading
import time

import uvicorn
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / '02_backend'))


def test_sandbox_queries(tmp_path, monkeypatch):
    from common import db
    from engineering.test_bench import run_test_bench
    from api.main import app
    monkeypatch.setattr(db, 'get_db_path', lambda: str(tmp_path / 'ops.db'))
    db.init_db()
    run_test_bench('PACK-ATLAS-01')
    sock = socket.socket()
    sock.bind(('127.0.0.1', 0))
    port = sock.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(app, log_level='error'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
    thread.start()
    try:
        for _ in range(100):
            if server.started:
                break
            time.sleep(.05)
        assert server.started

        async def check():
            env = {**os.environ, 'PYTHONPATH': str(ROOT / 'mcp_server'),
                   'NPI_API_BASE_URL': f'http://127.0.0.1:{port}/api'}
            params = StdioServerParameters(command=sys.executable,
                args=['-c', 'from npi_mcp.server import main; main()'], env=env)
            async with stdio_client(params) as streams:
                async with ClientSession(*streams) as session:
                    await session.initialize()
                    for tool in ['query_requirements', 'query_design', 'query_bom', 'query_test_results']:
                        result = await session.call_tool(tool, {'program_id': 'PACK-ATLAS-01',
                            'requirement_id': 'REQ-ATLAS-thermal'})
                        assert not result.isError, result
                        # Older MCP v1 SDKs serialize dict results as JSON text.
                        data = result.structuredContent or json.loads(result.content[0].text)
                        assert data['total'] == 1, data
                        assert data['items'][0]['req_id'] == 'REQ-ATLAS-thermal'
                        if tool == 'query_test_results':
                            assert data['items'][0]['verdict'] == 'MARGINAL'
                            assert 'synthetic' in data['provenance']
                    search = await session.call_tool('search_knowledge', {'query': 'thermal'})
                    assert not search.isError and 'AST-' in str(search)
                    for asset, content_type in [('AST-ATLAS-thermal-report', 'text'),
                                                ('AST-ATLAS-pack-photo', 'image')]:
                        content = await session.call_tool('read_knowledge_content', {'asset_id': asset})
                        assert not content.isError, content
                        assert any(c.type == content_type for c in content.content)
        asyncio.run(check())
        with db.get_connection() as conn:
            assert conn.execute('SELECT COUNT(*) FROM gate_reviews').fetchone()[0] == 0
            assert conn.execute('SELECT COUNT(*) FROM evidence').fetchone()[0] == 0
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        sock.close()
    assert not thread.is_alive()


if __name__ == '__main__':
    assert ROOT.is_dir()
