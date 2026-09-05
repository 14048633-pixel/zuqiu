# -*- coding: utf-8 -*-
"""校准+双条件后 batch 出单清单(完整列示)."""
import io, json, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

p = r"D:\足球分析\analysis_records\v2_best_scan_20260904_0833.json"
d = json.load(io.open(p, encoding='utf-8'))
print("快照: %s | 场次: %d" % (p.split("\\")[-1], len(d)))
print("=" * 100)
for m in d:
    bets = m.get("bets") or []
    best = m.get("best")
    if not bets:
        print("%-8s %-28s %-18s | 无正EV" % (m.get("ko_bjt", "")[:16], m.get("home", "") + " vs " + m.get("away", ""), m.get("league", "")))
        continue
    print("%-16s %-30s %-20s | BEST: %s" % (
        m.get("ko_bjt", "")[:16], (m.get("home", "") + " vs " + m.get("away", ""))[:30], m.get("league", ""),
        ("%s p%.0f%% @%.2f EV%+.1f%% ★%d" % (best["name"], best["prob"], best["odds"], best["ev"], best["star"])) if best else "无"))
    for b in bets:
        note = ""
        if b.get("note_big_div"):
            note = " ⚠" + b["note_big_div"]
        if b.get("veto_data") or b.get("veto_draw") or b.get("veto_low") or b.get("note_data_ou"):
            note += " [风控]"
        print("    %-6s p%5.1f%% @%-6.2f EV%+6.1f%% ★%d  %s%s" % (
            b.get("name", ""), b.get("prob", 0), b.get("odds", 0), b.get("ev", 0), b.get("star", 0),
            b.get("mkt", ""), note))
print("=" * 100)
