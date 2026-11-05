"""Keep successful readiness probes out of Uvicorn access logs."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import copy
import logging
from uvicorn.config import LOGGING_CONFIG


class HealthCheckFilter(logging.Filter):
    def filter(self, record):
        # Uvicorn access args: client, method, path, HTTP version, status.
        if not isinstance(record.args, tuple) or len(record.args) != 5:
            return True
        _, method, path, _, status = record.args
        try:
            status = int(status)
        except (TypeError, ValueError):
            return True
        return not (method in {'GET', 'HEAD'} and isinstance(path, str)
                    and path.partition('?')[0] in {'/', '/api/health'}
                    and 200 <= status < 300)


def server_log_config():
    config = copy.deepcopy(LOGGING_CONFIG)
    config.setdefault('filters', {})['health_checks'] = {'()': 'common.access_logging.HealthCheckFilter'}
    config['handlers']['access'].setdefault('filters', []).append('health_checks')
    return config


if __name__ == '__main__':
    record = logging.LogRecord('uvicorn.access', logging.INFO, '', 0, '%s %s %s %s %s',
                               ('127.0.0.1', 'GET', '/api/health', '1.1', 200), None)
    assert not HealthCheckFilter().filter(record)
    assert 'health_checks' in server_log_config()['handlers']['access']['filters']
