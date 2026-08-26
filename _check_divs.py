# -*- coding: utf-8 -*-
import io, csv, sys, os, collections
sys.stdout.reconfigure(encoding="utf-8")
D = r"D:\足球分析\data\raw\football_data"
for fn in ["csl_2026_results.csv","supplement_P1_B1.csv","espn_英冠_results.csv","espn_葡超_results.csv","espn_意甲_results.csv","espn_阿甲_results.csv","espn_美职_results.csv","football_data_recent.csv","matches_2023_2024.csv","api_supplement_2024_2025.csv","api_supplement_2025_2026.csv","hf_2025_26_backfill.csv"]:
    p = os.path.join(D, fn)
    if not os.path.exists(p):
        print(fn, "不存在"); continue
    divs = collections.Counter()
    seas = collections.Counter()
    with io.open(p, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            divs[(r.get("Div") or "").strip()] += 1
            seas[(r.get("Season") or r.get("season") or "?").strip()] += 1
    print("== %s: %d行 | Div=%s | Season=%s" % (fn, sum(divs.values()), dict(divs.most_common(8)), dict(seas.most_common(6))))
