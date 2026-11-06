"""Bounded, read-only NiFi inspection. Never feeds the NPI decision pipeline."""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import ssl
from urllib.parse import urlsplit, quote
import httpx
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Literal

router = APIRouter(prefix="/api/nifi", tags=["NiFi reader"])
LIMIT = 100


def settings():
    return {"url": os.getenv("NIFI_API_URL", "").strip().rstrip("/"),
            "group": os.getenv("NIFI_PROCESS_GROUP_ID", "root").strip(),
            "token": os.getenv("NIFI_TOKEN", "").strip(),
            "ca": os.getenv("NIFI_CA_BUNDLE", "").strip()}


def safe_text(value, limit=240):
    text = str(value or "")
    token = settings()["token"]
    if token:
        text = text.replace(token.removeprefix("Bearer "), "[redacted]")
    text = re.sub(r"(?i)(bearer\s+)\S+", r"\1[redacted]", text)
    text = re.sub(r"(?i)((?:password|token|secret|api[_-]?key)\s*[:=]\s*)[^\s,;]+", r"\1[redacted]", text)
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[redacted]@", text)
    return text[:limit]


def normalize(flow, status, bulletins, mode):
    entity = flow["processGroupFlow"]
    group = entity["id"]
    contents = entity["flow"]
    snapshot = status["processGroupStatus"]["aggregateSnapshot"]
    processors = []
    for item in contents.get("processors", [])[:LIMIT]:
        c = item.get("component") or {}
        processors.append({"id": safe_text(item.get("id") or c.get("id")),
                           "name": safe_text(c.get("name") or item.get("id")),
                           "state": safe_text(c.get("state") or "UNKNOWN"),
                           "validation": safe_text(c.get("validationStatus") or "UNKNOWN"),
                           "type": safe_text(c.get("type")),
                           "threads": (item.get("status") or {}).get("aggregateSnapshot", {}).get("activeThreadCount")})
    connections = []
    for item in contents.get("connections", [])[:LIMIT]:
        c = item.get("component") or {}
        snap = (item.get("status") or {}).get("aggregateSnapshot", {})
        connections.append({"id": safe_text(item.get("id") or c.get("id")),
                            "source": safe_text((c.get("source") or {}).get("id")),
                            "target": safe_text((c.get("destination") or {}).get("id")),
                            "relationships": [safe_text(x) for x in c.get("selectedRelationships", [])[:20]],
                            "queued": snap.get("flowFilesQueued")})
    recent = []
    for item in bulletins["bulletinBoard"].get("bulletins", [])[:LIMIT]:
        b = item.get("bulletin") or {}
        if b.get("groupId") != group:
            continue
        recent.append({"id": safe_text(b.get("id")), "source": safe_text(b.get("sourceName")),
                       "level": safe_text(b.get("level")), "timestamp": safe_text(b.get("timestamp")),
                       # Native messages may contain credentials or processor property values.
                       "message": "Message omitted; inspect the bulletin in NiFi for details."})
    limits = ["Direct child processors and connections only; nested groups and ports are not expanded.",
              "Status metrics cover the selected group; processor counts cover listed direct children.",
              "Bulletins are retained recent events, not historical logs. Bulletin timestamps use the source timezone."]
    if any(len(contents.get(k, [])) > LIMIT for k in ("processors", "connections")):
        limits.append("Inventory truncated to 100 processors and 100 connections. Select a smaller group on the server.")
    if len(bulletins["bulletinBoard"].get("bulletins", [])) >= LIMIT:
        limits.append("Bulletins reached the 100-event limit; more events may exist.")
    return {"mode": mode, "group_id": safe_text(group),
            "name": safe_text(snapshot.get("name") or group),
            "refreshed": safe_text(status["processGroupStatus"].get("statsLastRefreshed") or "Not supplied by source"),
            "processors": processors, "connections": connections, "bulletins": recent,
            "metrics": {"queued": snapshot.get("flowFilesQueued"), "bytes_queued": snapshot.get("bytesQueued"),
                        "active_threads": snapshot.get("activeThreadCount"), "received": snapshot.get("flowFilesReceived")},
            "limitations": limits}


