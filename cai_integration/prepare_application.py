"""Workbench build Job: install, seed, prepare, then smoke-test local app routes."""
import os
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / '02_backend'))

import subprocess

STEPS = ('01_installer/install.py',
         '02_backend/scripts/prepare.py',
         'cai_integration/smoke_test.py')


def main():
    from common.runtime import data_mode
    for script in STEPS:
        if script=='02_backend/scripts/prepare.py' and data_mode()=='demo':
            from data_generation.generate_synthetic_data import generate
            from common.config import get_config
            generate(str(ROOT/get_config().get('source',{}).get('csv_dir','data/raw')))
        print('Preparation step: ' + script, flush=True)
        subprocess.run([sys.executable, str(ROOT / script)], cwd=ROOT, check=True)
    # Install the thin adapter. Its test suite is an explicit release check,
    # never part of operational Pilot preparation.
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade', str(ROOT / 'mcp_server')], cwd=ROOT, check=True)
    print('Preparation complete for '+data_mode()+' profile. MCP release verification is a separate command.')


if __name__ == '__main__':
    assert len(STEPS) == 3 and all((ROOT / script).is_file() for script in STEPS)
    main()
