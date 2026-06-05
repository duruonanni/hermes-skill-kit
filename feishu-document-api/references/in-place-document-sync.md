# In-Place Document Sync (update pattern)

When you need to **periodically overwrite** a Feishu document's content (e.g. a daily backup/status report), you cannot simply append new content — the document accumulates stale blocks. The approach is: **delete all children → add new blocks**.

## API endpoints

| Step | Method | Endpoint |
|------|--------|----------|
| Get child count | `GET` | `/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=500` |
| Delete all children | `DELETE` | `/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete` |
| Add new content | `POST` | `/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children` |

## Python pattern

```python
import json, urllib.request

headers = {'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json; charset=utf-8'}
doc_id = "your-document-id"

# 1. Check how many children the root block has
req = urllib.request.Request(
    f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children?page_size=500',
    headers=headers
)
resp = urllib.request.urlopen(req, timeout=15)
data = json.loads(resp.read().decode())
items = data.get('data', {}).get('items', [])
count = len(items)

# 2. Delete all existing children
if count > 0:
    payload = json.dumps({"start_index": 0, "end_index": count}).encode('utf-8')
    req = urllib.request.Request(
        f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children/batch_delete',
        data=payload, headers=headers, method='DELETE'
    )
    resp = urllib.request.urlopen(req, timeout=15)
    result = json.loads(resp.read().decode())
    if result.get('code') != 0:
        print(f"WARNING: batch_delete returned code {result.get('code')}")

# 3. Add new content in batches of 50 (API limit)
import time

CHUNK_SIZE = 50
all_blocks = [
    {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": "Updated Section"}}]}},
    # ... more blocks
]

for i in range(0, len(all_blocks), CHUNK_SIZE):
    chunk = all_blocks[i:i+CHUNK_SIZE]
    payload = json.dumps({"children": chunk}).encode('utf-8')
    req = urllib.request.Request(
        f'https://open.feishu.cn/open-apis/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
        data=payload, headers=headers, method='POST'
    )
    resp = urllib.request.urlopen(req, timeout=30)
    result = json.loads(resp.read().decode())
    if result.get('code') != 0:
        print(f"ERROR batch {i//CHUNK_SIZE + 1}: {result.get('msg')}")
    time.sleep(0.3)
```

## Document structure: preserving extra sections

If your document includes manually-maintained sections alongside auto-synced content (e.g. evaluation notes, changelog, commentary), **include them in the sync script's `build_children()` function** — otherwise the delete-all step destroys them every run.

Pattern:

```python
def build_children(auto_text_1, auto_text_2):
    children = []
    
    # Auto-synced sections
    children.append(block_h2("File A"))
    children.append(block_code(auto_text_1))
    children.append(block_empty())
    
    children.append(block_h2("File B"))
    children.append(block_code(auto_text_2))
    children.append(block_empty())
    
    # Preserved manual section — hardcoded in the sync script
    children.append(block_h2("Notes"))
    children.append(block_text("These notes survive every sync cycle."))
    
    # Footer with timestamp
    children.append(block_quote(f"Sync time: {now}"))
    return children
```

This ensures that even though the "delete-all → rewrite" approach is destructive, the preserved sections are re-created identically each time.

## Helper function pattern

Instead of inline block dicts, define helper functions at the top of your script for cleaner maintenance:

```python
def block_h2(c):     # heading2, bold
def block_h3(c):     # heading3, bold  
def block_code(c):   # code block (type 14)
def block_quote(c):  # block quote (type 15)
def block_text(c):   # text paragraph (type 2)
def block_bullet(c): # bullet point (type 12)
def block_empty():   # empty spacer
```

See `references/markdown-to-feishu-blocks.md` for full implementations.

## Pitfalls

### ⚠️ batch_delete index is 0-based, exclusive end

### ⚠️ batch_delete index is 0-based, exclusive end
`end_index` is exclusive — to delete all N children, pass `{"start_index": 0, "end_index": N}`. Passing `end_index` equal to the count is correct.

### ⚠️ 50 blocks max per POST when re-adding content
After deleting children, the re-add step must chunk blocks into batches of **at most 50** (the code example above already uses `CHUNK_SIZE = 50`). A batch exceeding 50 returns `code: 99992402` (`field validation failed - the max len is 50`).

### ⚠️ Get child count before delete
Always `GET` the children first to know the count. Don't hardcode — the count changes after each update cycle.

### ⚠️ Token expiry gets fresh token per run
For cron jobs that sync data, always fetch a fresh token at the start of each run. The token expires in ~2 hours, and a daily cron job will certainly be past that window.

## Cron job: no_agent + bash wrapper pattern

The `cronjob` tool's script parameter only accepts a **filename** relative to `~/.hermes/scripts/`, with no argument support for `no_agent=True` scripts.

**Workaround:** Create a thin bash wrapper that calls the real script with args:

`~/.hermes/scripts/sync_runner.sh`:
```bash
#!/usr/bin/env bash
PYTHON="/path/to/python3"
SCRIPT="/path/to/your_real_script.py"
DOC_ID="your-document-id"
exec "$PYTHON" "$SCRIPT" --doc-id "$DOC_ID"
```

Then register the cron job with just the filename:
```python
cronjob(action='create', no_agent=True, script='sync_runner.sh', schedule='0 8 * * *')
```

## Real-world example: memory sync

A complete implementation is available at `~/.hermes/scripts/sync_memory_to_feishu.py`. It reads `~/.hermes/memories/MEMORY.md` and `~/.hermes/memories/USER.md`, deletes old content, writes fresh blocks, and reports the document URL. Run manually:

```bash
python3 ~/.hermes/scripts/sync_memory_to_feishu.py --doc-id YOUR_DOC_ID
```
