"""ORM models for the Skill Importer plugin.

Two self-contained tables (``plugin_skillimp_*`` prefix so they never collide
with core tables):

* ``SkillImportApiKey`` — hashed X-API-Key credentials that authenticate the
  public import endpoint. Only the SHA-256 hash and a short display prefix are
  stored; the raw key is shown once at creation time and never persisted.
* ``SkillImportLog`` — one row per import call for a lightweight audit trail
  (which key, which agent alias, how many skills created/updated, outcome).
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from core.database.base import Base


def _utcnow() -> datetime:
    return datetime.now(UTC)


class SkillImportApiKey(Base):
    """An X-API-Key credential for the skill import endpoint."""

    __tablename__ = "plugin_skillimp_api_keys"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    key_prefix: Mapped[str] = mapped_column(String(16), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by_user_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


class SkillImportLog(Base):
    """Audit row written after each import attempt."""

    __tablename__ = "plugin_skillimp_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    api_key_id: Mapped[int | None] = mapped_column(
        Integer,
        ForeignKey("plugin_skillimp_api_keys.id", ondelete="SET NULL"),
        nullable=True,
    )
    agent_alias: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    skills_created: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    skills_updated: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ok")
    message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
