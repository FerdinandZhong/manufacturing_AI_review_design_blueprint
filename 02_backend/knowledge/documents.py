"""Build-time source extraction with stable, attributable chunks.

Captions remain metadata. Missing OCR never becomes extracted source text.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import hashlib
import io
import json
import re
import xml.etree.ElementTree as ET

EXTRACTION_VERSION = 'document-chunks-v1'


def extract_document(asset):
    blob = asset['blob']
    digest = hashlib.sha256(blob).hexdigest()
    sections = []
    method = 'unavailable'
    status = 'available'
    detail = ''
    transcription_metadata = None
    if len(blob)>20_000_000:
        return {'chunks':[], 'state':'unsupported', 'detail':'Source exceeds 20 MB extraction bound'}
    if asset['modality'] == 'text':
        text = blob.decode('utf-8', errors='strict')
        try:
            value = json.loads(text)
            sections = [(1, str(key), json.dumps(item, sort_keys=True, ensure_ascii=False)) for key, item in sorted(value.items())] if isinstance(value, dict) else [(1, 'document', text)]
            method = 'utf8-json'
        except ValueError:
            sections, method = [(1, 'document', text)], 'utf8-text'
    elif asset['modality'] == 'pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(blob))
        if len(reader.pages)>100:
            return {'chunks':[], 'state':'unsupported', 'detail':'PDF exceeds 100 page extraction bound'}
        sections = [(i+1, 'page', (page.extract_text() or '')[:200000]) for i, page in enumerate(reader.pages)]
        if any(not text.strip() for _,_,text in sections):
            status, detail = 'partial_or_scanned', 'Pages without extractable text require separate image OCR; PDF raster OCR is unsupported'
        method = 'pypdf-text-v1'
    elif blob.lstrip().startswith(b'<svg') or b'<svg' in blob[:200]:
        tree = ET.fromstring(blob)
        text = ' '.join(''.join(node.itertext()) for node in tree.iter() if node.tag.rsplit('}',1)[-1] in {'text'})
        sections, method = [(1, 'svg-text-elements', text)], 'svg-text-markup-v1'
    elif asset['modality'] == 'image':
        from knowledge.openai_ocr import extract_image, OpenAIOCRUnavailable
        try:
            cached = extract_image(blob, allow_remote=False)
            sections = [(1, 'ocr-unverified', cached['text'])]
            method = cached['extraction_method']
            transcription_metadata = {key:cached[key] for key in ('source_sha256','contract','cache_key','verification','extraction_method','transcription','page','width','height','submitted_width','submitted_height')}
            status = cached['transcription']['status']
        except OpenAIOCRUnavailable as exc:
            status, detail = 'unavailable', str(exc)
    chunks = []
    for page, section, text in sections:
        text = re.sub(r'\s+', ' ', text).strip()
        # Fixed overlapping character windows are reproducible and retain source locators.
        for start in range(0, len(text), 1000):
            part = text[start:start+1200]
            identity = f'{EXTRACTION_VERSION}:{asset["asset_id"]}:{digest}:{page}:{section}:{start}:{method}:{part}'
            chunks.append({'chunk_id':'CHK-'+hashlib.sha256(identity.encode()).hexdigest()[:24],
                           'asset_id':asset['asset_id'], 'source_sha256':digest, 'page':page,
                           'section':section, 'offset':start, 'text':part, 'extraction_method':method,
                           'verification':'unverified transcription; reference only' if 'OCR' in method else 'source text; applicability unchanged',
                           'extraction_version':EXTRACTION_VERSION,
                           **({'transcription_metadata':transcription_metadata} if transcription_metadata else {})})
    return {'chunks':chunks, 'state':status, 'detail':detail, 'method':method,
            **({'transcription_metadata':transcription_metadata} if transcription_metadata else {})}


def extract_chunks(asset):
    return extract_document(asset)['chunks']


if __name__ == '__main__':
    asset = {'asset_id':'self-check','modality':'text','blob':b'Visible source text'}
    assert extract_chunks(asset) == extract_chunks(asset)
    assert extract_chunks(asset)[0]['text']=='Visible source text'
