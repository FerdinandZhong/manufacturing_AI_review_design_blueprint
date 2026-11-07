"""Resolve the assigned application hostname from deployment-owned Workbench metadata."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import re
import httpx
from common.security import public_origin
from common.workbench_key import project_url


def configure_public_origin():
    """Resolve once before the backend starts; never trust request Host/Origin headers.

    The runtime's key reads deployment metadata only. Caller authorization still
    validates the caller's own key independently on every request.
    """
    if os.getenv('NPI_PUBLIC_ORIGIN', '').strip():
        return public_origin()
    url, _ = project_url()
    token = os.getenv('CDSW_APIV2_KEY', '').strip()
    if not token or any(ord(c) < 33 or ord(c) > 126 for c in token):
        raise RuntimeError('Application origin discovery requires the runtime CDSW_APIV2_KEY; alternatively set NPI_PUBLIC_ORIGIN')
    prefix = os.getenv('NPI_APP_SUBDOMAIN', '').strip() or 'vehicle-npi-platform'
    label = r'[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?'
    if not re.fullmatch(label, prefix):
        raise ValueError('NPI_APP_SUBDOMAIN must be a DNS label')
    matches = []
    seen = set()
    page = None
    try:
        with httpx.Client(timeout=10, follow_redirects=False, trust_env=False) as client:
            while True:
                params = {'page_size':100}
                if page:
                    params['page_token'] = page
                response = client.get(url+'/applications',params=params,headers={'Authorization':'Bearer '+token})
                if response.status_code != 200:
                    raise RuntimeError('Workbench application metadata is unavailable; set NPI_PUBLIC_ORIGIN if metadata access is disabled')
                payload = response.json()
                for app in payload['applications']:
                    subdomain = app.get('subdomain','')
                    if (app.get('script') == '03_frontend/start_frontend.py' and
                            re.fullmatch(label,subdomain) and (subdomain == prefix or subdomain.startswith(prefix+'-'))):
                        matches.append(subdomain)
                page = payload.get('next_page_token')
                if not page:
                    break
                if page in seen:
                    raise RuntimeError('Workbench application metadata repeated a page')
                seen.add(page)
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        raise RuntimeError('Could not resolve the application origin from Workbench metadata') from None
    if len(matches) != 1:
        raise RuntimeError('Application origin is missing or ambiguous; set NPI_PUBLIC_ORIGIN to this application HTTPS URL')
    domain = os.environ['CDSW_DOMAIN'].strip()
    os.environ['NPI_PUBLIC_ORIGIN'] = f'https://{matches[0]}.{domain}'
    return public_origin()


if __name__ == '__main__':
    assert callable(configure_public_origin)
    print('Deployment-owned application origin discovery available')
