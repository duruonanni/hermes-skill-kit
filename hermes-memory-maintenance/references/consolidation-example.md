# Real-World Consolidation: From 99% to 30% in One Pass

## Context (2026-06-02)

User reported that tesseract-ocr memory was "lost" after only 2 days. Investigation showed:

- MEMORY.md was at **2,146/2,200 chars (97%)** — only 54 chars free
- USER.md was at **1,343/1,375 chars (97%)**
- The tesseract entry WAS present (line 39) — but the system was likely truncating memory injection because the file was near capacity

## Before Consolidation

### MEMORY.md: 11 entries, 2,200 chars (at limit)

Issues found:
- **Feishu MEDIA restriction** mentioned 3 times across different entries
- **Avoid hallucination rule** (get real data, don't hardcode) mentioned in 2 separate entries
- **Skill format YAML spec** — 18-line complete YAML example (~400 chars of static docs that belong in the `skill_manage` tool's behavior)
- **Skills Hub info** — how to search/install skills (~200 chars of static docs)
- **Feishu approval issue** — mentioned in both MEMORY line 1 and as a standalone entry

### USER.md: 7 entries, 2,231 chars (over limit)

Issues found:
- **Girlfriend info** duplicated from MEMORY
- **Feishu formatting** and **evidence-based preference** both mentioned in 2 separate entries
- **Pragmatic/evidence-based** preference stated 3 different ways across the file

## Actions Taken

### 1. Expanded Config Limits

```python
memory_char_limit: 2200 → 5000
user_char_limit: 1375 → 2500
```

### 2. Rewrote MEMORY.md (11 entries → 8 entries)

| Removed | Rationale |
|---------|-----------|
| MEDIA restriction ×2 duplicates | Merged into single entry |
| Hallucination rule duplicate | Merged with main preferences |
| Skill format YAML (18 lines) | Static knowledge, tool-handled |
| Skills Hub info (3 lines) | Static knowledge, in hermes-agent skill |

**Result:** 1,500 chars / 5,000 limit = **30% utilization**

### 3. Rewrote USER.md (7 entries → 5 entries)

| Removed | Rationale |
|---------|-----------|
| Girlfriend info | Keep only in MEMORY (environment fact, not user identity) |
| Duplicate formatting rules | Already in MEMORY + single user entry |
| Evidence-based preference ×3 | Merged into one core entry |

**Result:** 1,079 chars / 2,500 limit = **43% utilization**

### 4. Added Image Routing Rule

New entry in MEMORY.md: "用户说'截图读文本'→调tesseract，否则默认MiMo"

## Key Metrics

| Metric | Before | After |
|--------|--------|-------|
| MEMORY.md chars | 2,146 (99%) | 1,500 (30%) |
| USER.md chars | 1,343 (97%) | 1,079 (43%) |
| Total entries | 18 | 13 |
| Total free capacity | ~86 chars | ~4,921 chars |
| Estimated tokens consumed | ~780 | ~670 |

## Lessons Learned

1. **The memory tool's add/replace cannot handle bulk operations** — for consolidation, write the files directly
2. **"Static docs" creep into memory** — YAML specs, Skill Hub descriptions, and procedure steps all ended up in memory because the agent adds info when it discovers it. These need a separate archive path (skills).
3. **Memory and user profile overlap** — facts like "girlfriend info" and "formatting rules" naturally belong in both but should live in ONE place to avoid duplication
4. **Limit expansion should happen BEFORE consolidation** — trying to consolidate at 99% capacity with the add/replace interface fails because there's no room to add the replacement before removing old entries
