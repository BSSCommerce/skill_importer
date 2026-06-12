"""Admin UI for the Skill Importer plugin.

Session-protected page at ``/skill-importer`` to create / revoke / delete the
X-API-Keys used by the public import endpoint, plus copy-paste usage docs.
Mirrors community plugin conventions: ``get_current_user_from_request`` for
auth, ``get_templates()`` for rendering, 303-redirect after mutating POSTs.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from core.agents.models import Agent
from core.auth.service import get_current_user_from_request
from core.database.base import get_db
from core.template_env import get_templates
from skill_importer import service
from skill_importer.models import SkillImportApiKey, SkillImportLog

router = APIRouter(prefix="/skill-importer", tags=["skill-importer"])


def _render(request: Request, db: Session, *, new_raw_key: str | None = None):
    keys = (
        db.query(SkillImportApiKey)
        .order_by(SkillImportApiKey.created_at.desc())
        .all()
    )
    logs = (
        db.query(SkillImportLog)
        .order_by(SkillImportLog.created_at.desc())
        .limit(20)
        .all()
    )
    alias_rows = (
        db.query(Agent.alias)
        .filter(Agent.alias.is_not(None))
        .order_by(Agent.alias.asc())
        .all()
    )
    agent_aliases = [a for (a,) in alias_rows]
    example_alias = agent_aliases[0] if agent_aliases else "your-agent-alias"
    return get_templates().TemplateResponse(
        request=request,
        name="skill_importer.html",
        context={
            "request": request,
            "keys": keys,
            "logs": logs,
            "agent_aliases": agent_aliases,
            "example_alias": example_alias,
            "new_raw_key": new_raw_key,
        },
    )


@router.get("")
async def skill_importer_page(request: Request, db: Session = Depends(get_db)):
    return _render(request, db)


@router.post("/keys")
async def create_key(
    request: Request,
    name: str = Form(""),
    db: Session = Depends(get_db),
):
    user = get_current_user_from_request(db, request)
    _, raw = service.create_api_key(
        db, name=name, created_by_user_id=getattr(user, "id", None)
    )
    # Render directly (not a redirect) so the raw key can be shown exactly once.
    return _render(request, db, new_raw_key=raw)


@router.post("/keys/{key_id}/revoke")
async def revoke_key(key_id: int, db: Session = Depends(get_db)):
    row = db.query(SkillImportApiKey).filter(SkillImportApiKey.id == key_id).first()
    if row is not None:
        row.is_active = False
        db.commit()
    return RedirectResponse(url="/skill-importer", status_code=303)


@router.post("/keys/{key_id}/delete")
async def delete_key(key_id: int, db: Session = Depends(get_db)):
    row = db.query(SkillImportApiKey).filter(SkillImportApiKey.id == key_id).first()
    if row is not None:
        db.delete(row)
        db.commit()
    return RedirectResponse(url="/skill-importer", status_code=303)
