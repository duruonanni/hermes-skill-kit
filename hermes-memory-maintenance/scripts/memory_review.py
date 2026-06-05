#!/usr/bin/env python3
"""Enhanced weekly memory review — quality, consistency, stale detection, growth projection."""
import os, re, json, yaml
from pathlib import Path
from datetime import datetime

HERMES = os.path.expanduser("~/.hermes")
MEMORY = Path(HERMES) / "memories" / "MEMORY.md"
USER  = Path(HERMES) / "memories" / "USER.md"
CONFIG = Path(HERMES) / "config.yaml"

# ── Config-aware limits ──────────────────────────────────────────────────

def load_limits():
    defaults = {"memory_char_limit": 5000, "user_char_limit": 2500}
    try:
        with open(CONFIG) as f:
            cfg = yaml.safe_load(f)
        mc = cfg.get("memory", {})
        return {
            "mem": int(mc.get("memory_char_limit", defaults["memory_char_limit"])),
            "user": int(mc.get("user_char_limit", defaults["user_char_limit"])),
        }
    except Exception:
        return {"mem": defaults["memory_char_limit"], "user": defaults["user_char_limit"]}


# ── Parse helpers ────────────────────────────────────────────────────────

ENTRY_DELIMITER = "\n§\n"

def parse_entries(path: Path) -> list:
    if not path.exists():
        return []
    raw = path.read_text(encoding="utf-8")
    return [e.strip() for e in raw.split(ENTRY_DELIMITER) if e.strip()]


# ── Quality scoring (GATE criteria: detail + structure + actionability + verifiability) ──

def quality_score(entry: str) -> int:
    """0-4: specificity + actionability + verifiability."""
    s = 0
    if len(entry) > 80:
        s += 1  # sufficient detail
    if re.search(r"[【\[]", entry):
        s += 1  # structured / labelled
    if re.search(r"(验证|确认|检查|必须|禁止|不准|拒绝)", entry):
        s += 1  # actionable directive
    if re.search(r"(open_id|chat_id|GitHub|repo|路径|地址|\d+\.\d+\.\d+)", entry):
        s += 1  # contains verifiable facts
    return s


# ── Contradiction detection ──────────────────────────────────────────────

def detect_contradictions(entries: list, label: str) -> list:
    """Rule-based contradiction checks."""
    warnings = []
    seen_open_ids = {}
    for entry in entries:
        m = re.search(r"open_id[=: ]*([a-zA-Z0-9_]+)", entry)
        if m:
            oid = m.group(1)
            if oid in seen_open_ids:
                warnings.append(f"⚠️ [{label}] 重复 open_id 条目: {oid}")
            seen_open_ids[oid] = entry

    # Check for duplicate headers (same ## topic)
    topic_map = {}
    for entry in entries:
        hm = re.search(r"^##\s+(.+)$", entry, re.MULTILINE)
        if hm:
            topic = hm.group(1).strip()
            if topic in topic_map:
                warnings.append(f"⚠️ [{label}] 重复主题「{topic}」")
            topic_map[topic] = entry
    return warnings


# ── Stale detection ──────────────────────────────────────────────────────

