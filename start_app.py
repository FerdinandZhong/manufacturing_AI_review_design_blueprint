"""Local-dev launcher for the Vehicle NPI Blueprint.

Delegates to 03_frontend/start_frontend.py, which co-locates its own FastAPI
backend child process (AML's single-CML-app pattern — see that file's
docstring). This script does NOT spawn a second backend: 03_frontend/
start_frontend.py already starts one bound to BACKEND_PORT, so spawning
02_backend/start_backend.py here too would double-bind that port and one of
the two would fail with "address already in use" (confirmed while wiring up
Task 12 packaging). On CAI Workbench, the AMP's start_application task points
directly at 03_frontend/start_frontend.py for the same reason.
"""

import os
import sys
import subprocess
import signal
import time

try:
    PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
except NameError:
    PROJECT_ROOT = os.getcwd()

BACKEND_PORT = int(os.environ.get("BACKEND_PORT", 7078))
FRONTEND_PORT = int(os.environ.get("CDSW_APP_PORT", os.environ.get("FRONTEND_PORT", 8100)))

processes = []


def cleanup(signum=None, frame=None):
    print("\nShutting down...")
    for proc in processes:
        if proc.poll() is None:
            proc.terminate()
    for proc in processes:
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    sys.exit(0)


signal.signal(signal.SIGINT, cleanup)
signal.signal(signal.SIGTERM, cleanup)


def main():
    # Check prerequisites — warn but don't block
    db_path = os.path.join(PROJECT_ROOT, "data", "npi.db")
    model_path = os.path.join(PROJECT_ROOT, "models", "risk_model.pkl")

    if not os.path.exists(db_path) or not os.path.exists(model_path):
        print("WARNING: Database or trained model not found.")
        print("  Build them first by running:")
        print("    python3 02_backend/scripts/prepare.py")
        print()

    env = os.environ.copy()
    env["BACKEND_PORT"] = str(BACKEND_PORT)
    env["CDSW_APP_PORT"] = str(FRONTEND_PORT)

    # Single process: 03_frontend/start_frontend.py starts its own co-located
    # backend (see module docstring above) and serves the frontend. Do not
    # also spawn 02_backend/start_backend.py here — that would double-bind
    # BACKEND_PORT.
    dist_dir = os.path.join(PROJECT_ROOT, "03_frontend", "dist")
    mode = "prod" if os.path.isdir(dist_dir) else "dev"
    print(f"Starting app ({mode}) — backend on :{BACKEND_PORT}, frontend on :{FRONTEND_PORT}...")

    frontend = subprocess.Popen(
        [sys.executable, os.path.join(PROJECT_ROOT, "03_frontend", "start_frontend.py"), mode],
        env=env,
        cwd=PROJECT_ROOT,
    )
    processes.append(frontend)

    print()
    print("=" * 55)
    print(f"  App:   http://localhost:{FRONTEND_PORT}")
    print("=" * 55)
    print("Press Ctrl+C to stop.")
    print()

    # Wait for either process to exit
    while True:
        for proc in processes:
            ret = proc.poll()
            if ret is not None:
                print(f"Process exited with code {ret}")
                cleanup()
        time.sleep(1)


if __name__ == "__main__":
    main()
