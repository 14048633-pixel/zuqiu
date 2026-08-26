import csv, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
rows = list(csv.DictReader(io.open(r"D:\足球分析\analysis_records\bet_ledger.csv", encoding='utf-8-sig')))
new = [r for r in rows if r['src'] and '20260825_34场' in r['src']]
print("== 方向参考 22 场 ==")
for r in new:
    if r['src'] == '20260825_34场_方向参考':
        print(f"  {r['ko' if False else 'kickoff'][:16]} {r['league']:<8} {r['home'][:16]:18} vs {r['away'][:16]:18} {r['bet_name']:12} odds={r['odds']} {r['result']:5} pnl={float(r['pnl']):+.2f}")
print()
print("== 否决 5 场 (方向若打) ==")
for r in new:
    if r['src'] == '20260825_34场_否决':
        print(f"  {r['league']:<8} {r['home'][:16]:18} vs {r['away'][:16]:18} {r['bet_name']:12} odds={r['odds']} {r['result']:5} pnl={float(r['pnl']):+.2f}")
