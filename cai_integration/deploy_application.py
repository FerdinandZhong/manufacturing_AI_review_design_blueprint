"""Create/restart only the named NPI Application, private behind Workbench SSO."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '02_backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import json
import re
from client import Client, load_environment, write_result

NAME = 'Vehicle NPI Platform'
SCRIPT = '03_frontend/start_frontend.py'
FAILED = {'failed', 'error', 'engine_failed', 'startup_failed', 'killed'}


def build_payload(runtime, subdomain='vehicle-npi-platform'):
    if not runtime:
        raise ValueError('RUNTIME_IDENTIFIER is required; select a Python 3.11 Standard runtime')
    if not re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', subdomain):
        raise ValueError('APP_SUBDOMAIN must be a valid DNS label')
    return {'name': NAME, 'description': 'Vehicle NPI gate-review prototype',
            'script': SCRIPT, 'subdomain': subdomain, 'runtime_identifier': runtime,
            'cpu': 2, 'memory': 8, 'bypass_authentication': False,
            'environment': {'BACKEND_PORT': '7078', 'NPI_APP_MODE': 'prod',
                            'LLM_PROVIDER': os.getenv('LLM_PROVIDER', 'caii')}}


def deploy(client, project_id, payload, timeout=600):
    base = f'projects/{project_id}/applications'
    matches = [a for a in client.list(base, 'applications')
               if a.get('name') == payload['name'] or a.get('subdomain') == payload['subdomain']]
    if len(matches) > 1:
        raise RuntimeError('Multiple matching Applications; resolve the duplicate names/subdomains before deploying')
    if matches:
        app = client.request('GET', base + '/' + matches[0]['id'])
        # Refuse ambiguous config changes; restarting must not silently retain wrong settings.
        for key in ('name', 'script', 'subdomain', 'runtime_identifier', 'cpu', 'memory', 'bypass_authentication', 'environment'):
            if app.get(key) != payload[key]:
                raise RuntimeError(f'Existing Application differs in {key}; update its Workbench Settings to match the dry-run payload before restart')
        # API v2 action routes use a colon suffix, rather than a child path.
        client.request('POST', base + '/' + app['id'] + ':restart', {})
    else:
        app = client.request('POST', base, payload)
    if not app.get('id'):
        raise RuntimeError('Application response is missing its ID')
    ready = client.wait(base + '/' + app['id'], {'running'}, FAILED, timeout)
    return {'project_id': project_id, 'application_id': app['id'],
            'url': ready.get('url') or ready.get('application_url'),
            'status': 'running', 'health_verified': False,
            'note': 'Platform Running confirmed. Open the authenticated URL to verify UI and gate review.'}


def main():
    load_environment()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-id', default=os.getenv('CML_PROJECT_ID') or os.getenv('CDSW_PROJECT_ID'))
    p.add_argument('--runtime-identifier', default=os.getenv('RUNTIME_IDENTIFIER'))
    p.add_argument('--subdomain', default=os.getenv('APP_SUBDOMAIN', 'vehicle-npi-platform'))
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--output', default='.cai/deployment.json')
    args = p.parse_args()
    payload = build_payload(args.runtime_identifier, args.subdomain)
    if args.dry_run:
        print(json.dumps(payload, indent=2)); return
    if not args.project_id:
        p.error('--project-id or CML_PROJECT_ID is required')
    client = Client()
    try:
        result = deploy(client, args.project_id, payload)
        write_result(args.output, result)
        print(json.dumps(result, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    assert build_payload('test-runtime')['bypass_authentication'] is False
    main()
