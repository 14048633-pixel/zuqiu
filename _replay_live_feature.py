# -*- coding: utf-8 -*-
"""临场特征回测(场次级): BEST场次 早盘(最早赛前快照) vs 临场(最晚赛前快照)
每场独立重放两版, 对比各自BEST腿的命中/ROI, 及临场特征(ΔEV/翻转/掉出/新增)."""
import sys, os, io, json, csv, re, unicodedata, collections
from datetime import datetime, timezone, timedelta

ROOT = r"D:\足球分析"
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
sys.path.insert(0, ROOT)
import scan_upcoming as su
from _replay_adj import get_team_stats, patch_cal, build_team_stats, load_scores, find_score
import settle_batch

SNAP = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
TMP = os.path.join(ROOT, "_snap_live_tmp.csv")

def _pt(s):
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d
    except Exception:
        return None

def _norm(s):
    s = unicodedata.normalize("NFKD", str(s or ""))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def load_snap_idx():
    idx = collections.defaultdict(lambda: collections.defaultdict(list))
    with io.open(SNAP, encoding="utf-8", errors="replace") as f:
        rd = csv.reader(f); hdr = next(rd)
        for x in rd:
            if not x:
                continue
            st, ct = _pt(x[0]), _pt(x[3])
            if st is None or ct is None or st > ct:
                continue
            idx[(x[2], _norm(x[4]), _norm(x[5]))][x[0]].append(x)
    return idx, hdr

def replay(rows, hdr):
    with io.open(TMP, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f); w.writerow(hdr)
        for x in rows:
            w.writerow(x)
    recs, _ = su.parse_snapshots(TMP)
    return recs[0] if recs else None

def analyze_rec(rec):
    mm = {"id": rec["id"], "league": rec["league"], "home": rec["home"], "away": rec["away"],
          "ct": rec["ct"], "h2h": rec["h2h"], "spread": rec.get("spread"), "totals": rec.get("totals"),
          "snap": rec["snap"], "books_used": rec.get("books_used") or {}, "coach_mods": {}}
    ts, lavg, index = get_team_stats("new", cutoff=rec["ct"])
    r = su.analyze_match(mm, ts, lavg, index)
    return r

def settle(name, odds, hg, ag):
    try:
        res, ret = settle_batch.settle_leg(name, odds or 0.0, hg, ag)
        return res, (ret - 1.0) if ret is not None else None
    except Exception:
        return "unknown", None

