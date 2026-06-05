# Table Block (type 31) Discovery

Empirically discovered on 2026-06-05. The official Feishu Open API docs for tables are client-rendered (SPA) and not accessible via curl/extract — the actual format was determined through trial and error.

## What did NOT work

### ❌ Inline cells in children POST
Tried passing cells as part of the table block within the `children` array. Failed with code 9499 "Invalid parameter type in json: cells".

Three variants all failed:
1. **2D array with per-cell block arrays**: `cells[row][col] = [block1, block2, ...]`
2. **Flat array of blocks**: `cells = [blockA, blockB, ...]` (row-by-row)
3. **2D array of blocks** (not wrapped in arrays): `cells[row][col] = block`

All returned 9499 — the `cells` field cannot be provided inline during creation.

### ❌ 10+ rows in table creation
Tables with `row_size >= 10` (including the header row) fail with code **1770001**: "invalid param". The hard limit is 9 rows via API. Document UI can create larger tables; this restriction applies only to API-based creation.

```python
# FAILS
{'row_size': 10, 'column_size': 2}  # code 1770001

# WORKS — max 9
{'row_size': 9, 'column_size': 2}
```

Workaround: split large data into multiple ≤9-row tables. Verified: 9 rows ✓, 10 rows ✗.

### ❌ POST with `index` parameter for table blocks
When appending tables at the end of a document, including `index` in the POST body can cause HTTP 400. Text blocks tolerate `index`; table blocks don't always. Workaround: omit `index` when appending tables.

```python
# WORKS
api('POST', path, {'children': [table_block]})  # no index

# MAY FAIL (HTTP 400)
api('POST', path, {'children': [table_block], 'index': pos})
```

### ❌ PATCH on cell blocks
After creating the table skeleton (which auto-creates empty cells with block_type=32), tried to update cell content via:
```
PATCH /docx/v1/documents/{doc_id}/blocks/{cell_id}
Body: {"update_text_elements": {"elements": [...]}}
```
Returns code **1770025**: `"operation and block not match"` — cells (type 32) do not support `update_text_elements`.

## What DID work

### ✅ Two-step process

**Step 1 — Create table skeleton (NO `cells` field):**
```
POST /docx/v1/documents/{doc_id}/blocks/{doc_id}/children
Body: {
  "children": [{
    "block_type": 31,
    "table": {
      "property": {
        "row_size": 3,
        "column_size": 3,
        "column_width": [240, 240, 240]
      }
    }
  }]
}
```
Response: returns the table block with auto-created cell block_ids in a flat array: `"cells": ["cell_id_1", "cell_id_2", ...]` ordered row-by-row.

**Step 2 — Add text blocks as children of each cell:**
```
POST /docx/v1/documents/{doc_id}/blocks/{cell_id}/children
Body: {
  "children": [{
    "block_type": 2,
    "text": {"elements": [{"text_run": {"content": "Cell content"}}]}
  }]
}
```
Works for any cell. Each cell starts with one empty child block; adding more appends alongside it (harmless).

### ✅ Table type reference

| block_type | Key | Created how |
|------------|-----|-------------|
| 31 | `table` | POST children, provide `property` only |
| 32 | `table_cell` | Auto-created when table is created |
| 2 | `text` | POST children into each cell for content |

### ✅ Cell layout

Cells are returned as a flat array indexed row-by-row:
- `cells[0..n-1]` = row 0 (n = column_size)
- `cells[n..2n-1]` = row 1
- etc.

```python
for row_idx, row_data in enumerate(all_rows):
    for col_idx, cell_text in enumerate(row_data):
        cell_id = cell_ids[row_idx * n_cols + col_idx]
        # POST child text block into cell_id
```
