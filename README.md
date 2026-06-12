# Hermes Agent Skills — Community Edition

Two community-vetted skills for [Hermes Agent](https://hermes-agent.nousresearch.com/), the self-improving AI agent by Nous Research.

| Skill | Description | Codex Score | Status |
|-------|-------------|:-----------:|:------:|
| **feishu-document-api** | Create, write, and manage Feishu/Lark documents programmatically via the Open API | **8/10** | ✅ Hub-ready |
| **feishu-response-format** | Standardized Feishu/Lark response formatting: message types, pipe tables vs interactive cards, Markdown compatibility, MEDIA attachments, Card JSON 2.0 table component | **8/10** | ✅ Hub-ready |
| **hermes-memory-maintenance** | Maintain MEMORY.md/USER.md: audit redundancy, GATE rules, quality scoring, drift recovery | **9/10** | ✅ Hub-ready |

All skills were audited by Codex (GPT 5.5) source-level review (+ Claude Code review for feishu-response-format) and fixed per findings before submission.

## Installation

```bash
# Install directly from this repo
hermes skills install https://github.com/duruonanni/hermes-skill-kit/tree/main/feishu-document-api
hermes skills install https://github.com/duruonanni/hermes-skill-kit/tree/main/feishu-response-format
hermes skills install https://github.com/duruonanni/hermes-skill-kit/tree/main/hermes-memory-maintenance
```

## Skills

### feishu-document-api

Programmatic Feishu/Lark document creation via the Open API. Covers:
- OAuth 2.0 tenant access token flow
- Block types (text, heading, bullet, code, quote, table)
- Mixed-type batch ordering (consecutive-run pattern)
- Ownership transfer (create → transfer → reveal URL)
- 50-block-per-POST limit handling
- Table creation (block_type 31, max 9 rows)
- In-place document sync (delete-all → rewrite)
- Cron job integration

**Scripts:** `scripts/create_doc.py` (simple), `scripts/create_structured_doc.py` (full workflow)
**References:** 5 docs covering ownership transfer, in-place sync, table discovery, cron patterns, markdown conversion

### feishu-response-format

Standardized Feishu/Lark response formatting. Covers:
- Message type selection guide (`text` / `post` / `interactive` / `MEDIA:`)
- 3 table schemes: pipe tables (🥇 default), interactive cards (Column Set), Card JSON 2.0 Table component (🆕)
- Markdown compatibility matrix (what works and what doesn't on Feishu)
- MEDIA attachment conventions (absolute path rules)
- P0/P1/P2 graded pitfalls ("一表毁所有", Token expiry, security scanner bypass)
- Output checklist for quality assurance
- 53 unit tests for all pure functions

**Scripts:** `templates/send_card.py` — interactive card sender with full type hints, HTTP 429 retry, stdin secret pipe
**Templates:** `templates/reply_templates.md` — multi-step, verification loop, before/after, research summary
**References:** 7 docs covering msg types, API call patterns, Markdown support, pipe table alignment, troubleshooting

### hermes-memory-maintenance

Maintain Hermes agent memory files. Covers:
- §-separated entry format (drift detection & recovery)
- GATE-style hallucination prevention rules
- Memory entry quality scoring (0-4)
- Cross-file redundancy detection (MEMORY.md vs USER.md)
- Capacity planning & growth prediction
- Write discipline & aggregation patterns
- Multi-user section-based structure
- Frozen snapshot architecture
- Concurrent write safety (fcntl flock + atomic write)

**Scripts:** `scripts/memory_review.py` — automated weekly audit
**References:** consolidation examples, drift recovery guide

## Verification

Skills are tested locally and pass:
- `skills_list` discovery ✅
- `skill_view` content loading ✅
- Python syntax validation (all scripts) ✅
- Real execution against local memory files ✅

## License

MIT — feel free to use, modify, and share.