def main():
    su.recent_league_avg = lambda: {}
    idx, hdr = load_snap_idx()
    scores = load_scores()

    led = []
    with io.open(os.path.join(ROOT, "analysis_records", "bet_ledger.csv"), encoding="utf-8-sig", errors="replace") as f:
        for r in csv.DictReader(f):
            led.append(r)
    best = [r for r in led if r.get("status") == "已结算" and (r.get("star") or "") not in ("", "0")]
    # 场次级去重: (lg, home, away)
    matches = {}
    for r in best:
        k = (r.get("league"), r.get("home"), r.get("away"))
        matches.setdefault(k, r)
    print("BEST已结算腿:", len(best), "| 去重场次:", len(matches))

    out = []
    matched = only1 = nosnap = 0
    for (lg, h, a), r in matches.items():
        kf = r.get("kickoff") or ""
        ct = _pt(kf.replace("+08:00", "+00:00")) if "+08:00" in kf else _pt(kf)
        if ct is None:
            continue
        key = (lg, _norm(h), _norm(a))
        g = idx.get(key)
        if not g:
            nosnap += 1
            continue
        tss = sorted(ts for ts in g if _pt(ts) <= ct)
        if len(tss) < 2:
            only1 += 1
            continue
        matched += 1
        early_ts, live_ts = tss[0], tss[-1]
        er = replay(g[early_ts], hdr)
        lr = replay(g[live_ts], hdr)
        sc = find_score(scores, lg, h, a, ct)
        hg, ag = sc if sc else (None, None)

        def pack(rec, ts_):
            if rec is None:
                return None
            try:
                rr = analyze_rec(rec)
            except Exception as e:
                return {"error": str(e)}
            bb = rr.get("best_bet") or {}
            d = rr.get("direction") or {}
            res = {"snap": ts_, "snap_age_h": rr.get("snap_age_h"),
                   "best": bb.get("name"), "ev": bb.get("ev"), "star": bb.get("star"),
                   "veto": d.get("vetoed"), "veto_reason": d.get("veto_reason"),
                   "risk_tags": rr.get("risk_tags")}
            if hg is not None and bb.get("name"):
                res["result"], res["pnl"] = settle(bb["name"], bb.get("odds"), hg, ag)
            return res

        e = pack(er, early_ts)
        l = pack(lr, live_ts)
        if not e or not l:
            continue
        row = {"league": lg, "home": h, "away": a, "kickoff": kf,
               "score": ("%d-%d" % (hg, ag)) if hg is not None else None,
               "early": e, "live": l}
        if e.get("best") and l.get("best"):
            row["same_leg"] = (e["best"] == l["best"])
            row["delta_ev"] = (l.get("ev") or 0) - (e.get("ev") or 0) if e.get("ev") is not None and l.get("ev") is not None else None
        out.append(row)
    print("对比场次:", matched, "| 仅1时点:", only1, "| 无快照:", nosnap)

    json.dump(out, io.open(os.path.join(ROOT, "_replay_live_feature_out.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    valid = [x for x in out if x.get("early") and x.get("live")]

    def stat(rs, label, side="early"):
        rows = []
        for x in rs:
            s = x.get(side) or {}
            if s.get("best") and s.get("result"):
                rows.append(s)
        n = len(rows)
        if not n:
            print("%-26s n=0" % label); return
        win = sum(1 for s in rows if s["result"] in ("win", "half"))
        dec = sum(1 for s in rows if s["result"] in ("win", "half", "lose"))
        hit = win / dec * 100 if dec else 0
        pnl = sum((s.get("pnl") or 0) for s in rows)
        veto_n = sum(1 for s in rows if s.get("veto"))
        print("%-26s n=%3d 命中=%d/%d=%5.1f%% PnL=%+7.2f ROI=%+6.1f%% 否决=%d" % (label, n, win, dec, hit, pnl, pnl / n * 100 if n else 0, veto_n))

    print()
    print("== 早盘口径 vs 临场口径 (各自时点BEST腿) ==")
    stat(valid, "早盘 BEST 出单", "early")
    stat(valid, "临场 BEST 出单", "live")
    # 未否决子集
    nv = [x for x in valid if not (x.get("early") or {}).get("veto")]
    print()
    print("== 早盘未否决场次的临场表现 ==")
    stat(nv, "早盘BEST(未否决)", "early")
    stat(nv, "同日临场BEST", "live")
    same = [x for x in nv if x.get("same_leg")]
    diff = [x for x in nv if x.get("same_leg") is False]
    print()
    print("== 临场特征分组(早盘未否决场次) ==")
    stat(same, "两版同腿(临场确认)", "live")
    stat(diff, "两版翻转(不同腿)", "live")
    # 临场掉出: 早盘有best, 临场无best(否决或垃圾)
    dropped = [x for x in nv if (x.get("early") or {}).get("best") and not (x.get("live") or {}).get("best")]
    added = [x for x in valid if not (x.get("early") or {}).get("best") and (x.get("live") or {}).get("best")]
    print()
    stat(dropped, "临场掉出(早盘有单)", "early")
    stat(added, "临场新增(早盘无单)", "live")
    # ΔEV 分组 (仅同腿)
    ups = [x for x in same if (x.get("delta_ev") or 0) >= 0]
    dns = [x for x in same if (x.get("delta_ev") or 0) < 0]
    stat(ups, "同腿 ΔEV>=0(加强)", "live")
    stat(dns, "同腿 ΔEV<0(减弱)", "live")

if __name__ == "__main__":
    main()
