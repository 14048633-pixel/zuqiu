import io, sys
src = io.open(r"D:\足球分析\_scan_next24h_v2.py", encoding="utf-8").read()
# 在 bsd_odds_merge 后加 apifb 注入
old = """    print("events:", len(events))
    try:
        n = su.bsd_odds_merge(events)
        print("BSD consensus 覆盖:", n)
    except Exception as e:
        print("bsd_odds_merge skip:", repr(e)[:200])"""
new = """    print("events:", len(events))
    try:
        n = su.bsd_odds_merge(events)
        print("BSD consensus 覆盖:", n)
    except Exception as e:
        print("bsd_odds_merge skip:", repr(e)[:200])
    # 天皇杯: 注入 API-Football 盘口 (snapshots.csv apifb 行)
    try:
        n2 = _apifb_emperor_inject(events)
        print("API-FB 天皇杯盘口注入:", n2)
    except Exception as e:
        print("apifb inject skip:", repr(e)[:200])"""
assert old in src
src = src.replace(old, new)

# 在 main() 前插入注入函数
inject_fn = '''
def _apifb_emperor_inject(events):
    """从 snapshots.csv 注入 apifb 天皇杯盘口 (h2h/totals 均值)"""
    import csv, statistics
    snap_p = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    rows = list(csv.DictReader(io.open(snap_p, encoding="utf-8-sig")))
    agg = {}   # apifb{fid} -> {h2h:{side:[price]}, totals:{side:[price]}}
    for r in rows:
        eid = r.get("event_id") or ""
        if r.get("league") != "天皇杯" or not eid.startswith("apifb"):
            continue
        d = agg.setdefault(eid, {"h2h": {}, "totals": {}})
        try:
            price = float(r["price"])
        except Exception:
            continue
        if r["market"] == "h2h":
            d["h2h"].setdefault(r["side"], []).append(price)
        elif r["market"] == "totals" and r.get("point") == "2.5":
            d["totals"].setdefault(r["side"], []).append(price)
    # fid -> BSD 队名
    fid_map = {}
    try:
        fm = json.load(io.open(os.path.join(ROOT, "analysis_records", "apifb_fixture_map_emperor_20260826.json"), encoding="utf-8"))["matches"]
        for mm in fm:
            fid_map[int(mm["fixture_id"])] = (mm["target_home"], mm["target_away"])
    except Exception:
        pass
    n = 0
    for m in events:
        fid = None
        for _fid, (_h, _a) in fid_map.items():
            if _h == m["home"] and _a == m["away"]:
                fid = _fid
                break
        if fid is None:
            continue
        d = agg.get("apifb%d" % fid)
        if not d:
            continue
        h2h = d["h2h"]
        if h2h.get("home") and h2h.get("draw") and h2h.get("away"):
            m["h2h"] = {"home": statistics.mean(h2h["home"]), "draw": statistics.mean(h2h["draw"]), "away": statistics.mean(h2h["away"])}
            m.setdefault("books_used", {})["h2h"] = "apifb_avg"
        tt = d["totals"]
        if tt.get("over") and tt.get("under"):
            m["totals"] = {"line": 2.5, "over_price": statistics.mean(tt["over"]), "under_price": statistics.mean(tt["under"])}
            m.setdefault("books_used", {})["totals"] = "apifb_avg(2.5)"
        if "h2h" in m or "totals" in m:
            n += 1
    return n

'''
marker = "def main():"
assert marker in src
src = src.replace(marker, inject_fn + "\n" + marker)
io.open(r"D:\足球分析\_scan_next24h_v2.py", "w", encoding="utf-8").write(src)
print("inject added")
