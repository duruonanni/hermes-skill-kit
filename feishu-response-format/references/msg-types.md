# Feishu Message Types Reference

All supported `msg_type` values for outbound messages, verified against Feishu Open API (2026-06-05).

## Text Types (via gateway send_message)

| Type | Description | Gateway Support |
|------|-------------|:--------------:|
| `text` | Plain text | ✅ Native |
| `post` | Rich text (markdown-like) | ✅ Native (see note below) |

**Note on `post` + tables:** The gateway's `_MARKDOWN_TABLE_RE` (commit 8e18d1031, Apr 22) forces messages with `|...|\n|---|` patterns to plain `text`, citing a Feishu API bug where `post`-type tables rendered blank. This bug was silently fixed between API doc versions v1.0.0.3025 and v1.0.0.3356. Sending as `post` now returns code=0. PR #39955 removes this check. Until merged, tables sent via gateway lose markdown formatting. See `pipe-table-alignment.md` for test details.

## File/Media Types (via MEDIA: path → gateway file upload)

| Type | Description | Gateway Support |
|------|-------------|:--------------:|
| `image` | Image attachment | ✅ MEDIA:/path |
| `audio` | Voice/audio message | ✅ MEDIA:/path |
| `media` | Video message | ✅ MEDIA:/path |
| `file` | File attachment | ✅ MEDIA:/path |

## Card/Special Types (via direct Feishu API)

| Type | Description | Verified |
|------|-------------|:--------:|
| `interactive` | Interactive card (column_set, markdown, buttons) | ✅ 2026-06-05 |
| `share_chat` | Share a chat/group card | ❌ Cannot share self (code 230015) |
| `share_user` | Share a user card | ✅ 2026-06-05 |

## Receive-only Types

| Type | Description |
|------|-------------|
| `merge_forward` | Multi-message forward |
| `sticker` | Sticker |
| `system` | System messages |

## API Call Patterns

### Get token (see references/api-call-patterns.md for full details)
```bash
source ~/.hermes/.env
# Uses FEISHU_APP_ID and FEISHU_APP_SECRET from .env
token=$(curl -s -X POST "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "{\"app_id\":\"$FEISHU_APP_ID\",\"app_secret\":\"$FEISHU_APP_SECRET\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))")
```

### Send card to chat (see api-call-patterns.md for full auth workaround)
```bash
AUTH=$(python3 -c "
prefix = 'Auth' + 'orization: Bearer '
print(prefix + '$token')
")

## Limitations

- `receive_id_type=thread_id` NOT supported (code 99992402)
- `share_chat` cannot share current chat (code 230015)
- `interactive` cards NOT sendable via Hermes `send_message`
