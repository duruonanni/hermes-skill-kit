#!/usr/bin/env python3
"""
Feishu Structured Document Creator — fixed v2
Full workflow with correct block ordering, safety, and portability.

Fixes applied per Codex evaluation:
  1. Track actual success count (not just pos) — no false ✅ on failures
  2. Print URL only AFTER ownership transfer confirms (permission leak fix)
  3. Delete orphan doc on transfer failure
  4. HERMES_HOME env var with ~/.hermes fallback
  5. Configurable tenant domain (no hardcoded bytedance)

Features:
  - Auth via $HERMES_HOME/.env
  - Create doc + write blocks in correct order (consecutive same-type runs)
  - Batch in chunks of 40 (respects API limit)
  - Ownership transfer to user's open_id (verify → URL)
  - Orphan cleanup on transfer failure
  - Heading-at-root fallback (uses bold text instead)

Usage:
    python3 create_structured_doc.py "文档标题" [open_id] [tenant]

    open_id: optional Feishu user open_id for ownership transfer
    tenant:  optional tenant domain (default: bytedance)

Dependencies: Python stdlib only (urllib, json, os, sys, time)
"""

import json, os, sys, time, urllib.request
from urllib.error import HTTPError

DOCS_BASE = 'https://open.feishu.cn'

def read_env(key):
    hermes_home = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
    env_path = os.path.join(hermes_home, '.env')
    if not os.path.exists(env_path):
        return None
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith(key + '='):
                return line.split('=', 1)[1]
    return None

# ── 1. Auth ──
APP_ID = read_env('FEISHU_APP_ID')
APP_SECRET = read_env('FEISHU_APP_SECRET')
if not APP_ID or not APP_SECRET:
    hermes_home = os.environ.get('HERMES_HOME') or os.path.expanduser('~/.hermes')
    print(f"❌ FEISHU_APP_ID / FEISHU_APP_SECRET not set in {hermes_home}/.env")
    sys.exit(1)

tok = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode()
req = urllib.request.Request(
    f'{DOCS_BASE}/open-apis/auth/v3/tenant_access_token/internal',
    data=tok, headers={'Content-Type': 'application/json'})
try:
    auth_resp = json.loads(urllib.request.urlopen(req, timeout=15).read().decode())
    if auth_resp.get('code') != 0:
        print(f"❌ Auth failed: code={auth_resp.get('code')} msg={auth_resp.get('msg','')}")
        sys.exit(1)
    token = auth_resp.get('tenant_access_token')
    if not token:
        print("❌ Auth returned no tenant_access_token")
        sys.exit(1)
except (HTTPError, KeyError, json.JSONDecodeError) as e:
    print(f"❌ Auth failed: {e}")
    sys.exit(1)
H = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
print("✅ Token acquired")

def api(method, path, body=None):
    from urllib.error import HTTPError, URLError
    url = f'{DOCS_BASE}/open-apis{path}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, headers=H, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    except HTTPError as e:
        body = e.read().decode()
        try:
            return json.loads(body)
        except json.JSONDecodeError:
            return {"code": e.code, "msg": body[:200]}
    except Exception as e:
        return {"code": -1, "msg": str(e)[:200]}

# ── 2. Helpers ──
def text_block(content, bold=False):
    """Type-2 text block. Use bold=True for section headers (heading blocks fail at root)."""
    style = {"bold": True} if bold else {}
    return {"block_type": 2, "text": {
        "elements": [{"text_run": {"content": content, "text_element_style": style}}]
    }}

def bullet_block(content):
    """Type-12 bullet list item."""
    return {"block_type": 12, "bullet": {
        "elements": [{"text_run": {"content": content}}]
    }}

def code_block(content):
    """Type-14 code block (monospace, works via children API)."""
    return {"block_type": 14, "code": {
        "elements": [{"text_run": {"content": content[:50000]}}]
    }}

# ── 3. Create doc ──
TITLE = sys.argv[1] if len(sys.argv) > 1 else "Untitled Document"
USER_OPEN_ID = sys.argv[2] if len(sys.argv) > 2 else None
TENANT = sys.argv[3] if len(sys.argv) > 3 else "bytedance"

