"""Public skill-import API (machine-to-machine, X-API-Key authenticated).

Mounted under ``/api/skill-import`` which is registered as a public prefix in
``core.auth.middleware`` so it bypasses the session-cookie gate — auth is done
here via the ``X-API-Key`` header instead.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from core.database.base import get_db
from skill_importer import service

router = APIRouter(prefix="/api/skill-import", tags=["skill-import"])


@router.post("/skills")
async def import_skills_endpoint(request: Request, db: Session = Depends(get_db)):
    """Import Agent skills from JSON.

    Headers::

        X-API-Key: <key created in the Skill Importer admin page>
        Content-Type: application/json

    Body::

        {
          "agent_alias": "support-bot",
          "skills": [
            {
              "name": "Refund policy",
              "description": "How to handle refund requests",
              "content": "# Refunds\\n...markdown...",
              "tags": "support,billing",
              "status": "enabled"
            }
          ]
        }

    A single skill may be sent as ``{"agent_alias": ..., "skill": {...}}``.
    Skills are matched by ``name``: existing ones are updated (with version
    history), new ones are created.
    """
    key = service.resolve_active_api_key(db, request.headers.get("X-API-Key"))
    if key is None:
        return JSONResponse(
            status_code=401,
            content={"detail": "Invalid or missing API key. Pass X-API-Key header."},
        )
    service.touch_key(db, key)

    try:
        payload = await request.json()
    except Exception:
        return JSONResponse(status_code=400, content={"detail": "Body must be valid JSON"})
    if not isinstance(payload, dict):
        return JSONResponse(status_code=400, content={"detail": "Body must be a JSON object"})

    alias = str(payload.get("agent_alias") or "").strip() or None
    try:
        result = service.import_skills(db, payload)
    except ValueError as e:
        service.record_log(
            db,
            api_key_id=key.id,
            agent_alias=alias,
            created=0,
            updated=0,
            status="error",
            message=str(e),
        )
        return JSONResponse(status_code=400, content={"detail": str(e)})

    service.record_log(
        db,
        api_key_id=key.id,
        agent_alias=alias,
        created=result.created,
        updated=result.updated,
        status="ok",
        message=None,
    )
    return {
        "ok": True,
        "agent_alias": alias,
        "created": result.created,
        "updated": result.updated,
        "skipped": result.skipped,
        "skills": result.skill_names,
    }
