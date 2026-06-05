# Ownership Transfer for Feishu Documents

When `permission.member.create` API fails (error 917813 / 1066001), ownership transfer is the verified workaround. The user becomes document owner with full access including version history.

## API Endpoint

```
POST /open-apis/drive/v1/permissions/{token}/members/transfer_owner?type=docx
Body: {"member_type": "openid", "member_id": "<user_open_id>"}
```

The document `token` is the same as `document_id` returned by create.

**⚠️ HTTP method:** Use **POST**, not PATCH. PATCH returns 404.

## Full Workflow (Python)

```python
import json, os, http.client

# === Auth ===
env_path = os.path.expanduser(os.environ.get('HERMES_HOME', '~/.hermes') + '/.env')
def read_env(k):
    with open(env_path) as f:
        for line in f:
            if line.startswith(k + '='):
                return line.split('=', 1)[1]
    return None

app_id = read_env('FEISHU_APP_ID')
app_secret = read_env('FEISHU_APP_SECRET')

conn = http.client.HTTPSConnection('open.feishu.cn')
tok = json.dumps({"app_id": app_id, "app_secret": app_secret}).encode('utf-8')
conn.request('POST', '/open-apis/auth/v3/tenant_access_token/internal',
             tok, {'Content-Type': 'application/json; charset=utf-8'})
token = json.loads(conn.getresponse().read().decode()).get('tenant_access_token')
h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json; charset=utf-8'}

# === Step 1: Create document ===
DOC_TITLE = "Task Tracking"
body = json.dumps({"title": DOC_TITLE}).encode('utf-8')
conn.request('POST', '/open-apis/docx/v1/documents', body, h)
resp = json.loads(conn.getresponse().read().decode())
doc_id = resp['data']['document']['document_id']
print(f"Created doc: {doc_id}")

# === Step 2: Transfer ownership to user ===
user_open_id = "ou_xxx"  # get from sender.open_id
body = json.dumps({
    "member_type": "openid",
    "member_id": user_open_id
}).encode('utf-8')
url = f'/open-apis/drive/v1/permissions/{doc_id}/members/transfer_owner?type=docx'\nconn.request('POST', url, body, h)
resp = json.loads(conn.getresponse().read().decode())

if resp.get('code') == 0:
    # Step 3: Only NOW show the link
    doc_url = f"https://bytedance.feishu.cn/docx/{doc_id}"
    print(f"Transferred! URL: {doc_url}")
    # Send doc_url to user via Feishu message
else:
    # Step 3 (fail): Rollback — delete the orphan document
    print(f"Transfer failed: {resp.get('code')} {resp.get('msg')}")
    conn.request('DELETE', f'/open-apis/drive/v1/permissions/{doc_id}?type=docx', headers=h)
    delete_resp = json.loads(conn.getresponse().read().decode())
    print(f"Rollback: {delete_resp.get('code')}")
    # Tell user: "暂时无法创建文档，请稍后重试"
```

## Error Codes

| Code | Meaning | Action |
|------|---------|--------|
| 0 | Success | Continue |
| 917813 | `permission.to.create member` — endpoint not available | Use ownership transfer instead |
| 1066001 | Internal error (permission not published or API unavailable) | Check publish status; use transfer_owner as workaround |
| 99991672 | Missing docx:document scope | Add scope + publish new version |
| 400/403 | Target user invalid (deleted, external, wrong tenant) | Tell user, no retry |

## Critical Rules

1. **Never expose the link before transfer completes** — the user has no access during the window between creation and transfer. They'll see a 403.
2. **Always delete on transfer failure** — otherwise orphan docs accumulate in the app account.
3. **Transfer to the person you're chatting with** — use their `open_id` from the Feishu gateway.
4. **After transfer, the user can add collaborators via UI** — you cannot add members via API; let the owner manage permissions.

## Proactive Suggestion in Chat

When the conversation involves complex tasks (≥3 steps, cross-session, multi-person):

1. **Suggest** — "需要我帮你创建一个飞书文档来记录这些步骤吗？文档归属你，方便管理和分享。"
2. **Wait for confirmation** — never create without explicit user approval.
3. **Execute** — create → transfer → verify → send link.
4. **If user refuses** — don't suggest again this session.
5. **On failure** — delete orphan, apologize, suggest manual creation.

See also: `feishu-document-api` SKILL.md for the full context.
