"""Find/create a private Git-backed NPI project; never change unrelated projects."""
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / '02_backend'))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import argparse
import json
from urllib.parse import urlsplit
from client import Client, load_environment, write_result

PROJECT_NAME = 'Vehicle NPI Blueprint'


def project_payload(name, git_url):
    url = urlsplit(git_url or '')
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
        raise ValueError('GIT_URL must be an HTTPS Git URL without embedded credentials')
    return {'name': name, 'description': 'EV battery-pack NPI prototype on Cloudera AI',
            'template': 'git', 'git_url': git_url, 'project_visibility': 'private'}


def setup(client, name, git_url=None, project_id=None):
    if project_id:
        row = client.request('GET', 'projects/' + project_id)
        if row.get('id') != project_id:
            raise RuntimeError('Project ID could not be verified')
        return project_id
    matches = [r for r in client.list('projects', 'projects') if r.get('name') == name]
    if len(matches) > 1:
        raise RuntimeError('Multiple projects have this name; specify CML_PROJECT_ID')
    if matches:
        raise RuntimeError('A project with this name already exists; specify CML_PROJECT_ID explicitly to reuse its storage')
    row = client.request('POST', 'projects', project_payload(name, git_url))
    project_id = row.get('id')
    if not project_id:
        raise RuntimeError('Project creation response has no ID')
    client.wait('projects/' + project_id, {'success', 'ready', 'running'},
                {'error', 'failed'}, 900, field='creation_status')
    return project_id


def main():
    load_environment()
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project-id', default=os.getenv('CML_PROJECT_ID') or os.getenv('CDSW_PROJECT_ID'))
    p.add_argument('--name', default=os.getenv('PROJECT_NAME', PROJECT_NAME))
    p.add_argument('--git-url', default=os.getenv('GIT_URL'))
    p.add_argument('--dry-run', action='store_true')
    p.add_argument('--output', default='.cai/project.json')
    a = p.parse_args()
    if a.dry_run:
        print(json.dumps({'project_id': a.project_id} if a.project_id else project_payload(a.name, a.git_url), indent=2)); return
    client = Client()
    try:
        result = {'project_id': setup(client, a.name, a.git_url, a.project_id)}
        write_result(a.output, result)
        print(json.dumps(result))
    finally:
        client.close()


if __name__ == '__main__':
    assert project_payload('test', 'https://example.com/repo.git')['project_visibility'] == 'private'
    main()
