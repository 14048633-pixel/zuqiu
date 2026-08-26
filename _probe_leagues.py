# -*- coding: utf-8 -*-
import io, csv, sys, os, collections
sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\足球分析\data\raw\football_data"
target = {"ML":"美职","F2":"法乙","SW":"瑞超","BR":"巴甲"}
files = ["football_data_recent.csv","api_supplement_2024_2025.csv","api_supplement_2025_2026.csv","matches_2023_2024.csv"]
for fn in files:
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        print(fn, "不存在"); continue
    cnt = collections.Counter()
    seas = collections.defaultdict(collections.Counter)
    teams = collections.defaultdict(set)
    with io.open(p, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            div = (r.get("Div") or "").strip()
            if div in target:
                cnt[div] += 1
                s = (r.get("Season") or r.get("season") or "?").strip()
                seas[div][s] += 1
                teams[div].add(r.get("HomeTeam",""))
    print("==", fn)
    for div in target:
        print("  %s(%s): %d场 | 赛季:%s" % (target[div], div, cnt[div], dict(seas[div])))
