"""Project → one build Job → private CAI Application. No credentials in job env."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '02_backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import json
from client import Client, load_environment, write_result
from setup_project import setup, PROJECT_NAME, project_payload
from deploy_application import build_payload, deploy

JOB_NAME = 'Prepare Vehicle NPI Application'


def job_payload(runtime):
    if not runtime:
        raise ValueError('RUNTIME_IDENTIFIER is required')
    return {'name': JOB_NAME, 'script': 'cai_integration/prepare_application.py',
            'runtime_identifier': runtime, 'cpu': 2, 'memory': 8, 'timeout': 3600}


def prepare(client, pid, payload):
    base = f'projects/{pid}/jobs'
    matches = [r for r in client.list(base, 'jobs') if r.get('name') == JOB_NAME]
    if len(matches) > 1:
        raise RuntimeError('Duplicate preparation jobs; resolve them in Workbench')
    if matches:
        job = client.request('GET', base + '/' + matches[0]['id'])
        if any(job.get(k) != v for k, v in payload.items()):
            raise RuntimeError('Preparation Job settings differ; update them to match the dry-run payload')
    else:
        job = client.request('POST', base, payload)
    job_id = job['id']
    runs_path = base + '/' + job_id + '/runs'
    runs = client.list(runs_path, 'runs')
    terminal = {'succeeded', 'success', 'engine_succeeded', 'failed', 'error', 'engine_failed', 'stopped', 'killed', 'cancelled', 'timedout', 'timed_out'}
    if any(str(r.get('status', '')).lower() not in terminal for r in runs):
        raise RuntimeError('A preparation run is active or has unknown status; wait before rebuilding shared storage')
    run = client.request('POST', runs_path, {})
    run_id = run['id']
    client.wait(runs_path + '/' + run_id, {'succeeded', 'success', 'engine_succeeded'},
                terminal - {'succeeded', 'success', 'engine_succeeded'}, 3700)
    return {'job_id': job_id, 'run_id': run_id}


def main():
    load_environment()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-id', default=os.getenv('CML_PROJECT_ID') or os.getenv('CDSW_PROJECT_ID'))
    p.add_argument('--git-url', default=os.getenv('GIT_URL'))
    p.add_argument('--runtime-identifier', default=os.getenv('RUNTIME_IDENTIFIER'))
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--output', default='.cai/deployment.json')
    a = p.parse_args()
    app_payload = build_payload(a.runtime_identifier, os.getenv('APP_SUBDOMAIN', 'vehicle-npi-platform'))
    build = job_payload(a.runtime_identifier)
    name = os.getenv('PROJECT_NAME', PROJECT_NAME)
    if a.dry_run:
        print(json.dumps({'project': {'id': a.project_id} if a.project_id else project_payload(name, a.git_url),
                          'preparation_job': build, 'application': app_payload}, indent=2)); return
    client = Client()
    try:
        pid = setup(client, name, a.git_url, a.project_id)
        # Builds rewrite shared artifacts. A running app must be stopped first.
        active = [r for r in client.list(f'projects/{pid}/applications', 'applications')
                  if str(r.get('status', '')).lower() not in {'stopped', 'failed', 'error', 'engine_failed', 'killed'}]
        if active:
            raise RuntimeError('Project has a running/starting Application; stop it in Workbench before rebuilding shared artifacts')
        write_result(a.output, {'project_id': pid, 'status': 'preparing'})
        build_result = prepare(client, pid, build)
        write_result(a.output, {'project_id': pid, **build_result, 'status': 'prepared'})
        result = {**build_result, **deploy(client, pid, app_payload)}
        write_result(a.output, result)
        print(json.dumps(result, indent=2))
    finally:
        client.close()


if __name__ == '__main__':
    assert job_payload('test')['script'] == 'cai_integration/prepare_application.py'
    main()
