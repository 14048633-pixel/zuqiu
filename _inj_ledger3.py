import csv, collections

p = 'analysis_records/bet_ledger.csv'
rows = []
with open(p, encoding='utf-8-sig', errors='replace') as f:
    for r in csv.DictReader(f):
        rows.append(r)
settled = [r for r in rows if r.get('status') == '已结算']

def has_inj(r): return '伤停' in (r.get('risk_tags') or '')
def fnum(x):
    try: return float(x)
    except: return 0.0

def stats(rs):
    n = len(rs)
    win = sum(1 for r in rs if r.get('result') in ('win','half'))
    lose = sum(1 for r in rs if r.get('result') == 'lose')
    dec = win + lose
    hit = win/dec*100 if dec else 0
    pnl = sum(fnum(r.get('pnl')) for r in rs)
    roi = pnl/n*100 if n else 0
    return n, hit, roi

by_league = collections.defaultdict(lambda: {'inj': [], 'noinj': []})
for r in settled:
    lg = r.get('league') or ''
    (by_league[lg]['inj'] if has_inj(r) else by_league[lg]['noinj']).append(r)

print(f"{'联赛':8s} | {'有伤停 n/命中/ROI':28s} | {'无伤停 n/命中/ROI':28s}")
for lg, g in sorted(by_league.items(), key=lambda kv: -(len(kv[1]['inj'])+len(kv[1]['noinj']))):
    if len(g['inj'])+len(g['noinj']) < 20: continue
    ni, hi, ri = stats(g['inj']) if g['inj'] else (0,0,0)
    nn, hn, rn = stats(g['noinj']) if g['noinj'] else (0,0,0)
    print(f"{lg:8s} | 有伤停 n={ni:3d} {hi:5.1f}% {ri:+6.1f}%    | 无伤停 n={nn:3d} {hn:5.1f}% {rn:+6.1f}%")
