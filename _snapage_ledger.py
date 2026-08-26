import csv, collections

p = 'analysis_records/bet_ledger.csv'
rows = []
with open(p, encoding='utf-8-sig', errors='replace') as f:
    for r in csv.DictReader(f):
        rows.append(r)
settled = [r for r in rows if r.get('status') == '已结算']

def fnum(x):
    try: return float(x)
    except: return 0.0

def bucket(r):
    s = r.get('snap_age_h') or ''
    try: v = float(s)
    except: return None
    if v < 3: return '临场 <3h'
    if v < 6: return '3~6h'
    if v < 12: return '6~12h'
    return '>12h(过期)'

def stats(rs, label):
    n = len(rs)
    if n == 0:
        print(f'{label:16s} n=0'); return
    win = sum(1 for r in rs if r.get('result') in ('win','half'))
    lose = sum(1 for r in rs if r.get('result') == 'lose')
    push = sum(1 for r in rs if r.get('result') == 'push')
    dec = win + lose
    hit = win/dec*100 if dec else 0
    pnl = sum(fnum(r.get('pnl')) for r in rs)
    roi = pnl/n*100 if n else 0
    veto = sum(1 for r in rs if (r.get('veto') or '') == '1')
    print(f'{label:16s} n={n:4d} 命中={win:3d}/{dec:<4d}={hit:5.1f}% 走水={push:2d} PnL={pnl:+7.2f} ROI={roi:+6.1f}% 其中否决={veto}')

print('== 全部已结算 按快照距开赛 ==')
g = collections.defaultdict(list)
for r in settled:
    b = bucket(r)
    if b: g[b].append(r)
for k in ['临场 <3h','3~6h','6~12h','>12h(过期)']:
    stats(g.get(k, []), k)

print()
print('== 仅未被否决(有效盘口) ==')
nv = [r for r in settled if (r.get('veto') or '') != '1']
g2 = collections.defaultdict(list)
for r in nv:
    b = bucket(r)
    if b: g2[b].append(r)
for k in ['临场 <3h','3~6h','6~12h','>12h(过期)']:
    stats(g2.get(k, []), k)

print()
print('== 仅★出单 按快照年龄 ==')
s_ = [r for r in settled if (r.get('star') or '') not in ('','0')]
g3 = collections.defaultdict(list)
for r in s_:
    b = bucket(r)
    if b: g3[b].append(r)
for k in ['临场 <3h','3~6h','6~12h','>12h(过期)']:
    stats(g3.get(k, []), k)
