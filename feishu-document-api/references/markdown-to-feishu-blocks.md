# Markdown-to-Feishu-Block Conversion

When syncing raw markdown/text files (MEMORY.md, USER.md, configs) into a Feishu document for readable display, you cannot simply paste the raw text. You must parse each line and construct the appropriate block type.

## Block type caveats

**Code block display (type 14) WORKS via children API.** Use `block_type=14` with `{"code": ...}`:

```python
{
    "block_type": 14,
    "code": {
        "elements": [{"text_run": {"content": "full file content string"}}]
    }
}
```

Type 14 renders raw text in monospace — ideal for MEMORY.md dumps, configs, logs.

**Code block language-highlighted (type 17) CANNOT be created via `POST /children`.** Returns `code: 1770001`. Type 17 can only be created by updating an existing code block via `PATCH /blocks/{block_id}` — not useful for batch writes.

**Quote blocks (type 15)** work via children API with `{"quote": ...}` — good for metadata, timestamps, and status labels.

## Core conversion functions

```python
def block_text(c, bold=False):
    """Text paragraph (type 2)."""
    style = {"bold": True} if bold else None
    d = {"text_run": {"content": c}}
    if style:
        d["text_run"]["text_element_style"] = style
    return {"block_type": 2, "text": {"elements": [d]}}

def block_h2(c):
    """Heading level 2 (type 4)."""
    return {"block_type": 4, "heading2": {"elements": [{"text_run": {"content": c}}]}}

def block_h3(c):
    """Heading level 3 (type 5)."""
    return {"block_type": 5, "heading3": {"elements": [{"text_run": {"content": c}}]}}

def block_bullet(c):
    """Bullet point (type 12)."""
    return {"block_type": 12, "bullet": {"elements": [{"text_run": {"content": c}}]}}

def block_code(c):
    """Code/monospace block (type 14) — works via children API."""
    return {"block_type": 14, "code": {"elements": [{"text_run": {"content": c}}]}}

def block_quote(c):
    """Block quote (type 15) — good for metadata/timestamps."""
    return {"block_type": 15, "quote": {"elements": [{"text_run": {"content": c}}]}}

def block_empty():
    """Blank line spacer."""
    return {"block_type": 2, "text": {"elements": [{"text_run": {"content": ""}}]}}
```

## Parsing markdown lines

```python
def parse_markdown_file(text, source_name="file"):
    """Convert raw markdown text into a list of Feishu block dicts."""
    blocks = []
    blocks.append(h2(source_name))
    blocks.append(t(f"Full content (~/.hermes/memories/{source_name}):"))

    for line in text.split('\n'):
        s = line.strip()
        if s == '':
            continue

        if s.startswith('## ') and not s.startswith('### '):
            blocks.append(h2(s[3:]))           # Heading level 2
        elif s.startswith('### '):
            blocks.append(h3(s[4:]))            # Heading level 3
        elif s.startswith('---'):
            blocks.append(t('─────────────────'))  # Divider (type 16 unsupported)
        elif s.startswith('- '):
            blocks.append(b(s[2:]))             # Bullet point
        elif s.startswith('| '):
            # Table row → "key: value" bullet
            parts = [p.strip() for p in s.split('|') if p.strip()]
            if 'Dimension' in s or s.startswith('|--'):
                continue  # skip header & separator
            if len(parts) >= 2:
                blocks.append(b(f"{parts[0]}: {parts[1]}"))
        else:
            # Regular text — strip ** markers
            clean = s.replace('**', '')
            blocks.append(t(clean))

    return blocks
```

## Handling `**bold**` markers

Feishu `text_run` supports native bold via `text_element_style`. Do NOT leave markdown `**` in the content. Three approaches:

1. **Strip entirely** (simplest): `s.replace('**', '')` — loses bold formatting but clean
2. **Parse into segments**: Split on `**` and apply bold to alternating segments
3. **Full bold**: If the line starts and ends with `**`, strip markers and use `bold=True`

For session scripts, approach #1 (strip) is recommended unless the bold distinction matters.

## Handling table rows

Markdown tables like:
```
| Dimension | Level |
|-----------|-------|
| Engineering Rigor | Very High |
```

Parse as:
```python
for line in text.split('\n'):
    s = line.strip()
    if s.startswith('| '):
        parts = [p.strip() for p in s.split('|') if p.strip()]
        if 'Dimension' in s or s.startswith('|--'):
            continue  # header/separator → skip
        if len(parts) >= 2:
            blocks.append(b(f"{parts[0]}: {parts[1]}"))
```

**Important:** Do NOT filter out rows that contain words like "Engineering" in their key value — only filter the header and separator rows. A naive `if 'Dimension' in s or '|------' in s: continue` is safe because header row contains "Dimension" and separator contains dashes.

## Document ordering

When doing a full sync (delete-all → rewrite), block order determines document order:

```python
# CORRECT order:
blocks = []
blocks += parse_markdown_file(memory_text, "📦 MEMORY.md — 环境事实与工具技巧")
blocks += parse_markdown_file(user_text,   "👤 USER.md — 用户画像与偏好")
blocks += evaluation_blocks  # optional appendix

# WRONG — places content after the second heading:
blocks = []
blocks.append(h2("📦 MEMORY.md"))
blocks.append(h2("👤 USER.md"))
blocks += parse_markdown_file(memory_text)  # appears under USER.md
```

Always write content blocks immediately after their heading block in the array.

## Iterative cleanup pattern

If a document already has blocks in wrong order, you cannot reorder them in-place — you must:

1. `GET /children` to count all blocks
2. `DELETE /children/batch_delete` with `{start_index: 0, end_index: N}` (deletes ALL)
3. Rewrite everything from scratch in correct order

This is destructive (loses any content added outside your sync script), but ensures clean structure.
