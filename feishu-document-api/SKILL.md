---
name: feishu-document-api
description: >
  Create, write, and manage Feishu (Lark) documents programmatically via the Open API. Covers auth, block-type reference, pitfalls, and complete scripts.
version: 2.5.0
license: MIT
platforms: [linux, macos]
compatibility: Hermes Agent (requires FEISHU_APP_ID + FEISHU_APP_SECRET in .env)
required_environment_variables:
  - name: FEISHU_APP_ID
    prompt: Feishu/Lark application App ID from open.feishu.cn
    required_for: creating and modifying documents
  - name: FEISHU_APP_SECRET
    prompt: Feishu/Lark application App Secret
    required_for: creating and modifying documents
metadata:
  hermes:
    tags: [feishu, document, API, lark, productivity]
    related_skills: [hermes-agent, hermes-agent-skill-authoring]
    trigger: manual
---

# Feishu Document API

Use when the user asks to create, write to, or manipulate Feishu documents via the Open API.

Merged from: `productivity/feishu-api` (v1.0.0)

## Prerequisites

The Feishu app must have the `docx:document` permission enabled in [飞书开放平台](https://open.feishu.cn/app) → 权限管理 → 添加 `docx:document`. 添加后需要发布新版本才能生效.

## Workflow

### 1. Get tenant access token

Two equivalent approaches:

**Option A — `http.client`:**
```python
import json, os, http.client

env_path = os.path.expanduser(os.environ.get('HERMES_HOME', '~/.hermes') + '/.env')
def read_env(k):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(k + '='):
                return line.split('=', 1)[1]
    return None

app_id = read_env('FEISHU_APP_ID')
app_secret = read_env('FEISHU_APP_SECRET')

conn = http.client.HTTPSConnection('open.feishu.cn')
tok = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode()
conn.request('POST', '/open-apis/auth/v3/tenant_access_token/internal', tok, {'Content-Type': 'application/json'})
resp = conn.getresponse()
token = json.loads(resp.read().decode()).get('tenant_access_token')
h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
```

**Option B — `urllib.request`** (avoids `http.client` UTF-8 encoding issues):
```python
import json, urllib.request

# Read env vars similarly...
token_data = json.dumps({"app_id": FEISHU_APP_ID, "app_secret": FEISHU_APP_SECRET}).encode()
req = urllib.request.Request(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    data=token_data, headers={'Content-Type': 'application/json'}
)
resp = urllib.request.urlopen(req, timeout=15)
token = json.loads(resp.read().decode()).get('tenant_access_token')
headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
```

### 2. Create document

```
POST /open-apis/docx/v1/documents
Body: {"title": "文档标题"}
```

Returns `document_id` — this is also the root block ID.

### 3. Add content blocks

```
POST /open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children
Body: {"children": [...]}
```

### 4. Transfer document ownership (alternative to adding members)

When `permission.member.create` fails (error codes 917813, 1066001), use ownership transfer instead:

```
POST /open-apis/drive/v1/permissions/{token}/members/transfer_owner?type=docx
Body: {"member_type": "openid", "member_id": "<user_open_id>"}
```

**⚠️ HTTP method:** use **POST** not PATCH — PATCH returns 404.

The document `token` is the same as `document_id`. After transfer, the user becomes the document owner with full access including version history.

**⚠️ Critical timing: always transfer BEFORE exposing the link.** The user has no access during the window between creation and transfer. Follow this sequence:

```
1. Create doc → 2. transfer_owner (POST) → 3. verify success response → 4. send link to user
```

If transfer fails, **delete the document** to avoid orphans:
```
DELETE /open-apis/drive/v1/permissions/{token}?type=docx
```

This is the recommended pattern when direct `permission.member:create` is unavailable — verified working. See `references/ownership-transfer.md` for the full Python workflow.

### 5. Read a document

Read existing Feishu documents — no create/write required, same auth token.

**Option A — Raw content (plain text):**

```
GET /open-apis/docx/v1/documents/{document_id}/raw_content
```

Returns a single `content` field with all text concatenated (headings as `#`, bullets as `-`, etc.). Fast and simple for searching or summarising.

**Option B — Structured blocks (full fidelity):**

```
GET /open-apis/docx/v1/documents/{document_id}/blocks/{document_id}/children?page_size=500
```

Returns typed blocks — you can identify headings (type 3–7), bullets (12), code (14), quotes (15) and extract `text_run` content per block.

Complete Python example for reading:

```python
import json, urllib.request
from urllib.error import HTTPError

headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'}
doc_id = "your-document-id"  # last segment of docx URL

# Option A: raw text
req = urllib.request.Request(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/raw_content',
    headers=headers
)
resp = urllib.request.urlopen(req, timeout=15)
raw = json.loads(resp.read().decode())
print(raw['data']['content'])  # plain markdown-like text

# Option B: structured blocks
req = urllib.request.Request(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=500',
    headers=headers
)
resp = urllib.request.urlopen(req, timeout=15)
blocks = json.loads(resp.read().decode())['data']['items']
for block in blocks:
    text = ''
    for key in ['text','heading1','heading2','heading3','heading4','heading5','bullet','ordered','code','quote']:
        if key in block:
            for el in block[key].get('elements', []):
                if 'text_run' in el:
                    text += el['text_run'].get('content', '')
    if text.strip():
        prefix = '#' if block['block_type'] in range(3,8) else '> ' if block['block_type']==15 else ''
        print(f'{prefix} {text}')
```

**Document ID extraction:** The Feishu docx URL format is `https://{tenant}.feishu.cn/docx/{document_id}`. The last path segment is the document ID.

### Block type reference

| block_type | Key | Element type |
|-----------|-----|-------------|
| 1 | `page` | Root block (document itself) |
| 2 | `text` | Normal paragraph |
| 3 | `heading1` | Heading level 1 |
| 4 | `heading2` | Heading level 2 |
| 5 | `heading3` | Heading level 3 |
| 6 | `heading4` | Heading level 4 |
| 7 | `heading5` | Heading level 5 |
| 12 | `bullet` | Bullet point (unordered list) |
| 13 | `ordered` | Numbered list |
| 14 | `code` | Code block (monospace, works via children API) |
| 15 | `quote` | Block quote |
| 31 | `table` | Table (create skeleton only, no inline cells) |
| 32 | `table_cell` | Cell within a table (auto-created, add children via POST) |

### Element format

Each block needs `elements` array with `text_run` objects:

```python
{
    "block_type": 4,  # heading2
    "heading2": {
        "elements": [{"text_run": {"content": "Section Title"}}]
    }
}
```

Optional `text_element_style` for bold/italic/etc:
```python
{"text_run": {"content": "bold text", "text_element_style": {"bold": True}}}
```

### Sharing URL

Documents can be shared with the URL format:
```
https://bytedance.feishu.cn/docx/{document_id}
```
The `document_id` is returned in the create response. The URL works for any user with access to the app's Feishu tenant.

### 6. Display file content as document blocks

When syncing raw text/markdown files (like MEMORY.md or USER.md) into a Feishu document for readable display, convert the file line-by-line into Feishu blocks:

| Source line | Target block | Notes |
|---|---|---|
| `## Section` | heading2 (type 4) | Strip the `## ` prefix |
| `### Subsection` | heading3 (type 5) | Strip the `### ` prefix |
| `- item` | bullet (type 12) | Strip the `- ` prefix |
| `---` | text (type 2) with `─────` | Dividers (type 16) not creatable via API |
| `**bold text:** rest` | text (type 2) | Strip `**` markers, use `text_element_style: {bold: true}` if needed |
| `\| key \| val \|` | bullet (type 12) as `key: val` | Parse table rows into key-value bullets |
| Raw file content/MEMORY.md/etc. | code block (type 14) | block_code(file_text) — monospace, full file dump |

**Key rules:**
- **Always show full content, never summaries** — users want the raw file visible in the doc, not a "syncs automatically" placeholder
- **Write in order** — delete all existing blocks, then write MEMORY.md content first, then USER.md content. Block order = document order
- **Clean markdown artifacts** — strip `**`, ``` `` ```, and other markdown syntax before writing as Feishu text_run
- **Handle table rows** — skip header and separator lines, parse data rows as `bullet("key: value")`

See `references/markdown-to-feishu-blocks.md` for the complete Python conversion function and error handling.

When you need to **periodically overwrite** a document's content (daily/weekly sync), append new blocks won't work — they accumulate stale content. Instead:

1. `GET` the root block's children to get a count
2. `DELETE /open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete` with `{"start_index": 0, "end_index": N}`
3. `POST` new blocks as normal

See `references/in-place-document-sync.md` for the full pattern, Python code, pitfalls, and the **cron no_agent + bash wrapper pattern** for script parameters.

### Codex (GPT 5.5) audit & fixes

This skill was evaluated by Codex (GPT 5.5 source-level audit) on 2026-06-05 and re-evaluated on 2026-06-11. Key findings and their fixes:

| # | Finding | Fix applied | Scope |
|---|---------|-------------|-------|
| 1 | **Mixed block types in single POST** (`create_doc.py`) | All blocks converted to type-2 text blocks (no mixed batch error 1770001) | `create_doc.py` |
| 2 | **Heading blocks at doc root** (`create_doc.py`) | Bold text blocks replace heading2 — heading blocks (types 3-7) fail at root | `create_doc.py` |
| 3 | **False "success" on API error** (`create_structured_doc.py`) | Track actual success count; `write_blocks_in_order` returns `(total_written, errors)` tuple | `create_structured_doc.py` |
| 4 | **URL printed before ownership transfer** (both scripts) | `create_structured_doc.py`: print URL **after** transfer success or not at all. `create_doc.py`: no transfer needed (app-owned) | Both scripts |
| 5 | **Transfer failure leaves orphan doc** (`create_structured_doc.py`) | DELETE doc on transfer failure; print manual cleanup hint if DELETE also fails | `create_structured_doc.py` |
| 6 | **Hardcoded `.env` path** | `HERMES_HOME` env var with `~/.hermes` fallback | Both scripts |
| 7 | **Hardcoded `bytedance.feishu.cn`** | Configurable `TENANT` parameter (3rd CL argument), default `bytedance` | Both scripts |
| 8 | **No auth response validation** (`create_doc.py:53`) | `.get('tenant_access_token')` returns None silently on API failure → proceeds with `Bearer None` and 401. Still unfixed — needs `code == 0` check before proceeding. | `create_doc.py` |
| 9 | **No create-doc response validation** (`create_doc.py:67`) | `['data']['document']` crashes on API error with KeyError. Still unfixed — needs `code == 0` check before indexing. | `create_doc.py` |
| 10 | **Auth token not validated** (`create_structured_doc.py:60`) | `['tenant_access_token']` raises KeyError on auth failure (partial — HTTPError caught, KeyError not). Still unfixed — add KeyError to exception or use `.get()`. | `create_structured_doc.py` |

Re-audit verdict (2026-06-11): Both scripts FAIL due to items 8–10. These are pre-existing issues missed by the first audit, not regressions from the v2 fixes.

**Lesson for Skill authoring:** Every script that writes a URL should follow the **verify-then-reveal** principle: create → write → transfer → *verify* → reveal URL. A URL leaked before the user has access is a permission leak, even if the recipient is trusted. Scripts must handle failure at every step and clean up side effects.

### Complete working scripts & references

Seven resources are available:

- `references/feishu-docx-create-write.md` — copy and modify as needed (original create workflow)
- `references/in-place-document-sync.md` — batch-delete update pattern, cron wrapper, real-world memory sync example
- `references/table-block-discovery.md` — empirical discovery log for Feishu tables (block_type 31/32): what didn't work and why, cell layout indexing, PATCH pitfall detail
- `references/cron-append-pattern.md` — append blocks from cron context (where `execute_code` is blocked): write a script file, run via `terminal()`, read block count for index positioning. Verified working with `daily-tips-summary` cron job.
- `scripts/create_doc.py` — **Fixed v2.** Basic workflow: authenticate, create doc, write blocks (all type-2, no more heading-at-root), print URL. Uses `$HERMES_HOME/.env`, configurable tenant.
- `scripts/create_structured_doc.py` — **Fixed v2.** Enhanced version with correct batch ordering (consecutive same-type runs), ownership transfer with **verify-then-reveal** URL safety, orphan cleanup on transfer failure, real success counting (no false ✅), `$HERMES_HOME/.env`, and configurable tenant domain. Run: `python3 ~/.hermes/skills/feishu/feishu-document-api/scripts/create_structured_doc.py "标题" [open_id] [tenant]`

### Generating PDFs (HTML → PDF)

For generating PDFs (e.g. from HTML guides), see the **`html-to-pdf` skill** — covers WeasyPrint installation, CJK font setup, and pitfalls.

## Pitfalls

### ⚠️ Feishu Rich Text ≠ Markdown Tables
When creating or delivering content to Feishu conversations (via the gateway), be aware that Feishu's `post` rich text format does **not** support Markdown tables. The gateway's `_build_outbound_payload()` method detects markdown tables via `_MARKDOWN_TABLE_RE` and **falls back to plain `text` mode** — the table renders as raw Markdown syntax.

**User preference:** They want ALL messages delivered as rich text (`post` format). When you need to present tabular/comparison data, use indented lists or key-value pairs instead of `| ... |` Markdown tables:

```
Good (rich text works):
  Item A → value 1
  Item B → value 2

Bad (triggers text fallback):
  | Item | Value |
  |------|-------|
  | A    | 1     |
```

This applies to both Feishu documents (where block-based APIs support tables) and conversational messages (where the gateway handles the conversion). For documents the native block API supports tables — the pitfall is specifically for **messages** sent through the gateway.
Chinese characters in body MUST be encoded as UTF-8 bytes. `http.client` defaults to latin-1:

```python
body_bytes = json.dumps(body, ensure_ascii=False).encode('utf-8')
conn.request('POST', url, body_bytes, h)  # NOT the dict
```

### ⚠️ 50 blocks max per POST request
The API enforces a hard limit of **50 blocks per POST** to `/blocks/{id}/children`. Exceeding it returns `code: 99992402` with `field validation failed — the max len is 50`. Always chunk block arrays into batches:

```python
CHUNK_SIZE = 50
for i in range(0, len(all_blocks), CHUNK_SIZE):
    chunk = all_blocks[i:i+CHUNK_SIZE]
    payload = json.dumps({"children": chunk}).encode('utf-8')
    # POST each chunk separately
```

For in-place sync (delete-all → rewrite), count total blocks before deleting. 111 blocks → 3 batches of 50+50+11.

### ⚠️ Too deep nesting (code 1770005)
Inserting blocks as children of a newly-inserted block creates nested hierarchy. When the nesting depth exceeds ~30 levels, the API returns `code: 1770005, msg: "too deep level in document"`.

**Fix:** Use the SAME parent for all sibling inserts, shifting `index` to control position:

```python
# RIGHT — same parent, all siblings
current_idx = anchor_idx
for block in blocks:
    body = json.dumps({"children": [block], "index": current_idx}).encode()
    post_into(DOC_ID, body)  # always at doc root level
    current_idx += 1
```

**Rule of thumb:** Only nest when you intentionally want sub-blocks (e.g. text under a heading). For appending a flat list of blocks, always insert into the document root (`DOC_ID`) with an incrementing `index`.

### ⚠️ Never insert test blocks into a production doc
When debugging Feishu API calls (testing batch limits, block types, parent restrictions), **do NOT insert test blocks into a shared/production document**. The user sees the garbage before you clean it up — and it disrupts their workflow.

**Do this instead:**
1. Create a throwaway test doc: `POST /open-apis/docx/v1/documents` with title "TEST - delete me"
2. Run all debugging probes against the test doc
3. Delete the test doc when done: `DELETE /open-apis/drive/v1/permissions/{token}?type=docx`

**If you accidentally inserted test blocks into a production doc**, immediately use `batch_delete` to remove them from the parent block:

```python
# Get child count, then delete all
items = children_of(parent_block_id, headers)["data"]["items"]
count = len(items)
body = json.dumps({"start_index": 0, "end_index": count}).encode()
del_url = f"https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{parent_block_id}/children/batch_delete"
urllib.request.Request(del_url, data=body, headers=h, method="DELETE")
```

### ⚠️ Cannot mix block types in a single batch
The API **rejects** batches containing mixed block types with `code: 1770001, msg: "invalid param"`. All blocks in one POST must be the **same** `block_type`:

```python
# WORKS: all type 2
safe = [{"block_type":2,"text":{"elements":[{"text_run":{"content":"A"}}]}},
        {"block_type":2,"text":{"elements":[{"text_run":{"content":"B"}}]}}]

# FAILS (1770001): mixed types
bad = [{"block_type":2,"text":{"elements":[{"text_run":{"content":"A"}}]}},
       {"block_type":3,"heading3":{"elements":[{"text_run":{"content":"B"}}]}}]
```

**⚠️ WRONG approach (scrambles document order):** Do NOT group all blocks by type and then insert `sorted(by_type.keys())` — this inserts ALL type-2 blocks first, then ALL type-12 blocks, completely destroying the document's intended sequence. The `index` parameter controls position at insertion time, but inserting in type-grouped order means bullets end up after all text blocks regardless of their intended position.

**✅ CORRECT workaround — consecutive runs:** Process blocks in their original sequence, collect consecutive blocks of the same type into a run, then insert each run at the running position:

```python
i = 0
pos = 0  # running insertion index at the document root
while i < len(all_blocks):
    bt = all_blocks[i]["block_type"]
    run = []
    while i < len(all_blocks) and all_blocks[i]["block_type"] == bt:
        run.append(all_blocks[i])
        i += 1
    # Batch in chunks of 40 (API limit)
    for chunk_start in range(0, len(run), 40):
        chunk = run[chunk_start:chunk_start+40]
        r = api('POST', f'/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
                {"children": chunk, "index": pos})
        if r.get('code') != 0:
            print(f"WARN: type={bt} at pos={pos} → {r.get('code')}: {r.get('msg','')[:80]}")
        pos += len(chunk)
    time.sleep(0.2)  # small delay between batches avoids rate limits
```

### ⚠️ Doc root does NOT accept heading blocks via API
When inserting at the document root (`DOC_ID` as parent), only **text blocks (type 2)** succeed. Heading blocks (types 3-7) inserted directly under `DOC_ID` return `code: 1770001`.

This is a **runtime restriction** — heading blocks CAN exist at root level (created via the Feishu editor), they just can't be inserted there via API.

**Workaround:** Insert everything as type-2 text blocks with formatting indicators in the content (e.g., `【Heading】` or `**bold**`), or insert heading blocks as children of an existing heading block rather than the doc root.

### ⚠️ Empty text blocks are rejected
Blocks with an **empty `elements` array** return `code: 1770001`. Every text/heading block must have at least one element with non-empty content:

```python
# FAILS: empty elements
{"block_type":2,"text":{"elements":[]}}

# WORKS: use a single space
{"block_type":2,"text":{"elements":[{"text_run":{"content":" "}}]}}
```

### ⚠️ Markdown tables render as raw pipe text in Feishu documents
When you insert content like `| Col1 | Col2 | Col3 |` as a type=2 (text) block, Feishu renders the pipe characters **literally** — it does NOT auto-convert Markdown table syntax to native Feishu table blocks.

```python
# BAD — shows as raw text: | A | B | C |
{"block_type":2,"text":{"elements":[{"text_run":{"content":"| A | B | C |"}}]}}
```

**Solutions:**

**A — Restructure as formatted text (recommended for simple data):**
Use indentation + bold labels or arrow format:
```
  Label A: value of A
  Label B: value of B
  Item → Description
```

**B — Native Feishu table (block_type=31):**
For multi-column comparison data in Feishu **documents**, use native Feishu tables. See the **[Tables](#tables-飞书文档表格)** section under Document formatting standards for the complete workflow and helper code.

### ⚠️ All-text fallback pattern (when headings fail in batch)
When batch-inserting at the **document root** (DOC_ID as parent), only type=2 text blocks work reliably. Heading blocks (types 3-7) return 1770001 in batch mode.

**Reliable workaround:** Convert ALL content to type=2 text blocks using formatting conventions:

```python
# Instead of heading3 — use bold text
{"block_type":2,"text":{"elements":[{"text_run":{"content":"Section Title","text_element_style":{"bold":true}}}]}}

# Instead of heading4 — use bold subsection markers
{"block_type":2,"text":{"elements":[{"text_run":{"content":"Phase 1 - Subtitle","text_element_style":{"bold":true}}}]}}

# Instead of bullet lists — use indented text
{"block_type":2,"text":{"elements":[{"text_run":{"content":"  ■ Item with detail"}}]}}

# Instead of pipe tables — use formatted label:value rows
{"block_type":2,"text":{"elements":[
    {"text_run":{"content":"P0-1","text_element_style":{"bold":true}}},
    {"text_run":{"content":": Delete file | 30s"}}
]}}
```

This has been verified to work for batches of up to 50 blocks at the document root level.

### ⚠️ Square brackets `[...]` inside content strings cause Python syntax errors
When constructing block dicts inline in Python scripts, **square brackets inside content strings** (`[user:duro]`, `[key:value]`) can confuse the parser into thinking the `]` closes an outer data-structure bracket, producing `SyntaxError: closing parenthesis ']' does not match opening parenthesis '{'`.

**Fix:** Replace bracket-containing tokens parent-friendly alternatives:
```python
# Bad — triggers SyntaxError
"user:duro / user:raya / global 三段隔离"

# Good
"user:duro / user:raya / global 三段隔离"
```
Or construct block dicts programmatically via helper functions rather than inline literals — the issue only affects file-based inline dicts, not runtime-constructed data.

### ⚠️ Batch delete end_index is exclusive, min value = 1

The `end_index` parameter in `batch_delete` is an **exclusive upper bound** with a minimum value of 1. Unlike Python slicing habits (`end_index = len(block_ids) - 1`), Feishu's API requires `end_index = len(block_ids)`.

```python
# WRONG — Python habit: end_index = len(block_ids) - 1
{"start_index": 0, "end_index": len(block_ids) - 1}
# When block_ids has 1 item, end_index=0 → code 99992402 (min is 1)

# RIGHT — Feishu exclusive: end_index = len(block_ids)
{"start_index": 0, "end_index": len(block_ids)}
# 1 block → end_index=1, deletes block at index 0
```

Tested: `{"start_index": 0, "end_index": 1}` on a document with 1 child → returns `code: 0, success`.

### ⚠️ Block type number MUST match the key name

Each block type's `block_type` number and its corresponding key in the block dict must match. Mismatch returns `code: 1770001, msg: invalid param`.

| block_type | Correct key | Wrong key example |
|------------|-------------|-------------------|
| 3 | `heading1` | `heading2` (type 3 is heading1) |
| 4 | `heading2` | `heading3` (type 4 is heading2) |
| 5 | `heading3` | `heading4` (type 5 is heading3) |
| 6 | `heading4` | any other key |

This is easy to get wrong because it's intuitive to think heading2 = block_type 2, but Feishu starts at type 3 for heading1. Always cross-reference with the block type table above.

### ⚠️ Code blocks: type 14 works, type 17 doesn't via children API

**block_type 17** (code block with language syntax highlighting) returns `code: 1770001, msg: "invalid param"` when created via `POST /children`.

**block_type 14** (code block, inline code style) **DOES work** via the children API. Use:

```python
{
    "block_type": 14,
    "code": {
        "elements": [{"text_run": {"content": "full code or file content"}}]
    }
}
```

Type 14 renders as a monospace-style block in the Feishu document — suitable for displaying raw file content like MEMORY.md, log dumps, or config files.

**Rule of thumb:**
- Displaying raw file content → **block_type 14** (works via children API, monospace)
- Only fall back to type 2 (text blocks) for structured display with headings/bullets
- Type 17 can only be created by updating an existing code block via `PATCH /blocks/{block_id}`

See `references/markdown-to-feishu-blocks.md` for the full conversion pattern.

### ⚠️ Block type 16 (divider) not supported
Divider blocks (block_type=16) cannot be added via the children POST API — they can only exist in documents created through the UI. Skip them.

### ⚠️ Permission 99991672 — Missing document scope
If API returns `code: 99991672` with "docx:document scope required":
→ Go to 飞书开放平台 → 应用 → 权限管理 → 添加 `docx:document` → 发布新版本
→ Wait ~5 min for the new permission to take effect.

### ⚠️ Sharing documents (adding members) requires additional scopes
Creating docs only needs `docx:document`. **Sharing** docs with other users needs:
`docs:permission.member:create` or `drive:drive` (umbrella scope).

Adding members via POST `/open-apis/drive/v1/permissions/{token}/members?type=docx`:
```python
body = json.dumps({
    "member_type": "openid",
    "member_id": user_open_id,
    "role": "editor"   # or "viewer", "full_access"
}).encode()
r = urllib.request.Request(url, data=body, headers=h, method="POST")
```

**Error 1066001 (Internal Error)** on POST means scope was added but NOT published, OR the API itself fails even after publishing for some endpoints:
1. Go to 飞书开放平台 → 应用 → 权限管理 → add `docs:permission.member:create`
2. Go to 版本管理与发布 → 创建新版本 → publish
3. Wait 2-5 min after publish, then retry
Adding scopes without publishing has no effect — the API returns 1066001.

**Error 917813 (`permission.to.create member`)** — even after publishing, this error means the API endpoint for member creation is not available. The working workaround is **ownership transfer** (see section 4 above): transfer the document to the user's open_id instead of adding them as a member. The user becomes the owner and can manually add other collaborators in the UI.

### ⚠️ Proactive document suggestion pattern (聊天主动建议文档)
When chatting with users in Feishu, if the conversation involves **multi-step tasks (≥3 steps), cross-session tracking, or multi-person collaboration**, suggest creating a Feishu document. Do NOT immediately edit MEMORY.md — first evaluate if this is a Skill-worthy workflow. The document should be owned by the person you're chatting with:

```
User confirms → Create doc → transfer_owner (to user's open_id) → verify success → send link
User refuses → Don't suggest again this session
Transfer fails → Delete doc, tell user
```

See `references/ownership-transfer.md` for implementation.

### ⚠️ Built-in feishu_drive_* tools may fail — use Open API as fallback
Hermes provides built-in tools (`feishu_doc_read`, `feishu_drive_add_comment`, `feishu_drive_reply_comment`, etc.) that wrap the Feishu Open API. These tools depend on the gateway's Feishu platform context being fully initialized at startup. If the gateway was restarted recently or the Feishu doc client didn't load, these tools return `"Feishu client not available (not in a Feishu comment context)"`.

**This is not a credential/permission issue** — the credentials (`FEISHU_APP_ID`, `FEISHU_APP_SECRET`) are valid and the scopes are correct. The problem is the gateway-side client object not being instantiated.

**Workaround:** Use the Feishu Open API directly via `terminal`/`execute_code` instead of the built-in tools. The Open API always works as long as credentials are present:

```python
import json, urllib.request, os

# Read credentials from .env
env = {}
with open(os.path.expanduser(os.environ.get('HERMES_HOME', '~/.hermes') + '/.env')) as f:
    for line in f:
        line = line.strip()
        if '=' in line and not line.startswith('#'):
            k, v = line.split('=', 1)
            env[k] = v

cred = env.get('FEISHU_APP_SECRET', '')
tok_data = json.dumps({'app_id': env.get('FEISHU_APP_ID', ''), 'app_secret': cred}).encode()
req = urllib.request.Request(
    'https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal',
    data=tok_data, headers={'Content-Type': 'application/json'})
resp = urllib.request.urlopen(req, timeout=15)
token = json.loads(resp.read().decode())['tenant_access_token']
h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

# Read document raw content
doc_id = 'your-document-id-here'
req = urllib.request.Request(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/raw_content', headers=h)
resp = urllib.request.urlopen(req, timeout=15)
content = json.loads(resp.read().decode())['data']['content']

# Append blocks at a specific index
blocks = [{"block_type": 2, "text": {"elements": [{"text_run": {"content": "new text"}}]}}]
payload = json.dumps({"children": blocks, "index": 60}).encode('utf-8')
req = urllib.request.Request(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
    data=payload, headers=h, method='POST')
resp = urllib.request.urlopen(req, timeout=15)

# Add a whole-document comment
comment = json.dumps({"content": "{\"text\":\"comment text\"}"}).encode('utf-8')
req = urllib.request.Request(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/comments',
    data=comment, headers=h, method='POST')
resp = urllib.request.urlopen(req, timeout=15)
```

When using the Open API directly, remember:
- Always fetch a fresh token (2h expiry) — do not cache across turns
- Inserting at doc root: heading blocks (types 3-7) return 1770001 — use type 2 text with bold instead
- Group blocks by type to avoid the mixed-type batch restriction (code 1770001)
- The last segment of the Feishu URL `https://{tenant}.feishu.cn/docx/{document_id}` is the doc_id

### ⚠️ Token expiry
Tenant access token expires in ~2 hours. For scripts, always fetch a fresh token.

## Document formatting standards (飞书文档格式规范)

When creating user-facing Feishu documents (guides, handbooks, reference docs), follow these formatting conventions:

### Section headers
Since heading blocks (types 3-7) **cannot be inserted at document root via API**, use bold type-2 text blocks as section headers:

```python
{"block_type": 2, "text": {"elements": [{"text_run": {"content": "一、Section Title", "text_element_style": {"bold": True}}}]}}
```

### Nested structure for subsections
Use bold text with `▎` prefix for sub-category labels within a section:

```python
{"block_type": 2, "text": {"elements": [{"text_run": {"content": "▎Subcategory Label", "text_element_style": {"bold": True}}}]}}
```

### Paragraphs
Plain type-2 text blocks for body text. Insert empty text blocks (`" "` as content) for spacing between sections.

### Bullet lists
Use type-12 blocks for list items. Each list entry should be a separate bullet block - do NOT cram multiple items into one block.

### Achievement/entry format (reference-style documents)
For documents listing items with names, descriptions, and metrics, use this 3-bullet pattern per entry:

**⚠️ Separator rule: use spaces ONLY throughout.** Do NOT mix spaces, underscores, or other separators — mixed separators make it impossible to Ctrl+F search in the document. Everything uses spaces consistently.

```python
# Entry name line (bold effect via content) — spaces between parts
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "Achievement Name 标签（Category Label）"}}]}}
# Description line (indented with 2 spaces, NO emoji prefix duplication)
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "  Brief description of what this does"}}]}}
# Metadata line (tiers, thresholds, links) — use → arrows for progression, | for separators
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "  Level: Copper → Silver → Gold → Diamond → Olympian  |  Threshold: 100 / 300 / 1K / 3K / 8K"}}]}}
```

### Secret achievement format (标🔒的成就)
Secret achievements use a `🔒` prefix on the **name line only**. DO NOT repeat `🔒` on the description or metadata lines — duplication makes the document look messy.

```python
# CORRECT: 🔒 only on name line
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "🔒 Secret Achievement 🔌（Category Label）"}}]}}
# Description line — NO 🔒 prefix
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "  Description without lock emoji"}}]}}
# Metadata — NO 🔒 prefix
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "  Level: Copper → Silver → Gold → Diamond → Olympian  |  Threshold: 100 / 300 / 1K"}}]}}
```

### Unlocked achievements list format (已解锁成就)
When listing achievements a user has already unlocked, use this format:

```python
# Tier header — bold label with ★ prefix
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": "★ Silver", "text_element_style": {"bold": True}}}]}}
# Unlocked entry — exactly 1 space before emoji, NO trailing spaces
{"block_type": 12, "bullet": {"elements": [{"text_run": {"content": " 🏔️ ✓ achievement name with spaces"}}]}}
```

**Rules:**
- EXACTLY 1 space before the emoji/icon (not 0, not 2)
- EXACTLY 1 space between emoji and ✓
- EXACTLY 1 space between ✓ and the name
- Spaces between words in achievement names (NOT underscores)
- NO trailing spaces after the name
- NO parenthetical extras after the name (keep it clean)

### General indentation rules
- **Section headers**: bold type-2 text blocks, no indent
- **Category labels** (▎ prefixed): bold type-2 text blocks, no indent
- **Sub-items / descriptions**: type-12 bullet blocks, 2-space indent for the content text
- **Body text**: type-2 text blocks, no indent
- **Empty spacers**: type-2 text blocks with content `" "` (single space) for visual spacing
- **NO trailing whitespace** on any block's text content

### Batch insertion order (CRITICAL)
Always process blocks in their **original sequence** using the consecutive-run pattern (see above). Do NOT reorder blocks by type.

### Verification

After writing, always verify formatting quality — not just that content exists, but that it looks clean.

**Content check — read raw content:**
```python
r = api('GET', f'/docx/v1/documents/{doc_id}/raw_content')
content = r['data']['content']
# Check ordering — all text blocks first means wrong batching
if '等级：Copper' in content and content.index('等级：') == 0:
    print('⚠️ All metadata blocks at top — batching order is wrong')
```

**Formatting checklist (run these checks on the raw content):**
```python
issues = []
for line in content.split('\n'):
    stripped = line.rstrip()
    # Trailing whitespace (except intentional spacer lines)
    if line != stripped and stripped:
        issues.append(f'Trailing whitespace: {repr(line[:50])}')
    # Underscores in user-facing text (not code refs like delegate_task)
    if '_' in stripped and 'delegate_task' not in stripped:
        issues.append(f'Underscore found: {repr(stripped[:50])}')

# 🔒 duplication in descriptions
import re
if re.search(r'^\s{2,}🔒', content, re.MULTILINE):
    issues.append('🔒 duplicated on description lines — should only be on name line')

# Double-space indent on unlocked achievements
if '  🔨' in content:
    issues.append('Double-space indent found — should be single space')

if issues:
    print(f'❌ {len(issues)} formatting issues:')
    for i in issues[:10]:
        print(f'  {i}')
else:
    print('✅ All formatting checks passed')
```

If order is wrong (all text blocks first, then all bullets), you used the wrong batching approach — re-examine the consecutive-run pattern.

### Tables (飞书文档表格)

Feishu documents support native tables via `block_type=31`. Unlike Feishu chat messages (which cannot render tables), documents CAN render them properly.

**When to use tables:** When information has 3+ items with 2+ columns of structured data (comparison data, status lists, tier definitions). For simple key-value pairs, use formatted text instead.

**How it works — two-step process:**

1. **Create the table skeleton** (no cell content) — POST to document root
2. **Add content to each cell** — POST text blocks as children of each cell block

The API automatically creates empty cells — you don't specify cell content inline.

```python
def create_table(doc_id, headers, rows, col_widths=None):
    """
    Create a native Feishu table and populate it with content.
    
    Args:
        doc_id: Feishu document ID
        headers: list of column header strings
        rows: list of lists, each inner list is a row of cell values
        col_widths: optional list of column widths in px (default: 200 each)
    
    Returns: (table_block_id, cell_block_ids) or raises on failure
    """
    import json, urllib.request
    from urllib.error import HTTPError
    
    BASE = 'https://open.feishu.cn'
    # Assume `api(method, path, data)` helper is available
    # (returns parsed JSON response)
    
    n_cols = len(headers)
    n_rows = len(rows) + 1  # +1 for header row
    widths = col_widths or [200] * n_cols
    
    # Step 1: Create table skeleton (no cells in body)
    skeleton = {
        "children": [{
            "block_type": 31,
            "table": {
                "property": {
                    "row_size": n_rows,
                    "column_size": n_cols,
                    "column_width": widths
                }
            }
        }]
    }
    r = api('POST', f'/docx/v1/documents/{doc_id}/blocks/{doc_id}/children', skeleton)
    table_block = r['data']['children'][0]
    table_id = table_block['block_id']
    cell_ids = table_block['table']['cells']  # flat array, row-by-row
    
    # Step 2: Populate cells
    all_content = [headers] + rows
    for idx, content in enumerate(all_content):
        for col, text in enumerate(content):
            cell_id = cell_ids[idx * n_cols + col]
            cell_payload = {
                "children": [{
                    "block_type": 2,
                    "text": {
                        "elements": [{"text_run": {"content": str(text)}}]
                    }
                }]
            }
            api('POST', f'/docx/v1/documents/{doc_id}/blocks/{cell_id}/children', cell_payload)
    
    return table_id, cell_ids

# Usage example:
headers = ["Name", "Status", "Score"]
rows = [
    ["Alice", "Active", "95"],
    ["Bob", "Pending", "82"],
    ["Charlie", "Active", "88"],
]
create_table(doc_id, headers, rows, col_widths=[200, 150, 100])
```

**⚠️ Cell behavior notes:**
- Cells are `block_type=32` (table_cell) — they are NOT text blocks
- When a table is created, each cell gets ONE empty child block (type 2, text)
- Adding children to a cell via POST appends alongside the empty child — this is fine for display
- Cell content updates use `POST /blocks/{cell_id}/children`, NOT PATCH (which returns code 1770025)
- Cells are returned as a flat array in the response, ordered row-by-row: `cells[0..n-1]` = row 0, `cells[n..2n-1]` = row 1, etc.
- Each cell can contain multiple blocks (use POST children multiple times)
- Bold/formatting: add `text_element_style` to the text_run as normal

### ⚠️ Table row limit: max 9 rows (via API)
The Feishu API rejects table creation with 10+ rows (including the header row). Returns `code: 1770001, msg: invalid param`.

```python
# FAILS: 10+ rows
{'row_size': 10, 'column_size': 2}  # ❌ code 1770001

# WORKS: max 9 rows (1 header + 8 data rows)
{'row_size': 9, 'column_size': 2}   # ✅
```

**Workaround:** Split large tables into multiple small tables, each ≤9 rows:

```python
# Split 11-row CLI commands into 2 tables
table1_rows = 9  # header + 8 commands
table2_rows = 4  # header + 3 remaining commands
```

Verified: 9 rows succeeds, 10 rows fails. Applies to table creation only (the document UI can create larger tables).

### ⚠️ POST without `index` parameter for table blocks
When appending tables to a document, do NOT use the `index` parameter — it can cause HTTP 400 errors. Tables append fine without it.

```python
# WORKS
api('POST', '/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
    {'children': [table_block]})  # no index

# MAY FAIL
api('POST', '/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
    {'children': [table_block], 'index': pos})  # HTTP 400
```

### Prioritization rule: tables first
When creating reference-style documents, follow this priority:
1. **Multi-column structured data (≥3 items, ≥2 columns)** → native Feishu table (block_type=31)
2. **Simple key-value pairs (1-2 items)** → formatted text label:value rows
3. **Feishu chat messages** → indented lists (tables not supported in rich text)

**Implementation flow:**
1. Evaluate content: does it have 3+ items with 2+ columns of structured data?
2. If yes → build a `create_table()` skeleton, populate cells
3. If no → use formatted text with labels

### When NOT to use tables:
- Simple key-value pairs (use formatted text label:value rows instead)
- 1-2 items with 1-2 columns (use formatted text instead)
- Feishu chat messages (tables aren't supported in rich text — use indented lists)
