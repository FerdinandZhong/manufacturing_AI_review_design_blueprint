"""Probe filtering must preserve failed probes and API diagnostics."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import io
import logging
import pytest
from common.access_logging import HealthCheckFilter, server_log_config
from uvicorn.config import LOGGING_CONFIG


@pytest.mark.parametrize('method,path,status,visible',[
    ('GET','/',200,False),('HEAD','/',204,False),
    ('GET','/?probe=ready',200,False),('GET','/api/health',200,False),
    ('HEAD','/api/health',200,False),('GET','/api/health',500,True),
    ('GET','/',403,True),('GET','/',404,True),('GET','/',301,True),
    ('GET','/api/runtime/status',403,True),('GET','/api/programs',200,True),
    ('GET','/api/health-details',200,True),('POST','/',200,True),
])
def test_probe_access_record_filter(method,path,status,visible):
    stream=io.StringIO()
    handler=logging.StreamHandler(stream)
    handler.addFilter(HealthCheckFilter())
    logger=logging.Logger('uvicorn.access',logging.INFO)
    logger.addHandler(handler)
    logger.info('%s - "%s %s HTTP/%s" %s', '127.0.0.1:1234',method,path,'1.1',status)
    assert bool(stream.getvalue()) is visible


def test_non_access_errors_survive_and_configs_are_independent():
    record=logging.LogRecord('uvicorn.error',logging.ERROR,'',0,'startup failed',(),None)
    assert HealthCheckFilter().filter(record)
    first=server_log_config()
    second=server_log_config()
    assert first['handlers']['access']['filters']==['health_checks']
    first['handlers']['access']['filters'].append('changed')
    assert second['handlers']['access']['filters']==['health_checks']
    assert 'filters' not in LOGGING_CONFIG['handlers']['access']
    assert 'filters' not in first['handlers']['default']


if __name__=='__main__':
    assert callable(test_non_access_errors_survive_and_configs_are_independent)
