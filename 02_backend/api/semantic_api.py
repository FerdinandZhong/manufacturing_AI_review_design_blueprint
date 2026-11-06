"""Read-only semantic context and explicitly requested prose generation."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from typing import Literal
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from knowledge import semantic

router = APIRouter(prefix='/api/semantic', tags=['Semantic context'])


class ExplainRequest(BaseModel):
    question_id: Literal['thermal', 'packaging', 'venting', 'applicability'] = 'thermal'
    narration: Literal['template', 'model'] = 'template'
    include_images: bool = False
    program_id: str = 'PACK-ATLAS-01'
    question: str | None = Field(default=None, max_length=500)


@router.get('/model')
def model():
    return semantic.metadata()


@router.get('/context')
def context(question_id: Literal['thermal', 'packaging', 'venting', 'applicability'] = 'thermal', program_id: str = 'PACK-ATLAS-01'):
    try:
        return semantic.context(program_id=program_id, question_id=question_id)
    except KeyError:
        raise HTTPException(404, 'Unknown program or predefined question') from None
    except FileNotFoundError:
        raise HTTPException(503, 'The real reference evidence package has not been prepared yet.') from None


@router.post('/explain')
def explain(body: ExplainRequest, request: Request):
    try:
        from common.i18n import request_language, semantic_intent
        question_id = semantic_intent(body.question) if body.question else body.question_id
        request.scope['npi.language'] = request_language(request.scope,body.question or '')
        return semantic.explain(question_id, body.narration, body.include_images, body.program_id)
    except KeyError:
        raise HTTPException(404, 'Unknown program or predefined question') from None
    except FileNotFoundError:
        raise HTTPException(503, 'The real reference evidence package has not been prepared yet.') from None
    except ValueError as error:
        raise HTTPException(422, str(error)) from None


@router.get('/assets/{asset_id}')
def asset(asset_id: str):
    item = next((a for a in semantic.evidence_catalog() if a['id'] == asset_id), None)
    if item is None:
        from knowledge import kb
        from fastapi.responses import Response
        try:
            report = kb.get_asset(asset_id)
        except ValueError:
            raise HTTPException(409, 'Asset snapshot is stale; rebuild the knowledge base') from None
        except KeyError:
            raise HTTPException(404, 'Unknown reference asset') from None
        return Response(bytes(report['blob']), media_type='text/plain')
    if item['state'] != 'available':
        raise HTTPException(409, 'Reference file missing or checksum invalid')
    path = semantic.asset_path(item)
    return FileResponse(path, media_type=item['mime_type'])


@router.get('/experiments.csv')
def measurements():
    if semantic.metadata()['research_state'] != 'available':
        raise HTTPException(404, 'Verified measurement package unavailable')
    return FileResponse(semantic.REFERENCES / 'experiments.csv', media_type='text/csv', filename='published-battery-experiments.csv')


if __name__ == '__main__':
    assert len(router.routes) == 5
    assert ExplainRequest().narration == 'template'
    print('semantic API OK — read-only source routes and prose-only explanations')
