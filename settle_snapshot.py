# -*- coding: utf-8 -*-
"""9/5 校准后出单 vs 实际比分 结算(用 status=finished 显式拉已完赛)."""
import io, json, re, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.insert(0, r"D:\足球分析\prediction_v2")
import bsd_extra, requests

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

def fetch_finished():
    """GET status=finished 拉已完赛事件(9/4-9/5 UTC)."""
    out = []
    for d in ("2026-09-04", "2026-09-05"):
        off = 0
        while True:
            r = requests.get(bsd_extra.BASE_V2 + "/api/v2/events/", params={
                "status": "finished",
                "date_from": d + "T00:00:00Z", "date_to": d + "T23:59:59Z",
                "limit": 100, "offset": off, "full": "true"},
                headers=bsd_extra.HEADERS, timeout=60)
            if r.status_code != 200:
                print("HTTP", r.status_code, r.text[:120])
                break
            res = r.json().get("results") or []
            out += res
            if len(res) < 100:
                break
            off += 100
    return out

def main():
    d = json.load(io.open(SNAP, encoding="utf-8"))
    legs = []
    for m in d:
        for b in (m.get("bets") or []):
            legs.append({"home": m["home"], "away": m["away"], "league": m["league"],
                         "ko": m.get("ko_bjt", ""), "name": b["name"], "prob": b["prob"],
                         "odds": b["odds"], "ev": b["ev"], "star": b["star"], "mkt": b["mkt"]})
    print("快照腿数:", len(legs))

    evs = fetch_finished()
    print("finished 事件数:", len(evs))
    score_map = {}
    for j in evs:
        h = j.get("home_team"); a = j.get("away_team")
        h = h.get("name") if isinstance(h, dict) else h
        a = a.get("name") if isinstance(a, dict) else a
        st = bsd_extra.event_settle_scores(j)
        if st["needs_verify"] or st["hg_90"] is None or st["ag_90"] is None:
            continue
        score_map[(norm(h), norm(a))] = (st["hg_90"], st["ag_90"])
    print("有比分场次:", len(score_map))

    results = []
    for L in legs:
        key = (norm(L["home"]), norm(L["away"]))
        sc = score_map.get(key) or score_map.get((key[1], key[0]))
        if sc is None:
            results.append({**L, "status": "NO_MATCH"})
            continue
        hg, ag = sc
        if L["mkt"] == "1x2":
            actual = "主胜" if hg > ag else ("平局" if hg == ag else "客胜")
            win = (actual == L["name"])
        else:
            total = hg + ag
            win = (total >= 3) if L["name"].startswith("大") else (total <= 2)
        pnl = (L["odds"] - 1.0) if win else -1.0
        results.append({**L, "status": "OK", "score": "%d-%d" % (hg, ag), "win": win, "pnl": pnl})

    ok = [r for r in results if r["status"] == "OK"]
    nm = [r for r in results if r["status"] == "NO_MATCH"]
    print("=" * 94)
    print("已结算 %d / 未匹配 %d / 总 %d" % (len(ok), len(nm), len(results)))
    if ok:
        wins = sum(1 for r in ok if r["win"])
        pnl = sum(r["pnl"] for r in ok)
        print("【总】命中率 %.1f%% (%d/%d) | 净盈亏 %+.2f 单位 | ROI %+.1f%%" % (
            wins / len(ok) * 100, wins, len(ok), pnl, pnl / len(ok) * 100))
        for s in (3, 2, 1):
            g = [r for r in ok if r["star"] == s]
            if not g:
                continue
            w = sum(1 for r in g if r["win"])
            p = sum(r["pnl"] for r in g)
            print("  ★%d: n=%d 命中 %.0f%% 盈亏 %+.2f ROI %+.0f%%" % (
                s, len(g), w / len(g) * 100, p, p / len(g) * 100))
        # 按市场
        for mk in ("1x2", "ou"):
            g = [r for r in ok if r["mkt"] == mk]
            if not g:
                continue
            w = sum(1 for r in g if r["win"])
            p = sum(r["pnl"] for r in g)
            print("  [%s] n=%d 命中 %.0f%% ROI %+.1f%%" % (mk, len(g), w / len(g) * 100, p / len(g) * 100))
        print("-" * 94)
        for r in sorted(ok, key=lambda x: x["star"], reverse=True):
            tag = "W" if r["win"] else "L"
            print("  [%s] %-28s %-6s p%3.0f%% @%-5.2f ★%d %s %+6.2f" % (
                tag, (r["home"] + " vs " + r["away"])[:28], r["name"], r["prob"],
                r["odds"], r["star"], r["score"], r["pnl"]))
    if nm:
        print("未匹配腿(无最终比分):")
        for r in nm:
            print("  ?  %s vs %s | %s (%s)" % (r["home"], r["away"], r["name"], r["ko"]))

main()
