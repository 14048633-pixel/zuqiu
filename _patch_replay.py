import io, re
p = r"_replay_adj.py"
src = io.open(p, encoding="utf-8").read()

# 1) build_team_stats: fix date compare
src = src.replace(
    """                if cutoff is not None:
                    if d is None:
                        if season in ("2026", "2026/2027", "2025/2026"):
                            continue
                    elif d >= cutoff:
                        continue""",
    """                if cutoff is not None:
                    if d is None:
                        if season in ("2026", "2026/2027", "2025/2026"):
                            continue
                    elif d.date() > cutoff.date():
                        continue""")

# 2) add pre-match snapshot temp file builder + module cache, patch run()
src = src.replace(
    "def run():\n    su.recent_league_avg = lambda: {}   # 关闭基准偏差平移, A/B 都用配置原值\n    scores = load_scores()\n    recs, fs = su.parse_snapshots()",
    """_TS_CACHE = {}
def get_team_stats(mode, cutoff):
    dkey = cutoff.date().isoformat()
    key = (mode, dkey)
    if key in _TS_CACHE:
        return _TS_CACHE[key]
    ts, lavg, index = build_team_stats(cutoff=cutoff, include_espn_2024=(mode == "new"))
    _TS_CACHE[key] = (ts, lavg, index)
    return ts, lavg, index

def build_prematch_snapshots():
    src_path = os.path.join(ROOT, "prediction_v2", "output", "odds_snapshots", "snapshots.csv")
    tmp = os.path.join(ROOT, "_snap_prematch.csv")
    def _pt(s):
        try:
            return datetime.fromisoformat(s.replace("Z", "+00:00"))
        except Exception:
            return None
    keep = 0; drop = 0
    with io.open(src_path, "r", encoding="utf-8") as fin, io.open(tmp, "w", encoding="utf-8", newline="") as fout:
        rd = csv.reader(fin)
        wr = csv.writer(fout)
        hdr = next(rd)
        wr.writerow(hdr)
        for x in rd:
            if not x:
                continue
            st = _pt(x[0]); ct = _pt(x[3])
            if st is not None and ct is not None and st > ct:
                drop += 1
                continue
            wr.writerow(x)
            keep += 1
    print("prematch rows kept=%d dropped=%d" % (keep, drop))
    return tmp

def run():
    su.recent_league_avg = lambda: {}   # 关闭基准偏差平移, A/B 都用配置原值
    scores = load_scores()
    _tmp = build_prematch_snapshots()
    recs, fs = su.parse_snapshots(_tmp)""")

# 3) use cached team stats inside loop
src = src.replace(
    "            patch_cal(mode)\n            cutoff = m[\"ct\"]\n            ts, lavg, index = build_team_stats(cutoff=cutoff, include_espn_2024=(mode == \"new\"))",
    "            patch_cal(mode)\n            cutoff = m[\"ct\"]\n            ts, lavg, index = get_team_stats(mode, cutoff)")

io.open(p, "w", encoding="utf-8").write(src)
print("patched ok")