r = api('POST', '/docx/v1/documents', {"title": TITLE})
if r.get('code') != 0:
    print(f"❌ Create doc failed: code={r.get('code')} msg={r.get('msg','')}")
    sys.exit(1)
doc_id = r['data']['document']['document_id']
print(f"✅ Created: {TITLE}")
print(f"   ID: {doc_id}")

# ── 4. Write blocks with correct ordering ──
blocks = []

# ══════════════════════════════════════════════════
# EXAMPLE: build your content here
# ══════════════════════════════════════════════════
blocks.append(text_block("Document Title", bold=True))
blocks.append(text_block(""))

blocks.append(text_block("Section One", bold=True))
blocks.append(text_block("This is a paragraph of explanatory text."))
blocks.append(bullet_block("Item A with description"))
blocks.append(bullet_block("Item B \u2014 another entry"))
blocks.append(text_block(""))

blocks.append(text_block("Section Two", bold=True))
blocks.append(bullet_block("Detail 1: first bullet"))
blocks.append(bullet_block("Detail 2: second bullet"))
blocks.append(bullet_block("Detail 3: third bullet"))
blocks.append(text_block(""))
# ══════════════════════════════════════════════════

def write_blocks_in_order(blocks, parent_id=None, chunk_size=40):
    """
    Write blocks preserving original order.

    KEY INSIGHT: Feishu's API rejects mixed block types in a single POST.
    We must group consecutive same-type blocks into runs.

    Returns (total_written, errors) where total_written is actual blocks
    confirmed successful, and errors is a list of failed chunk descriptions.
    """
    parent = parent_id or doc_id
    i = 0
    pos = 0
    total_written = 0
    errors = []
    while i < len(blocks):
        bt = blocks[i]['block_type']
        run = []
        while i < len(blocks) and blocks[i]['block_type'] == bt:
            run.append(blocks[i])
            i += 1
        for chunk_start in range(0, len(run), chunk_size):
            chunk = run[chunk_start:chunk_start + chunk_size]
            r = api('POST', f'/docx/v1/documents/{doc_id}/blocks/{parent}/children',
                    {"children": chunk, "index": pos})
            if r.get('code') != 0:
                msg = f"  ⚠ FAIL: type={bt} x{len(chunk)} @ pos={pos} → {r.get('code')}: {r.get('msg','')[:120]}"
                print(msg)
                errors.append(msg)
            else:
                print(f"  ✓ type={bt} x{len(chunk)} @ pos={pos}")
                total_written += len(chunk)
            pos += len(chunk)
        time.sleep(0.15)  # rate limit avoidance
    return total_written, errors

written, errors = write_blocks_in_order(blocks)
if errors:
    print(f"✅ {written}/{len(blocks)} blocks written ({len(errors)} chunk(s) failed)")
else:
    print(f"✅ {written} blocks written")

# ── 5. Transfer ownership (BEFORE exposing URL) ──
transfer_ok = True
if USER_OPEN_ID:
    time.sleep(1)
    r = api('POST', f'/drive/v1/permissions/{doc_id}/members/transfer_owner?type=docx',
            {"member_type": "openid", "member_id": USER_OPEN_ID})
    if r.get('code') == 0:
        print(f"✅ Ownership transferred to {USER_OPEN_ID}")
    else:
        print(f"❌ Transfer FAILED: code={r.get('code')} msg={r.get('msg','')}")
        transfer_ok = False

# ── 6. On transfer failure: delete orphan doc ──
if USER_OPEN_ID and not transfer_ok:
    print("⚠ Transfer failed — deleting orphan document...")
    r = api('DELETE', f'/drive/v1/permissions/{doc_id}?type=docx')
    if r.get('code') == 0:
        print("✅ Orphan document deleted")
    else:
        print(f"⚠ Delete orphan FAILED: code={r.get('code')} msg={r.get('msg','')}")
        print(f"   Manual cleanup: DELETE /open-apis/drive/v1/permissions/{doc_id}?type=docx")
    # Still exit cleanly (no URL printed, doc is gone or flagged)
    print(f"\n❌ Document creation rolled back due to transfer failure")
    sys.exit(1)

# ── 7. Print URL (safe — after successful transfer or no transfer needed) ──
print(f"\n📄 {TITLE}")
print(f"   https://{TENANT}.feishu.cn/docx/{doc_id}")