def sample_snapshot():
    names = ["Receive test evidence", "Validate test schema", "Route by program", "Publish evidence"]
    processors = [{"id": f"sample-{i}", "component": {"name": name, "state": "STOPPED" if i == 3 else "RUNNING",
                  "validationStatus": "VALID", "type": "Sample processor"},
                  "status": {"aggregateSnapshot": {"activeThreadCount": 0 if i == 3 else 1}}} for i, name in enumerate(names)]
    connections = [{"id": f"connection-{i}", "component": {"source": {"id": f"sample-{i}"},
                   "destination": {"id": f"sample-{i+1}"}, "selectedRelationships": ["success"]},
                   "status": {"aggregateSnapshot": {"flowFilesQueued": 24 if i == 2 else 0}}} for i in range(3)]
    return normalize({"processGroupFlow": {"id": "sample-evidence", "flow": {"processors": processors, "connections": connections}}},
                     {"processGroupStatus": {"statsLastRefreshed": "2026-10-22T08:00:00Z", "aggregateSnapshot": {
                         "name": "Battery test evidence ingestion", "flowFilesQueued": 24, "bytesQueued": 49152,
                         "activeThreadCount": 3, "flowFilesReceived": 1200}}},
                     {"bulletinBoard": {"bulletins": [{"bulletin": {"id": "sample-bulletin", "groupId": "sample-evidence",
                         "sourceName": "Publish evidence", "level": "WARN", "timestamp": "2026-10-22T08:00:00Z"}}]}}, "sample")


@router.get("/config")
def config():
    s = settings()
    return {"configured": bool(s["url"]), "group_id": safe_text(s["group"]), "read_only": True}


@router.get("/snapshot")
async def read_snapshot(mode: Literal["sample", "live"] = "sample"):
    from common.runtime import data_mode
    if data_mode()=="pilot" and mode=="sample":
        raise HTTPException(503, "Sample NiFi data is disabled in Pilot mode. Select configured live inspection.")
    if mode == "sample":
        return sample_snapshot()
    s = settings()
    if not s["url"]:
        raise HTTPException(503, "NiFi is not configured. Set NIFI_API_URL and NIFI_PROCESS_GROUP_ID on the backend.")
    url = urlsplit(s["url"])
    if url.scheme not in {"https", "http"} or not url.hostname or url.username or url.password or url.query or url.fragment or not url.path.endswith("/nifi-api"):
        raise HTTPException(503, "NIFI_API_URL must be an HTTP(S) URL ending in /nifi-api, without credentials, query, or fragment.")
    if not re.fullmatch(r"root|[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", s["group"]):
        raise HTTPException(503, "NIFI_PROCESS_GROUP_ID must be root or a NiFi process-group UUID.")
    if s["token"] and url.scheme != "https":
        raise HTTPException(503, "Use HTTPS when configuring a NiFi bearer token.")
    token = s["token"]
    headers = {"Authorization": token if token.lower().startswith("bearer ") else "Bearer " + token} if token else {}
    try:
        tls = ssl.create_default_context(cafile=s["ca"] or None)
        async with httpx.AsyncClient(verify=tls, timeout=15, follow_redirects=False) as client:
            async def get(path, params=None):
                # Fixed GET routes; target comes only from server configuration.
                async with client.stream("GET", s["url"] + path, headers=headers, params=params) as response:
                    response.raise_for_status()
                    payload = bytearray()
                    async for chunk in response.aiter_bytes():
                        payload.extend(chunk)
                        if len(payload) > 4_000_000:
                            raise ValueError("Response too large")
                import json
                return json.loads(payload)
            flow = await get("/flow/process-groups/" + quote(s["group"], safe=""))
            group = flow["processGroupFlow"]["id"]
            if not re.fullmatch(r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", group):
                raise ValueError("Missing process group")
            if s["group"] != "root" and group != s["group"]:
                raise ValueError("Scope mismatch")
            status = await get(f"/flow/process-groups/{group}/status")
            if status["processGroupStatus"].get("id") != group:
                raise ValueError("Status scope mismatch")
            bulletins = await get("/flow/bulletin-board", {"groupId": "^" + re.escape(group) + "$", "limit": LIMIT})
            return normalize(flow, status, bulletins, "live")
    except (httpx.HTTPError, ValueError, KeyError, TypeError, AttributeError, OSError):
        raise HTTPException(502, "NiFi could not be read. Check the server URL, group permissions, token, and trusted CA. No sample data was substituted.") from None


class InspectionQuestion(BaseModel):
    question: str = Field(min_length=1,max_length=500)
    mode: Literal['sample','live'] = 'sample'


@router.post('/ask')
async def ask(body: InspectionQuestion, request: Request):
    from common.i18n import nifi_intent, request_language
    request.scope['npi.language'] = request_language(request.scope,body.question)
    try:
        intent = nifi_intent(body.question)
    except ValueError as error:
        raise HTTPException(422,str(error)) from None
    # The same bounded GET-only source reader handles both languages.
    return {'intent':intent,'snapshot':await read_snapshot(body.mode)}


if __name__ == "__main__":
    result = sample_snapshot()
    assert result == sample_snapshot()
    assert result["metrics"]["queued"] == 24
    assert len(result["processors"]) == 4
    assert all("properties" not in p for p in result["processors"])
    print("nifi OK — deterministic sample, projected read-only data")
