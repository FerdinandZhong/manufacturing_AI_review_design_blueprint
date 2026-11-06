import os
import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from npi_mcp import server


@pytest.fixture(autouse=True)
def clear_key_environment(monkeypatch):
    for name in ('CDSW_APIV2_KEY', 'NPI_API_BEARER_TOKEN', 'NPI_API_TOKEN'):
        monkeypatch.delenv(name, raising=False)


def test_single_workbench_key_takes_precedence(monkeypatch):
    monkeypatch.setenv("CDSW_APIV2_KEY", "Bearer workbench-key")
    monkeypatch.setenv("NPI_API_BEARER_TOKEN", "stale-alias")
    assert server._headers() == {"Authorization": "Bearer workbench-key"}
    monkeypatch.setenv("CDSW_APIV2_KEY", "bad key")
    with pytest.raises(RuntimeError, match="whitespace"):
        server._headers()


def test_base_url_and_token(monkeypatch):
    monkeypatch.setenv("NPI_API_BASE_URL", "https://npi.example.com/api/")
    monkeypatch.setenv("NPI_API_BEARER_TOKEN", "Bearer token-value")
    assert server._base_url() == "https://npi.example.com/api"
    assert server._headers() == {"Authorization": "Bearer token-value"}
    monkeypatch.delenv("NPI_API_BEARER_TOKEN")
    monkeypatch.setenv("NPI_API_TOKEN", "legacy-token")
    assert server._headers() == {"Authorization": "Bearer legacy-token"}
    monkeypatch.setenv("NPI_API_BASE_URL", "https://npi.example.com/not-api")
    with pytest.raises(RuntimeError, match="end with /api"):
        server._base_url()


def test_request_uses_expected_path_and_does_not_follow_redirects(monkeypatch):
    monkeypatch.setenv("NPI_API_BASE_URL", "https://npi.example.com/api")
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def request(self, method, url, **kwargs):
            seen.update(method=method, url=url, request=kwargs)
            return httpx.Response(200, json={"ok": True})

    monkeypatch.setattr(server.httpx, "Client", FakeClient)
    assert server._request("GET", "/programs") == {"ok": True}
    assert seen["follow_redirects"] is False
    assert seen["url"] == "https://npi.example.com/api/programs"


def test_request_rejects_redirect_and_non_json(monkeypatch):
    monkeypatch.setenv("NPI_API_BASE_URL", "https://npi.example.com/api")
    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def request(self, *args, **kwargs): return httpx.Response(302, headers={"location": "/login"})
    monkeypatch.setattr(server.httpx, "Client", FakeClient)
    with pytest.raises(RuntimeError, match="redirected"):
        server._request("GET", "/programs")


def test_request_redacts_bearer_authentication_errors(monkeypatch):
    monkeypatch.setenv("NPI_API_BASE_URL", "https://npi.example.com/api")
    monkeypatch.setenv("NPI_API_BEARER_TOKEN", "secret-value")

    class FakeClient:
        def __init__(self, **kwargs): pass
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def request(self, *args, **kwargs): return httpx.Response(401, json={"detail": "no"})

    monkeypatch.setattr(server.httpx, "Client", FakeClient)
    with pytest.raises(RuntimeError, match="bearer authentication.*was rejected") as error:
        server._request("GET", "/programs")
    assert "secret-value" not in str(error.value)


def test_program_path_encodes_input():
    assert server._program_path("PACK/ATLAS") == "/programs/PACK%2FATLAS"
    with pytest.raises(ValueError):
        server._program_path("")
