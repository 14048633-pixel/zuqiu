# -*- coding: utf-8 -*-
"""校准后 batch 快照 vs 实际比分 结算验证(2026-09-05)."""
import io, json, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import bsd_extra

SNAP = r"D:\足球分析\analysis_records\v2_best_scan_20260904_0833.json"

def norm(s):
    if not s:
        return ""
    s = str(s).lower()
    s = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", s)
    for suf in ("fc", "fk", "cf", "cfc", "afc", "ud", "cd", "ac", "sc", "sk", "bk", "if", "ff", "ss"):
        if s.endswith(suf) and len(s) > len(suf) + 2:
            s = s[: -len(suf)]
    return s

def main():
    d = json.load(io.open(SNAP, encoding="utf-8"))
    legs = []
    for m in d:
        for b in (m.get("bets") or []):
            legs.append({"home": m["home"], "away": m["away"], "league": m["league"],
                         "ko": m.get("ko_bjt", ""), "name": b["name"], "prob": b["prob"],
                         "odds": b["odds"], "ev": b["ev"], "star": b["star"], "mkt": b["mkt"]})
    print("快照腿数:", len(legs))

    # 拉 9/5 事件
    evs = bsd_extra.fetch_events("2026-09-05")
    print("BSD 事件数:", len(evs) if evs else 0)
    score_map = {}  # (norm_home, norm_away) -> (hg, ag, period)
    for j in (evs or []):
        h = j.get("home_team"); a = j.get("away_team")
        h = h.get("name") if isinstance(h, dict) else h
        a = a.get("name") if isinstance(a, dict) else a
        st = bsd_extra.event_settle_scores(j)
        if st["is_aet"] or st["needs_verify"]:
            continue
        if st["hg_90"] is None or st["ag_90"] is None:
            continue
        score_map[(norm(h), norm(a))] = (st["hg_90"], st["ag_90"], st["period"])
    print("可结算比分场次:", len(score_map))

    # 结算
    results = []
    matched = 0
    for L in legs:
        key = (norm(L["home"]), norm(L["away"]))
        sc = score_map.get(key)
        if sc is None:
            # 尝试反向
            sc = score_map.get((key[1], key[0]))
        if sc is None:
            results.append({**L, "status": "NO_MATCH"})
            continue
        matched += 1
        hg, ag, period = sc
        if L["mkt"] == "1x2":
            actual = "主胜" if hg > ag else ("平局" if hg == ag else "客胜")
            win = (actual == L["name"])
        else:
            total = hg + ag
            if L["name"].startswith("大"):
                win = total >= 3
            else:
                win = total <= 2
        pnl = (L["odds"] - 1.0) if win else -1.0
        results.append({**L, "status": "OK", "score": "%d-%d" % (hg, ag), "win": win, "pnl": pnl})

    # 统计
    print("=" * 92)
    ok = [r for r in results if r["status"] == "OK"]
    nm = [r for r in results if r["status"] == "NO_MATCH"]
    print("已结算 %d / 未匹配 %d / 总 %d" % (len(ok), len(nm), len(results)))
    if ok:
        wins = sum(1 for r in ok if r["win"])
        pnl = sum(r["pnl"] for r in ok)
        staked = len(ok)
        print("命中率: %.1f%% (%d/%d) | 净盈亏: %+.2f 单位 | ROI: %+.1f%%" % (
            wins / staked * 100, wins, staked, pnl, pnl / staked * 100))
        for s in (3, 2, 1):
            g = [r for r in ok if r["star"] == s]
            if not g:
                continue
            w = sum(1 for r in g if r["win"])
            p = sum(r["pnl"] for r in g)
            print("  ★%d: n=%d 命中 %.0f%% 盈亏 %+.2f ROI %+.0f%%" % (
                s, len(g), w / len(g) * 100, p, p / len(g) * 100))
        print("-" * 92)
        for r in ok:
            tag = "W" if r["win"] else "L"
            print("  [%s] %-30s %-6s p%4.0f%% @%-5.2f ★%d  %s  %+.2f" % (
                tag, (r["home"] + " vs " + r["away"])[:30], r["name"], r["prob"], r["odds"],
                r["star"], r["score"], r["pnl"]))
    if nm:
        print("未匹配腿(无比分):")
        for r in nm:
            print("  ?  %s vs %s | %s" % (r["home"], r["away"], r["name"]))

main()
