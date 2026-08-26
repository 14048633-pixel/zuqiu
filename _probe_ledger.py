# -*- coding: utf-8 -*-
import io, csv, sys
sys.stdout.reconfigure(encoding="utf-8")
p = r"D:\足球分析\analysis_records\bet_ledger.csv"
with io.open(p, encoding="utf-8-sig") as f:
    rd = csv.DictReader(f)
    cols = rd.fieldnames
    rows = list(rd)
print("列:", cols)
print("总行:", len(rows))
import collections
print("联赛分布:", collections.Counter((r.get("league") or "?").strip() for r in rows).most_common(25))
print()
print("样例行:")
for k, v in rows[0].items():
    print("  %s = %r" % (k, (v or "")[:80]))
