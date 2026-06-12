# Skill Importer

Import Agent **skills** as JSON into an existing agent through a public,
`X-API-Key`-protected HTTP endpoint. Includes an admin page to mint and manage
keys and read the usage docs.

## What it adds

| Surface | Path | Auth |
|---------|------|------|
| Admin UI (key management + docs) | `GET /skill-importer` | Session cookie |
| Import endpoint | `POST /api/skill-import/skills` | `X-API-Key` header |

Skills are written into the core `core_agent_skills` table (the same skills the
`agents_admin` UI shows). Plugin-owned tables use the `plugin_skillimp_` prefix:

- `plugin_skillimp_api_keys` — hashed keys (SHA-256 + short display prefix; the
  raw key is shown only once at creation).
- `plugin_skillimp_logs` — audit trail of import calls.

## Creating a key

1. Open **Skill Importer** in the sidebar (`/skill-importer`).
2. Enter a key name and click **Create key**.
3. Copy the key shown in the green banner — it is displayed only once.

## Importing skills

```bash
curl -X POST https://<host>/api/skill-import/skills \
  -H "X-API-Key: <your-key>" \
  -H "Content-Type: application/json" \
  -d '{
    "agent_alias": "support-bot",
    "skills": [
      {
        "name": "Refund policy",
        "description": "How to handle refund requests",
        "content": "# Refunds\n...markdown body...",
        "tags": "support,billing",
        "status": "enabled"
      }
    ]
  }'
```

A single skill may be sent as `{"agent_alias": ..., "skill": { ... }}`.

### Body fields

| Field | Required | Notes |
|-------|----------|-------|
| `agent_alias` | yes | Alias of the target agent (must already exist). |
| `skills[].name` | yes | Match key — existing skill is **updated** (with version history), otherwise **created**. |
| `skills[].description` | no | Short summary. |
| `skills[].content` | no | Markdown body. |
| `skills[].tags` | no | Comma-separated tags. |
| `skills[].status` | no | `enabled` (default) or `disabled`. |

### Responses

- `200` — `{ "ok": true, "agent_alias": ..., "created": n, "updated": m, "skipped": [...], "skills": [...] }`
- `400` — bad JSON, missing `agent_alias`, unknown agent, or no skills.
- `401` — missing/invalid/revoked `X-API-Key`.

## Notes

- The import prefix `/api/skill-import/` is registered in
  `core.auth.middleware.PUBLIC_PREFIXES` so it bypasses the session-cookie gate;
  authentication is enforced by the key check in the endpoint.
- Depends on the `agents_admin` plugin, which owns the skill `tags` /
  version-history columns on `core_agent_skills`.
