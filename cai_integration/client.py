"""Small API v2 client. Credentials come from environment, never CLI arguments."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "02_backend"))

import json
import time
from urllib.parse import urlsplit
import httpx


def normalize_host(value):
    value = value.rstrip('/')
    for suffix in ('/api/v1', '/api/v2'):
        if value.endswith(suffix):
            value = value[:-len(suffix)]
    parsed = urlsplit(value)
    if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.path:
        raise ValueError('CML_HOST must be an HTTPS workspace origin (optional /api/v2 suffix)')
    return value


def load_environment():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env', override=False)


class Client:
    def __init__(self, host=None, key=None, transport=None):
        self.host = normalize_host(host or os.getenv('CML_HOST') or os.getenv('CDSW_API_URL') or '')
        key = key or os.getenv('CML_API_KEY') or os.getenv('CDSW_APIV2_KEY')
        if not key:
            raise ValueError('Set CML_API_KEY or CDSW_APIV2_KEY')
        self.http = httpx.Client(base_url=self.host + '/api/v2/',
                                 headers={'Authorization': 'Bearer ' + key.strip()},
                                 timeout=60, follow_redirects=False, transport=transport)

    def request(self, method, path, payload=None, params=None):
        try:
            response = self.http.request(method, path, json=payload, params=params)
        except httpx.HTTPError:
            raise RuntimeError(f'Workbench connection failed during {method} {path}') from None
        if not 200 <= response.status_code < 300:
            # Bodies can contain credential-bearing request fields. Keep diagnostics safe.
            raise RuntimeError(f'Workbench returned HTTP {response.status_code} for {method} {path}')
        return response.json() if response.content else {}

    def list(self, path, key):
        rows, token = [], None
        seen = set()
        while True:
            params = {'page_size': 100}
            if token:
                params['page_token'] = token
            page = self.request('GET', path, params=params)
            rows.extend(page.get(key, []))
            token = page.get('next_page_token')
            if not token:
                return rows
            if token in seen:
                raise RuntimeError('Workbench returned a repeated pagination token')
            seen.add(token)

    def wait(self, path, success, failure, timeout=600, field='status'):
        deadline = time.monotonic() + timeout
        previous = None
        while time.monotonic() < deadline:
            row = self.request('GET', path)
            status = str(row.get(field, '')).lower()
            if status != previous:
                print(f'{path}: {status or "unknown"}', flush=True)
                previous = status
            if status in success:
                return row
            if status in failure:
                raise RuntimeError(f'{path} ended in {status}; inspect the Workbench workload logs')
            time.sleep(min(5, max(0, deadline - time.monotonic())))
        raise TimeoutError(f'Timed out waiting for {path}; workload may still be running')

    def close(self):
        self.http.close()


def write_result(path, result):
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(result, indent=2) + '\n')


if __name__ == '__main__':
    assert normalize_host('https://example.com/api/v2/') == 'https://example.com'
    print('client self-check OK')
