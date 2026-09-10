"""Workbench build Job: install, seed, prepare, then smoke-test local app routes."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '02_backend'))

import subprocess

STEPS = ('01_installer/install.py',
         '02_backend/data_generation/generate_synthetic_data.py',
         '02_backend/scripts/prepare.py',
         'cai_integration/smoke_test.py')


def main():
    for script in STEPS:
        print('Preparation step: ' + script, flush=True)
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)
    # Build/test the separately installable stdio adapter without turning it
    # into a long-running Application dependency.
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', str(ROOT / 'mcp_server')], cwd=ROOT, check=True)
    subprocess.run([sys.executable, '-m', 'pytest', 'mcp_server/tests', '-q'], cwd=ROOT, check=True)
    print('Preparation complete: frontend, source, SQLite, ML, Lance and API smoke checks passed.')


if __name__ == '__main__':
    assert len(STEPS) == 4 and all((ROOT / script).is_file() for script in STEPS)
    main()