def detect_stale(entries: list, label: str) -> list:
    """Flag entries with old dates or potentially stale content."""
    stale = []
    now = datetime.now()
    for entry in entries:
        for m in re.finditer(r"(\d{4})-(\d{2})-(\d{2})", entry):
            try:
                dt = datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
                delta = (now - dt).days
                if delta > 180:
                    stale.append((entry[:80], f"日期距今 {delta} 天"))
            except ValueError:
                pass
    return stale


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    limits = load_limits()
    mem_entries = parse_entries(MEMORY)
    user_entries = parse_entries(USER)

    mem_content = ENTRY_DELIMITER.join(mem_entries)
    user_content = ENTRY_DELIMITER.join(user_entries)

    mem_chars = len(mem_content)
    user_chars = len(user_content)

    # ── Output ────────────────────────────────────────────────────────
    print("🧠 记忆质量审查报告")
    print(f"   日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print()

    # 1. Capacity
    print("## 1. 容量")
    mem_pct = min(100, round(mem_chars / limits["mem"] * 100))
    user_pct = min(100, round(user_chars / limits["user"] * 100))
    print(f"   MEMORY.md: {mem_chars:,}/{limits['mem']:,} chars ({mem_pct}%) — {len(mem_entries)} 条")
    print(f"   USER.md:   {user_chars:,}/{limits['user']:,} chars ({user_pct}%) — {len(user_entries)} 条")
    total_chars = mem_chars + user_chars
    total_limit = limits["mem"] + limits["user"]
    print(f"   合计:      {total_chars:,}/{total_limit:,} chars ({min(100, round(total_chars/total_limit*100))}%)")
    print()

    # 2. Quality
    print("## 2. 质量评分 (0-4)")
    for i, entry in enumerate(mem_entries, 1):
        score = quality_score(entry)
        icon = "🟢" if score >= 3 else "🟡" if score >= 2 else "🔴"
        print(f"   {icon} M{i}: {score}/4 — {entry[:70]}...")
    print()

    # 3. Contradictions
    print("## 3. 矛盾检测")
    warns = []
    warns += detect_contradictions(mem_entries, "MEMORY")
    warns += detect_contradictions(user_entries, "USER")
    if warns:
        for w in warns:
            print(f"   {w}")
    else:
        print("   ✅ 未发现明显矛盾")
    print()

    # 4. Stale entries
    print("## 4. 过时条目")
    stale_m = detect_stale(mem_entries, "MEMORY")
    stale_u = detect_stale(user_entries, "USER")
    stale_all = stale_m + stale_u
    if stale_all:
        for preview, reason in stale_all:
            print(f"   ⏳ {reason}: {preview}...")
    else:
        print("   ✅ 无过时条目")
    print()

    # 5. Long entries
    print("## 5. 长条目 (建议精简)")
    for i, entry in enumerate(mem_entries, 1):
        if len(entry) > 300:
            print(f"   📏 M{i}: {len(entry)} chars — {entry[:60]}...")
    print()

    # 6. Growth projection
    print("## 6. 增长预测")
    weekly_growth = 400  # chars/week (empirical estimate)
    mem_weeks = (limits["mem"] - mem_chars) / weekly_growth if weekly_growth > 0 else 999
    user_weeks = (limits["user"] - user_chars) / weekly_growth if weekly_growth > 0 else 999
    print(f"   估计每周增长: {weekly_growth} chars")
    print(f"   MEMORY.md 可用: {mem_weeks:.1f} 周 ({limits['mem'] - mem_chars:,} chars 余量)")
    print(f"   USER.md 可用:   {user_weeks:.1f} 周 ({limits['user'] - user_chars:,} chars 余量)")
    if mem_weeks < 8:
        print("   ⚠️ MEMORY.md 8周内将满，建议清理过期内容或提高 memory_char_limit")
    if user_weeks < 4:
        print("   🔴 USER.md 即将耗尽! 立即清理或提高 user_char_limit")
    print()

    # 7. Summary
    print("## 7. 可操作建议")
    actions = []
    if mem_weeks < 8:
        actions.append(f"🔄 MEMORY.md 余量 {mem_weeks:.0f} 周 — 清理旧错误归档条目")
    if user_weeks < 4:
        actions.append(f"🔄 USER.md 余量仅 {user_weeks:.0f} 周 — 精简行为规则或提高 user_char_limit")
    for i, entry in enumerate(mem_entries, 1):
        if len(entry) > 300:
            actions.append(f"🔄 MEMORY.md 条目{i} 过长 ({len(entry)} chars) — 考虑拆分或精简")
    if not actions:
        actions.append("✅ 暂无必要操作")
    for a in actions:
        print(f"   {a}")


if __name__ == "__main__":
    main()
