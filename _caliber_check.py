# -*- coding: utf-8 -*-
import io, csv, sys, os, collections
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
D = os.path.join(ROOT, "data", "raw", "football_data")

files = ["football_data_recent.csv","matches_2015_2025.csv","matches_2023_2024.csv",
         "api_supplement_2024_2025.csv","api_supplement_2025_2026.csv","j1_2026_results.csv",
         "csl_2026_results.csv","supplement_P1_B1.csv","bsd_batch_20260821.csv",
         "supplement_bsd_2026_2027_b1n1p1.csv"]
for _f in sorted(os.listdir(D)):
    if _f.startswith("espn_") and _f.endswith("_results.csv"):
        files.append(os.path.join(D, _f))
    if _f.startswith("footballdata_") and _f.endswith("_results.csv"):
        files.append(os.path.join(D, _f))

targets = {"C1": "中超", "P1": "葡超", "E1": "英冠", "I1": "意甲", "ML": "美职", "AR": "阿甲"}
data = collections.defaultdict(list)  # (div, season) -> [goals...]
for fp in files:
    if not os.path.exists(fp):
        continue
    with io.open(fp, encoding="utf-8", errors="replace") as f:
        for r in csv.DictReader(f):
            div = (r.get("Div") or "").strip()
            if div not in targets:
                continue
            season = (r.get("Season") or r.get("season") or "?").strip()
            try:
                g = int(float(r["FTHG"])) + int(float(r["FTAG"]))
            except Exception:
                continue
            data[(div, season)].append(g)

for div, lg in targets.items():
    print("== %s(%s)" % (lg, div))
    for s in ["2023/2024","2024/2025","2025/2026","2026/2027","2026"]:
        gs = data.get((div, s))
        if gs:
            print("   %s: %3d场 场均%.3f" % (s, len(gs), sum(gs)/len(gs)))
    # 组合口径
    def avg(seasons):
        gs = []
        for s in seasons:
            gs += data.get((div, s), [])
        if not gs:
            return None
        return sum(gs)/len(gs), len(gs)
    for name, seasons in [("近2季(23/24+24/25)", ["2023/2024","2024/2025"]),
                          ("近2季(24/25+25/26)", ["2024/2025","2025/2026"]),
                          ("近2季(24/25+25/26+26)", ["2024/2025","2025/2026","2026"]),
                          ("近2季(24/25+25/26+26/27)", ["2024/2025","2025/2026","2026/2027"]),
                          ("近2季全(24/25+25/26+26+26/27)", ["2024/2025","2025/2026","2026","2026/2027"]),
                          ("仅当前(26)", ["2026"]), ("仅当前(26/27)", ["2026/2027"])]:
        r = avg(seasons)
        if r:
            print("   %s: 场均%.3f (%d场)" % (name, r[0], r[1]))
