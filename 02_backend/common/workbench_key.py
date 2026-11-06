"""Validate each caller's Workbench key against this application's project."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
import httpx


def project_url():
    # Only deployment-owned configuration chooses the credential destination.
    domain = os.getenv('CDSW_DOMAIN', '').strip()
    project = os.getenv('CDSW_PROJECT_ID', '').strip()
    label = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
    if not re.fullmatch(label + r'(?:\.' + label + r')*', domain):
        raise PermissionError('Workbench key validation requires a valid CDSW_DOMAIN')
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}', project):
        raise PermissionError('Workbench key validation requires CDSW_PROJECT_ID')
    return f'https://{domain}/api/v2/projects/{project}', project


def validate_key(token):
    """Return the verified username and current project permission; never cache keys."""
    if not token or len(token) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise PermissionError('Invalid Workbench bearer credential')
    url, project = project_url()
    try:
        with httpx.Client(timeout=5.0, follow_redirects=False, trust_env=False) as client:
            validated = client.post(url.split('/api/v2/')[0] + '/api/v2/auth/validate_key',
                                    headers={'Authorization': f'Bearer {token}'}, json={'audience':'API'})
            if validated.status_code != 200:
                raise PermissionError('Workbench key validation failed')
            identity = validated.json()
            if not isinstance(identity, dict) or identity.get('valid') is not True:
                raise PermissionError('Workbench key validation failed')
            actor = identity.get('username')
            if not isinstance(actor, str) or not actor.strip() or len(actor) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in actor):
                raise PermissionError('Workbench returned an invalid user identity')
            response = client.get(url, headers={'Authorization': f'Bearer {token}'})
        if response.status_code != 200:
            raise PermissionError('Workbench key validation failed; verify key access to the vehicle project')
        data = response.json()
    except (httpx.HTTPError, ValueError):
        raise PermissionError('Workbench key validation is unavailable') from None
    if not isinstance(data, dict) or data.get('id') != project:
        raise PermissionError('Workbench returned an invalid project identity')
    permissions = data.get('permissions')
    if not isinstance(permissions, dict) or permissions.get('read') is not True:
        raise PermissionError('Workbench project read permission is required')
    permission = 'RW' if permissions.get('write') is True or permissions.get('admin') is True else 'RO'
    return actor, permission


if __name__ == '__main__':
    assert callable(validate_key) and callable(project_url)
    print('Workbench user and project validation contract OK')
