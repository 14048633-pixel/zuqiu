import io
p = r"_replay_adj.py"
src = io.open(p, encoding="utf-8").read()
src = src.replace(
    """def find_score(scores, lg, h, a, kickoff):
    lst = scores.get((lg, _norm(h), _norm(a)))
    if not lst:
        return None
    if len(lst) == 1:
        return lst[0][1], lst[0][2]
    kd = kickoff.date() if isinstance(kickoff, datetime) else None
    best = None; best_d = None
    for ct_s, hg, ag in lst:
        d = None
        for fmt in ("%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z", "%Y-%m-%d %H:%M:%S+00:00"):
            try:
                d = datetime.strptime(ct_s.replace("Z", "+00:00"), fmt).date()
                break
            except Exception:
                pass
        if d is None and kd is not None:
            continue
        dist = abs((d - kd).days) if d and kd else 0
        if best_d is None or dist < best_d:
            best_d = dist; best = (hg, ag)
    return best""",
    """def find_score(scores, lg, h, a, kickoff):
    lst = scores.get((lg, _norm(h), _norm(a)))
    if not lst:
        return None
    kd = kickoff.date() if isinstance(kickoff, datetime) else None
    def _d(ct_s):
        for fmt in ("%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d %H:%M:%S%z"):
            try:
                return datetime.strptime(ct_s.replace("Z", "+00:00"), fmt).date()
            except Exception:
                pass
        return None
    dated = [x for x in lst if _d(x[0]) is not None]
    # 重复文件(ct为空)与唯一值直接取首条
    if len(dated) == 0 or len(lst) == 1:
        return lst[0][1], lst[0][2]
    best = None; best_d = None
    for ct_s, hg, ag in lst:
        d = _d(ct_s)
        if d is None:
            continue
        dist = abs((d - kd).days) if kd else 0
        if best_d is None or dist < best_d:
            best_d = dist; best = (hg, ag)
    if best is None:
        return lst[0][1], lst[0][2]
    return best""")
io.open(p, "w", encoding="utf-8").write(src)
print("patched find_score")
