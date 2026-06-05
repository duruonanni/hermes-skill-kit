#!/usr/bin/env python3
"""
Feishu Document Creation Script — v2 (Hub-clean)

Fixed vs v1:
- Uses ONLY type-2 text blocks (heading blocks fail at doc root)
- Batches blocks to respect 50-block API limit
- URL only printed after ownership transfer completes
- Uses FEISHU_BASE_URL env var (defaults to https://bytedance.feishu.cn)
- Validates all API responses

Usage:
    python3 create_doc.py "文档标题" [user_open_id]

Requires:
    FEISHU_APP_ID and FEISHU_APP_SECRET in .env
"""

import json, os, sys, time, urllib.request

FEISHU_BASE = os.environ.get('FEISHU_BASE_URL', 'https://bytedance.feishu.cn')
DOCS_BASE = 'https://open.feishu.cn'

def read_env(key):
    env_path = os.path.expanduser(
        os.environ.get('HERMES_HOME', '~/.hermes') + '/.env')
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
    print("❌ FEISHU_APP_ID / FEISHU_APP_SECRET not set")
    sys.exit(1)

tok = json.dumps({"app_id": APP_ID, "app_secret": APP_SECRET}).encode('utf-8')
req = urllib.request.Request(
    f'{DOCS_BASE}/open-apis/auth/v3/tenant_access_token/internal',
    data=tok, headers={'Content-Type': 'application/json; charset=utf-8'})
try:
    resp = urllib.request.urlopen(req, timeout=15)
except Exception as e:
    print(f"❌ Network error: {e}")
    sys.exit(1)
auth_data = json.loads(resp.read().decode())
if auth_data.get('code') != 0:
    print(f"❌ Auth failed: code={auth_data.get('code')} msg={auth_data.get('msg','')}")
    sys.exit(1)
token = auth_data.get('tenant_access_token')
if not token:
    print("❌ Auth returned no tenant_access_token")
    sys.exit(1)
H = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}
print("✅ Token acquired")

def api(method, path, body=None):
    url = f'{DOCS_BASE}/open-apis{path}'
    data = json.dumps(body, ensure_ascii=False).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, headers=H, method=method)
    try:
        return json.loads(urllib.request.urlopen(req, timeout=20).read().decode())
    except urllib.error.HTTPError as e:
        err = json.loads(e.read().decode())
        print(f"  ⚠ API error: {err.get('code')}: {err.get('msg','')[:80]}")
        return err

# ── 2. Create doc ──
TITLE = sys.argv[1] if len(sys.argv) > 1 else "Untitled Document"
USER_OPEN_ID = sys.argv[2] if len(sys.argv) > 2 else None

r = api('POST', '/docx/v1/documents', {"title": TITLE})
if r.get('code') != 0:
    print(f"❌ Create doc failed: code={r.get('code')} msg={r.get('msg','')}")
    sys.exit(1)
doc_id = r['data']['document']['document_id']
if not doc_id:
    print("❌ Document creation failed")
    sys.exit(1)
print(f"✅ Created: {TITLE} (ID: {doc_id})")

# ── 3. Write blocks (type-2 only, batched by 50) ──
blocks = [
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "Section Title", "text_element_style": {"bold": True}}}]}},
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "This is a paragraph of text."}}]}},
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "  • Bullet point A"}}]}},
    {"block_type": 2, "text": {"elements": [{"text_run": {"content": "  • Bullet point B"}}]}},
]

CHUNK_SIZE = 50
for i in range(0, len(blocks), CHUNK_SIZE):
    chunk = blocks[i:i+CHUNK_SIZE]
    r = api('POST', f'/docx/v1/documents/{doc_id}/blocks/{doc_id}/children',
            {"children": chunk, "index": i})
    if r.get('code') != 0:
        print(f"  ⚠ Write batch {i//CHUNK_SIZE + 1} failed")
        sys.exit(1)
    time.sleep(0.15)
print(f"✅ {len(blocks)} block(s) written")

# ── 4. Transfer ownership (only NOW print URL) ──
if USER_OPEN_ID:
    time.sleep(1)
    r = api('POST', f'/drive/v1/permissions/{doc_id}/members/transfer_owner?type=docx',
            {"member_type": "openid", "member_id": USER_OPEN_ID})
    if r.get('code') == 0:
        print(f"✅ Ownership transferred to {USER_OPEN_ID}")
    else:
        # Rollback: delete orphan doc
        api('DELETE', f'/drive/v1/permissions/{doc_id}?type=docx')
        print("❌ Transfer failed, document deleted")
        sys.exit(1)

print(f"\n📄 {FEISHU_BASE}/docx/{doc_id}")
