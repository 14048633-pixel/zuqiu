import io
src = io.open(r"D:\足球分析\_scan_next24h_v2.py", encoding="utf-8").read()
old = """    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260826_0000.json"), encoding="utf-8"))["matches"]
    team_stats, lavg, index = su.load_team_stats()
    # 构造 events
    events = []
    for m in lst:
        lg = LG_MAP.get(m.get("league")) or m.get("league") or "未知"
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        events.append({
            "id": m["id"], "lg": lg, "league": lg, "ct": ct, "home": m["home"], "away": m["away"],
            "snap": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "odds": collections.defaultdict(list),
        })"""
new = """    lst = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_20260826_0000.json"), encoding="utf-8"))["matches"]
    team_stats, lavg, index = su.load_team_stats()
    # 从 match_package 读真实联赛名(BSD detail), 映射为系统认识键
    def _pkg_league(mid):
        fp = os.path.join(ROOT, "analysis_records", "match_package", "%d.json" % mid)
        try:
            return json.load(io.open(fp, encoding="utf-8")).get("league")
        except Exception:
            return None
    events = []
    for m in lst:
        lg = LG_MAP.get(_pkg_league(m["id"])) or m.get("league") or "未知"
        try:
            ct = datetime.fromisoformat(m["ct"].replace("Z", "+00:00"))
        except Exception:
            continue
        events.append({
            "id": m["id"], "lg": lg, "league": lg, "ct": ct, "home": m["home"], "away": m["away"],
            "snap": NOW.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "odds": collections.defaultdict(list),
        })"""
assert old in src
src = src.replace(old, new)
io.open(r"D:\足球分析\_scan_next24h_v2.py", "w", encoding="utf-8").write(src)
print("patched")
