"""Keep every backend test's operational artifacts outside the demo workspace."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import copy
import pytest
from common.config import get_config
from knowledge import kb

@pytest.fixture(scope='session', autouse=True)
def isolated_operational_artifacts(tmp_path_factory):
    scratch = tmp_path_factory.mktemp('npi-test-artifacts')
    cfg = get_config()
    original = copy.deepcopy(cfg)
    original_embedder = kb._try_load_st
    cfg.setdefault('data', {})['db_path'] = str(scratch/'ops.db')
    cfg['data']['kb_dir'] = str(scratch/'kb')
    cfg.setdefault('pilot', {})['ops_db_path'] = str(scratch/'pilot.db')
    cfg.setdefault('ml', {})['model_dir'] = str(scratch/'models')
    kb._try_load_st = lambda: None
    try:
        yield
    finally:
        cfg.clear()
        cfg.update(original)
        kb._try_load_st = original_embedder

if __name__ == '__main__':
    assert callable(isolated_operational_artifacts)
    print('Backend test artifacts are isolated')
