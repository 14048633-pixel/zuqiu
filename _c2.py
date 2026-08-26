import csv, io, sys, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
rows = list(csv.DictReader(io.open(r'analysis_records/bet_ledger.csv', encoding='utf-8-sig')))
ou = [r for r in rows if (r.get('bet_name') or '').startswith(('大','小')) and r.get('home_score') not in (None,'')]
# 只保留已结算
ou = [r for r in ou if r.get('status')=='已结算']
def parse(n):
    m = re.match(r'^(大|小)([\d.]+)', n)
    return (m.group(1), float(m.group(2))) if m else None
groups = defaultdict(lambda: {'n':0,'win':0,'half':0,'push':0,'lose':0,'tot':0.0,'goals':0.0,'big_n':0,'small_n':0})
for r in ou:
    p = parse(r.get('bet_name',''))
    if not p: continue
    side, line = p
    lg = r.get('league','?')
    g = groups[lg]
    g['n'] += 1
    res = r.get('result','')
    g['win'] += res=='win'; g['half'] += res=='half'; g['push'] += res=='push'; g['lose'] += res=='lose'
    try:
        h = int(r.get('home_score')); a = int(r.get('away_score'))
    except: continue
    g['goals'] += h + a
    g['tot'] += 1
    if side=='大': g['big_n'] += 1
    else: g['small_n'] += 1
print('%-6s %4s %5s %5s %4s %5s  %8s  %6s %6s' % ('联赛','场','中','半','走','错','命中率','均进球','大:小'))
rows_out = []
for lg, g in groups.items():
    hit = (g['win'] + g['half']*0.5 + g['push']*0) / g['n'] * 100
    avg = g['goals'] / g['tot']
    rows_out.append((lg, g, hit, avg))
for lg, g, hit, avg in sorted(rows_out, key=lambda x: x[2]):
    print('%-6s %4d %5d %5d %4d %5d  %7.1f%%  %6.2f  %3d:%d' % (lg, g['n'], g['win'], g['half'], g['push'], g['lose'], hit, avg, g['big_n'], g['small_n']))
