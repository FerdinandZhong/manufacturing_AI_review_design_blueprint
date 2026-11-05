"""Native Workbench identity with a signed, process-owned loopback hop."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import hmac
import ipaddress
import json
from urllib.parse import urlsplit
from common.runtime import auth_mode

INTERNAL = {'x-npi-actor','x-npi-permission','x-npi-auth-kind','x-npi-proof'}
IDENTITY = {'remote-user','remote-user-perm','remote_user','remote_user_perm'}


def public_origin():
    value = os.getenv('NPI_PUBLIC_ORIGIN','').rstrip('/')
    url = urlsplit(value)
    _ = url.port
    if url.scheme != 'https' or not url.hostname or url.username or url.password or url.path or url.query or url.fragment:
        raise ValueError('Workbench requires NPI_PUBLIC_ORIGIN as an exact HTTPS origin')
    return value


def proxy_is_trusted(peer):
    try:
        address = ipaddress.ip_address(peer)
        networks = [ipaddress.ip_network(c.strip()) for c in os.getenv('NPI_TRUSTED_PROXY_CIDRS','').split(',') if c.strip()]
        return bool(networks) and any(address in network for network in networks)
    except ValueError:
        return False


def sign(secret, actor, permission, kind, method, path, origin):
    payload = json.dumps([actor,permission,kind,method,path,origin], separators=(',',':')).encode()
    return hmac.new(secret.encode(),payload,hashlib.sha256).hexdigest()


def forwarded_identity(request, secret):
    """Accept native headers only from the configured Workbench proxy socket."""
    if auth_mode() == 'local_demo':
        return {}
    public_origin()
    if not os.getenv('NPI_TRUSTED_PROXY_CIDRS','').strip():
        raise PermissionError('Workbench requires NPI_TRUSTED_PROXY_CIDRS with verified ingress proxy ranges')
    if not proxy_is_trusted(request.client.host if request.client else ''):
        raise PermissionError('Untrusted Workbench ingress; verify NPI_TRUSTED_PROXY_CIDRS against the platform ingress peers')
    values = {}
    for name in ('remote-user','remote-user-perm'):
        native = request.headers.getlist(name)
        if len(native) != 1 or not native[0] or any(ord(c)<32 for c in native[0]):
            raise PermissionError('Missing or ambiguous native Workbench identity')
        values[name] = native[0]
    if any(name in request.headers for name in ('remote_user','remote_user_perm')):
        raise PermissionError('Ambiguous native Workbench identity')
    actor, permission = values['remote-user'], values['remote-user-perm']
    if len(actor)>256 or permission not in {'RO','RW'}:
        raise PermissionError('Workbench access is unauthorized')
    kind = 'machine' if request.headers.get('authorization','').lower().startswith('bearer ') else 'browser'
    origin = request.headers.get('origin','')
    path = request.url.path + ('?'+request.url.query if request.url.query else '')
    return {'x-npi-actor':actor,'x-npi-permission':permission,'x-npi-auth-kind':kind,
            'x-npi-proof':sign(secret,actor,permission,kind,request.method,path,origin)}


def authenticated_actor(request):
    if auth_mode() == 'local_demo':
        return {'actor':'local-demo','permission':'RW','authentication':'explicit_local_demo_policy'}
    secret = os.getenv('NPI_INGRESS_SECRET','')
    public_origin()
    try:
        loopback = ipaddress.ip_address(request.client.host).is_loopback
    except (ValueError,AttributeError):
        loopback = False
    if not secret or not loopback:
        raise PermissionError('Workbench identity requires the trusted frontend hop')
    if any(name in request.headers for name in IDENTITY):
        raise PermissionError('Native identity must terminate at the trusted frontend')
    for name in INTERNAL:
        if len(request.headers.getlist(name)) != 1:
            raise PermissionError('Missing or ambiguous trusted frontend identity')
    actor = request.headers['x-npi-actor']
    permission = request.headers['x-npi-permission']
    kind = request.headers['x-npi-auth-kind']
    path = request.url.path + ('?'+request.url.query if request.url.query else '')
    expected = sign(secret,actor,permission,kind,request.method,path,request.headers.get('origin',''))
    if permission not in {'RO','RW'} or kind not in {'browser','machine'} or not hmac.compare_digest(expected,request.headers['x-npi-proof']):
        raise PermissionError('Invalid trusted frontend proof')
    return {'actor':actor,'permission':permission,'authentication':'workbench_'+kind}


def is_mutation(method, path):
    # Semantic explanation POST only narrates; it never persists state.
    return (method not in {'GET','HEAD','OPTIONS'} and path != '/api/semantic/explain') or (path.startswith('/api/review/') and path.endswith('/stream'))


def enforce_csrf(request, identity):
    if not is_mutation(request.method,request.url.path):
        return
    origin = request.headers.get('origin')
    site = request.headers.get('sec-fetch-site')
    if auth_mode() == 'local_demo':
        allowed = {str(request.base_url).rstrip('/')}
        local = os.getenv('NPI_LOCAL_ORIGIN','')
        if local:
            allowed.update({local,local.replace('127.0.0.1','localhost')})
        if site in {'cross-site','same-site'} or (origin and origin not in allowed):
            raise PermissionError('Cross-origin mutation is forbidden')
        return
    expected = public_origin()
    if site in {'cross-site','same-site'} or (origin is not None and origin != expected):
        raise PermissionError('Cross-origin mutation is forbidden')
    if identity['authentication']=='workbench_machine':
        return
    referer = request.headers.get('referer','')
    parsed = urlsplit(referer)
    referer_origin = f'{parsed.scheme}://{parsed.netloc}' if parsed.netloc else ''
    if origin != expected and not (referer_origin==expected and request.headers.get('x-npi-request')=='1'):
        raise PermissionError('Browser mutations require a same-origin request')


if __name__ == '__main__':
    assert is_mutation('GET','/api/review/p/stream')
    assert not is_mutation('POST','/api/semantic/explain')
    assert sign('s','a','RO','browser','GET','/x','') != sign('s','a','RW','browser','GET','/x','')
    print('Workbench boundary contract OK')
