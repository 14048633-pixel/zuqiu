import csv, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
rows = list(csv.DictReader(io.open(r"D:\足球分析\analysis_records\bet_ledger.csv", encoding='utf-8-sig')))
new = [r for r in rows if r['src'] and '20260825_34场' in r['src']]
print("本次入账行数:", len(new))
from collections import Counter
print()
print("== 按 src 分组 ==")
for src in ['20260825_34场_BEST', '20260825_34场_方向参考', '20260825_34场_否决']:
    g = [r for r in new if r['src'] == src]
    if not g: continue
    c = Counter(r['result'] for r in g)
    pnl = sum(float(r['pnl']) for r in g)
    rets = sum(float(r['ret']) for r in g)
    print(f"{src}: {len(g)} 场 | 结果 {dict(c)} | PnL {pnl:+.2f} | ROI {pnl/len(g)*100:+.1f}%")
print()
print("== BEST 明细 ==")
for r in new:
    if r['src'] == '20260825_34场_BEST':
        print(f"  {r['league']:<6} {r['home'][:18]:20} vs {r['away'][:18]:20} {r['bet_name']:8} odds={r['odds']} {r['result']:5} pnl={r['pnl']}")
print()
print("== 方向参考 明细 ==")
for r in new:
    if r['src'] in ('20260825_34场_方向参考', '20260825_34场_否决'):
        print(f"  {r['league']:<8} {r['home'][:18]:20} vs {r['away'][:18]:20} {r['bet_name']:12} odds={r['odds']} {r['result']:5} pnl={r['pnl']:+.2f} [{r['status']}]")
