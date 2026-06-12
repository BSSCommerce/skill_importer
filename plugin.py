"""Skill Importer plugin.

Exposes a public, X-API-Key-authenticated HTTP endpoint that lets external
systems import Agent **skills** as JSON into an existing agent (identified by
``agent_alias``), plus an admin page to mint and manage those API keys and read
the usage docs.

Two routers:

* ``router``     — admin UI at ``/skill-importer`` (session protected).
* ``api_router`` — public import API at ``/api/skill-import`` (key protected;
  its prefix is registered in ``core.auth.middleware.PUBLIC_PREFIXES``).

Skills are written to the core ``core_agent_skills`` table; the ``tags`` /
version-history fields are owned by the ``agents_admin`` plugin, hence the
dependency.
"""

from __future__ import annotations

from core.plugin_sdk import MenuItem, PluginBase, PluginMeta


class SkillImporterPlugin(PluginBase):
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="skill_importer",
            version="0.1.0",
            description=(
                "Import Agent skills as JSON via a public, X-API-Key-protected "
                "HTTP endpoint, with admin key management."
            ),
            author="community",
            dependencies=["agents_admin"],
        )

    def models(self):
        from skill_importer.models import SkillImportApiKey, SkillImportLog

        return [SkillImportApiKey, SkillImportLog]

    def routers(self):
        from skill_importer.api import router as api_router
        from skill_importer.router import router as admin_router

        return [admin_router, api_router]

    def menu_items(self):
        return [
            MenuItem(
                label="Skill Importer",
                url="/skill-importer",
                icon="upload-cloud",
                order=36,
                key="community_skill_importer",
                parent_key="community",
            ),
        ]
