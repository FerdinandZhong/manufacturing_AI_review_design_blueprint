"""Verify shipped image/document bytes and matching HTTP content types."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import xml.etree.ElementTree as ET
from fastapi.testclient import TestClient
from api.main import app
from knowledge import kb
from data_generation.generate_assets import build_assets


def test_assets_are_deterministic_and_real_content():
    first, second = build_assets(), build_assets()
    assert first == second
    for asset in first:
        blob = asset['blob']
        if asset['ontology_class'] == 'DesignImage':
            svg = ET.fromstring(blob)
            assert int(svg.attrib['width']) >= 800
            assert b'Synthetic demo schematic' in blob
        elif asset['ontology_class'] == 'ComponentPhoto':
            assert blob.startswith(b'\xff\xd8') and len(blob) > 10000
            assert 'RudolfSimon' in asset['provenance'] and asset['license_url']
        else:
            assert asset['modality'] == 'text' and blob.decode('utf-8')


def test_asset_mime_matches_shipped_content(monkeypatch):
    assets = {asset['asset_id']: asset for asset in build_assets()}
    monkeypatch.setattr(kb, 'get_asset', lambda asset_id: assets[asset_id])
    with TestClient(app) as client:
        for asset in assets.values():
            response = client.get('/api/asset/' + asset['asset_id'])
            expected = {'DesignImage': 'image/svg+xml', 'ComponentPhoto': 'image/jpeg'}.get(asset['ontology_class'], 'text/plain')
            assert response.headers['content-type'].startswith(expected)
            assert response.content == asset['blob']


if __name__ == '__main__':
    test_assets_are_deterministic_and_real_content()
    assert len(build_assets()) == 10
