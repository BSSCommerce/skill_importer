"""Key management + skill import logic for the Skill Importer plugin.

Keeping this separate from the routers means both the admin UI router and the
public API router share one implementation (key hashing, agent lookup, skill
upsert with version history).
"""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from core.agents.models import Agent, AgentSkill
from core.agents.skill_tags import normalize_skill_tags
from core.agents.skill_versioning import maybe_record_agent_skill_version
from skill_importer.models import SkillImportApiKey, SkillImportLog

KEY_PREFIX = "sk_imp_"
VALID_STATUSES = {"enabled", "disabled"}


# --- API keys ----------------------------------------------------------------
def generate_api_key() -> tuple[str, str, str]:
    """Return ``(raw_key, display_prefix, key_hash)``.

    The raw key is shown to the admin exactly once; only ``key_hash`` and the
    short ``display_prefix`` are stored.
    """
    raw = KEY_PREFIX + secrets.token_urlsafe(32)
    return raw, raw[: len(KEY_PREFIX) + 4], hash_api_key(raw)


def hash_api_key(raw_key: str) -> str:
    return hashlib.sha256(raw_key.encode()).hexdigest()


def create_api_key(
    db: Session, *, name: str, created_by_user_id: str | None
) -> tuple[SkillImportApiKey, str]:
    raw, prefix, key_hash = generate_api_key()
    row = SkillImportApiKey(
        name=name.strip() or "Import key",
        key_prefix=prefix,
        key_hash=key_hash,
        created_by_user_id=created_by_user_id,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row, raw


def resolve_active_api_key(db: Session, raw_key: str | None) -> SkillImportApiKey | None:
    """Return the active key matching the raw header value, or ``None``."""
    if not raw_key:
        return None
    return (
        db.query(SkillImportApiKey)
        .filter(
            SkillImportApiKey.key_hash == hash_api_key(raw_key.strip()),
            SkillImportApiKey.is_active.is_(True),
        )
        .first()
    )


# --- Import ------------------------------------------------------------------
@dataclass
class ImportResult:
    created: int = 0
    updated: int = 0
    skipped: list[str] = field(default_factory=list)
    skill_names: list[str] = field(default_factory=list)


def _coerce_skills(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """Accept either ``{"skills": [...]}`` or a single ``{"skill": {...}}``."""
    if isinstance(payload.get("skills"), list):
        return [s for s in payload["skills"] if isinstance(s, dict)]
    if isinstance(payload.get("skill"), dict):
        return [payload["skill"]]
    return []


def import_skills(db: Session, payload: dict[str, Any]) -> ImportResult:
    """Create or update skills on the agent named by ``agent_alias``.

    Raises ``ValueError`` with a user-facing message on bad input or unknown
    agent. A skill already present (matched by name) is updated in place and a
    version row is recorded; otherwise it is created.
    """
    alias = str(payload.get("agent_alias") or "").strip()
    if not alias:
        raise ValueError("'agent_alias' is required")

    agent = db.query(Agent).filter(Agent.alias == alias).first()
    if agent is None:
        raise ValueError(f"No agent found with alias '{alias}'")

    skills = _coerce_skills(payload)
    if not skills:
        raise ValueError("Provide at least one skill via 'skills' (list) or 'skill' (object)")

    result = ImportResult()
    existing = {
        s.name: s
        for s in db.query(AgentSkill).filter(AgentSkill.agent_id == agent.id).all()
    }

    for raw in skills:
        name = str(raw.get("name") or "").strip()
        if not name:
            result.skipped.append("(missing name)")
            continue

        description = raw.get("description") or ""
        content = raw.get("content") or ""
        tags = normalize_skill_tags(raw.get("tags"))
        status = str(raw.get("status") or "enabled").strip().lower()
        if status not in VALID_STATUSES:
            status = "enabled"

        current = existing.get(name)
        if current is not None:
            maybe_record_agent_skill_version(
                db,
                agent_id=agent.id,
                skill=current,
                new_name=name,
                new_description=description,
                new_content=content,
                new_status=status,
                new_tags=tags,
            )
            current.description = description
            current.content = content
            current.status = status
            if hasattr(current, "tags"):
                current.tags = tags
            result.updated += 1
        else:
            skill = AgentSkill(
                agent_id=agent.id,
                name=name,
                description=description,
                content=content,
                status=status,
            )
            if hasattr(skill, "tags"):
                skill.tags = tags
            db.add(skill)
            existing[name] = skill
            result.created += 1
        result.skill_names.append(name)

    db.commit()
    return result


def record_log(
    db: Session,
    *,
    api_key_id: int | None,
    agent_alias: str | None,
    created: int,
    updated: int,
    status: str,
    message: str | None,
) -> None:
    db.add(
        SkillImportLog(
            api_key_id=api_key_id,
            agent_alias=agent_alias,
            skills_created=created,
            skills_updated=updated,
            status=status,
            message=message,
        )
    )
    db.commit()


def touch_key(db: Session, key: SkillImportApiKey) -> None:
    key.last_used_at = datetime.now(UTC)
    db.commit()
