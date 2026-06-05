# Hermes Agent Skills — Community Edition

Two community-vetted skills for [Hermes Agent](https://hermes-agent.nousresearch.com/), the self-improving AI agent by Nous Research.

| Skill | Description | Codex Score | Status |
|-------|-------------|:-----------:|:------:|
| **feishu-document-api** | Create, write, and manage Feishu/Lark documents programmatically via the Open API | **8/10** | ✅ Hub-ready |
| **hermes-memory-maintenance** | Maintain MEMORY.md/USER.md: audit redundancy, GATE rules, quality scoring, drift recovery | **9/10** | ✅ Hub-ready |

Both skills were audited by Codex (GPT 5.5) source-level review and fixed per its findings before submission.

## Installation

```bash
# Install directly from this repo
hermes skills install https://github.com/duruonanni/hermes-community-skills/tree/main/feishu-document-api
hermes skills install https://github.com/duruonanni/hermes-community-skills/tree/main/hermes-memory-maintenance

# Or use individual skill repos (once created)
hermes skills install https://github.com/<user>/feishu-document-api
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
