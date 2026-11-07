"""Fresh AMP hostname discovery and browser-origin authorization regression tests."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import httpx
import pytest
from common import application_origin
from common.security import enforce_csrf
from starlette.requests import Request


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setenv('CDSW_DOMAIN','workbench.example.com')
    monkeypatch.setenv('CDSW_PROJECT_ID','test-project')
    monkeypatch.setenv('CDSW_APIV2_KEY','test-runtime-key')
    monkeypatch.setenv('NPI_AUTH_MODE','workbench')
    monkeypatch.delenv('NPI_PUBLIC_ORIGIN',raising=False)
    monkeypatch.delenv('NPI_APP_SUBDOMAIN',raising=False)


def transport(monkeypatch,handler):
    real=httpx.Client
    monkeypatch.setattr(application_origin.httpx,'Client',lambda **kw: real(**kw,transport=httpx.MockTransport(handler)))


def app(subdomain='vehicle-npi-platform-7nzina'):
    return {'id':'test-app','script':'03_frontend/start_frontend.py','subdomain':subdomain}


def test_assigned_origin_accepts_same_origin_browser_and_rejects_foreign(runtime,monkeypatch):
    def handler(request):
        assert str(request.url).startswith('https://workbench.example.com/api/v2/projects/test-project/applications')
        assert request.headers['authorization']=='Bearer test-runtime-key'
        return httpx.Response(200,json={'applications':[app()]})
    transport(monkeypatch,handler)
    origin=application_origin.configure_public_origin()
    assert origin=='https://vehicle-npi-platform-7nzina.workbench.example.com'
    def request(value):
        return Request({'type':'http','method':'POST','path':'/api/config/llm/models',
                        'headers':[(b'origin',value.encode()),(b'sec-fetch-site',b'same-origin')]})
    enforce_csrf(request(origin),{'authentication':'workbench_browser'})
    for foreign in ['https://evil.example','https://vehicle-npi-platform.workbench.example.com']:
        with pytest.raises(PermissionError):enforce_csrf(request(foreign),{'authentication':'workbench_browser'})


def test_origin_discovery_paginates_and_ignores_other_scripts(runtime,monkeypatch):
    def handler(request):
        if request.url.params.get('page_token')=='next':
            return httpx.Response(200,json={'applications':[app()]})
        return httpx.Response(200,json={'applications':[{**app(),'script':'unrelated.py'}],'next_page_token':'next'})
    transport(monkeypatch,handler)
    assert '-7nzina.' in application_origin.configure_public_origin()


@pytest.mark.parametrize('apps',[[],[app(),app('vehicle-npi-platform-another')]])
def test_missing_and_ambiguous_metadata_fail_closed(runtime,monkeypatch,apps):
    transport(monkeypatch,lambda request:httpx.Response(200,json={'applications':apps}))
    with pytest.raises(RuntimeError,match='missing or ambiguous'):application_origin.configure_public_origin()
    assert 'NPI_PUBLIC_ORIGIN' not in os.environ


@pytest.mark.parametrize('code',[302,401,403,500])
def test_metadata_errors_do_not_fall_back_to_request_host(runtime,monkeypatch,code):
    transport(monkeypatch,lambda request:httpx.Response(code,text='test-runtime-key'))
    with pytest.raises(RuntimeError) as error:application_origin.configure_public_origin()
    assert 'test-runtime-key' not in str(error.value)
    assert 'NPI_PUBLIC_ORIGIN' not in os.environ


def test_custom_origin_needs_no_runtime_key(runtime,monkeypatch):
    monkeypatch.delenv('CDSW_APIV2_KEY')
    monkeypatch.setenv('NPI_PUBLIC_ORIGIN','https://custom.example')
    assert application_origin.configure_public_origin()=='https://custom.example'


if __name__=='__main__':
    assert callable(application_origin.configure_public_origin)
