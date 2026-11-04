"""Shared backend authorization, CSRF, and mutation audit boundary."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sqlite3
from fastapi.responses import JSONResponse
from common import db
from common.runtime import auth_mode, data_mode
from common.security import authenticated_actor, enforce_csrf, is_mutation


def audit(request, identity, outcome, code):
    with db.get_connection() as conn:
        result = conn.execute('INSERT INTO audit_events(actor,authentication,permission,method,path,outcome,status_code) VALUES(?,?,?,?,?,?,?)',
                              (identity['actor'],identity['authentication'],identity['permission'],request.method,request.url.path,outcome,code))
        return result.lastrowid


async def enforce_access(request, call_next):
    if request.url.path == '/api/health':
        return await call_next(request)
    try:
        identity = authenticated_actor(request)
        request.state.identity = identity
        if is_mutation(request.method,request.url.path) and identity['permission']!='RW':
            raise PermissionError('Workbench RW permission is required for this action')
        enforce_csrf(request,identity)
    except (PermissionError,ValueError,RuntimeError) as error:
        if 'identity' in locals():
            try:
                audit(request,identity,'authorization_denied',403)
            except (RuntimeError,sqlite3.Error):
                pass
        return JSONResponse({'detail':str(error)},status_code=403)
    mutation = is_mutation(request.method,request.url.path)
    event = None
    if mutation:
        try:
            event = audit(request,identity,'authorized_attempt',None)
        except (RuntimeError,sqlite3.Error):
            return JSONResponse({'detail':'Mutation audit store is unavailable; action was not performed'},status_code=503)
    if data_mode()=='pilot':
        path = request.url.path
        # These capabilities require separately approved pilot protocols/packages.
        unsupported = path.startswith(('/api/review','/api/semantic','/api/kb','/api/asset')) or path.endswith(('/testbench','/reviews','/results','/data/test_results'))
        if unsupported:
            response = JSONResponse({'detail':'This capability is unavailable in Pilot mode; no demo evidence or computation was substituted'},status_code=503)
        else:
            response = await call_next(request)
    else:
        response = await call_next(request)
    if event is not None:
        with db.get_connection() as conn:
            conn.execute('UPDATE audit_events SET outcome=?,status_code=? WHERE event_id=?',
                         ('stream_accepted' if response.headers.get('content-type','').startswith('text/event-stream') else 'completed' if response.status_code<400 else 'rejected',response.status_code,event))
    return response


if __name__ == '__main__':
    assert callable(enforce_access) and callable(audit)
    print('Backend authorization and audit boundary OK')
