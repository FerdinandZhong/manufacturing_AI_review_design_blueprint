"""Translate JSON/SSE display fields after authorization and deterministic computation."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import json
from common.i18n import localize_payload, request_language


class LocalizationMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope,receive,send)
        state = {'start':None,'kind':'','buffer':b'','language':'en'}
        async def localized_send(message):
            if message['type'] == 'http.response.start':
                language = scope.get('npi.language') or request_language(scope)
                state['language'] = language
                headers = [(k,v) for k,v in message.get('headers',[]) if k.lower() not in {b'content-language'}]
                headers.append((b'content-language', b'zh-CN' if language=='zh' else b'en'))
                headers.append((b'vary',b'Accept-Language'))
                content_type = dict(headers).get(b'content-type',b'')
                state['kind'] = 'json' if b'application/json' in content_type else 'sse' if b'text/event-stream' in content_type else ''
                message = {**message,'headers':headers}
                if language == 'zh' and state['kind'] in {'json','sse'}:
                    message['headers'] = [(k,v) for k,v in headers if k.lower() not in {b'content-length',b'etag'}]
                    state['start'] = message
                    if state['kind']=='json':return
                await send(message)
                return
            if message['type']!='http.response.body' or state['language']!='zh' or not state['kind']:
                return await send(message)
            state['buffer'] += message.get('body',b'')
            if state['kind']=='json':
                if message.get('more_body',False):return
                if not state['buffer']:
                    await send(state['start'])
                    await send(message)
                    return
                payload = json.loads(state['buffer'])
                body = json.dumps(localize_payload(payload,'zh'),ensure_ascii=False,separators=(',',':')).encode()
                start = state['start']
                start['headers'].append((b'content-length',str(len(body)).encode()))
                await send(start)
                await send({**message,'body':body})
            else:
                chunks = state['buffer'].split(b'\n\n')
                state['buffer'] = chunks.pop()
                output = []
                for chunk in chunks:
                    lines = []
                    for line in chunk.split(b'\n'):
                        if line.startswith(b'data: ') and line[6:]!=b'[DONE]':
                            payload = json.loads(line[6:])
                            line = b'data: '+json.dumps(localize_payload(payload,'zh'),ensure_ascii=False).encode()
                        lines.append(line)
                    output.append(b'\n'.join(lines)+b'\n\n')
                if not message.get('more_body',False):
                    output.append(state['buffer'])
                    state['buffer'] = b''
                await send({**message,'body':b''.join(output)})
        await self.app(scope,receive,localized_send)


if __name__ == '__main__':
    assert callable(LocalizationMiddleware)
    print('JSON and SSE presentation localization available')
