# § Delimiter Drift Recovery

## Problem

MEMORY.md/USER.md uses `ENTRY_DELIMITER = "\n§\n"` to separate entries. When the file is edited manually or via `write_file`, extra blank lines around the `§` (e.g. `\n\n§\n\n`) cause the roundtrip check to fail:

```python
raw.strip() != ENTRY_DELIMITER.join(parsed)
# Because strip() removes the extra newlines that parsing preserved
```

## Symptoms

- `memory(action='add')` returns `"Refusing to write: file on disk has content that wouldn't round-trip"`
- A `.bak.<timestamp>` file is created with each failed write
- The internal store retains the session-startup snapshot (which may be stale)

## Recovery Procedure

1. **Read the current file** to understand its content:
   ```python
   read_file("~/.hermes/memories/MEMORY.md")
   ```

2. **Rewrite with correct § formatting** — exact `\n§\n`, no blank lines around §:
   ```bash
   cat > ~/.hermes/memories/MEMORY.md << 'EOF'
   Entry 1 content...
   §
   Entry 2 content...
   EOF
   ```

3. **Verify roundtrip:**
   ```python
   from pathlib import Path
   from tools.memory_tool import ENTRY_DELIMITER
   raw = Path("~/.hermes/memories/MEMORY.md").expanduser().read_text("utf-8")
   entries = [e.strip() for e in raw.split(ENTRY_DELIMITER) if e.strip()]
   ok = raw.strip() == ENTRY_DELIMITER.join(entries)
   print(f"Roundtrip: {'OK' if ok else 'FAIL'}")
   ```

4. **Test the memory tool:**
   ```python
   memory(action='add', target='memory', content='## Probe\ndrift check')
   # Should return success=True, not drift error
   ```

5. **Clean up** `.bak.<timestamp>` files:
   ```bash
   rm ~/.hermes/memories/MEMORY.md.bak.*
   ```

## Prevention

- Always use `memory(action='add/replace/remove')` for day-to-day memory changes
- When rewriting a memory file directly, use EXACT `\n§\n` formatting
- After any direct edit, verify roundtrip before continuing
- After modifying `memory_tool.py` parser methods, test a probe write before relying on memory
