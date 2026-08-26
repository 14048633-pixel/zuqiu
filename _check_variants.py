# -*- coding: utf-8 -*-
import io, csv, sys, os, unicodedata, collections
sys.stdout.reconfigure(encoding="utf-8")
DATA = r"D:\足球分析\data\raw\football_data"

def norm(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    return "".join(c.lower() for c in s if c.isalnum())

for lg in ["美职", "法乙", "瑞超", "巴甲"]:
    old = os.path.join(DATA, "espn_%s_results.csv" % lg)
    new = os.path.join(DATA, "espn_%s_2024_2025_results.csv" % lg)
    def teams(p):
        out = set()
        with io.open(p, encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                out.add(r["HomeTeam"].strip()); out.add(r["AwayTeam"].strip())
        return out
    t_old, t_new = teams(old), teams(new)
    new_only = sorted(t_new - t_old)
    # 变体检测: 归一化相同但原文不同
    norm_old = collections.defaultdict(list)
    for t in t_old:
        norm_old[norm(t)].append(t)
    variants = []
    for t in new_only:
        cand = norm_old.get(norm(t))
        if cand:
            variants.append((t, cand))
    print("== %s: 新文件队数%d, 2026文件队数%d, 新独有%d, 疑似变体%d" % (lg, len(t_new), len(t_old), len(new_only), len(variants)))
    for t, cand in variants:
        print("   变体: %r -> 2026文件 %r" % (t, cand))
    if not variants:
        print("   新独有样例(升降级):", new_only[:8])
