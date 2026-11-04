"""Explicit data and deployment policies. Workbench defaults fail closed."""
import os
import sys
from pathlib import Path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common.config import get_config


def data_mode():
    mode = os.getenv('NPI_DATA_MODE') or get_config().get('runtime', {}).get('data_mode', 'demo')
    if mode not in {'demo', 'pilot'}:
        raise RuntimeError('NPI_DATA_MODE must be demo or pilot')
    return mode


def on_workbench():
    return any(os.getenv(k) for k in ('CDSW_DOMAIN', 'CDSW_PROJECT_ID', 'CDSW_APP_ID')) or Path.home() == Path('/home/cdsw') or os.getenv('TASK_TYPE') == 'START_APPLICATION'


def auth_mode():
    mode = os.getenv('NPI_AUTH_MODE') or ('workbench' if on_workbench() or data_mode() == 'pilot' else 'local_demo')
    if mode not in {'workbench', 'local_demo'}:
        raise RuntimeError('NPI_AUTH_MODE must be workbench or local_demo')
    if mode == 'local_demo' and (on_workbench() or data_mode() != 'demo'):
        raise RuntimeError('local_demo authorization is permitted only for local Demo mode')
    return mode


def require_demo(operation):
    if data_mode() != 'demo':
        raise RuntimeError(operation + ' is disabled in Pilot mode')


if __name__ == '__main__':
    assert data_mode() in {'demo', 'pilot'}
    assert auth_mode() in {'local_demo', 'workbench'}
    print('Runtime policy OK')
