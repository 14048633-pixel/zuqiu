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

def stats(rs, label):
    n = len(rs)
    win = sum(1 for r in rs if r.get('result') in ('win','half'))
    lose = sum(1 for r in rs if r.get('result') == 'lose')
    push = sum(1 for r in rs if r.get('result') == 'push')
    dec = win + lose
    hit = win/dec*100 if dec else 0
    pnl = sum(fnum(r.get('pnl')) for r in rs)
    roi = pnl/n*100 if n else 0
    print(f'{label:14s} n={n:4d} 命中={win:3d}/{dec:<4d}={hit:5.1f}% 走水={push:2d} PnL={pnl:+7.2f} ROI={roi:+6.1f}%')

print('== 全部已结算 831 ==')
stats([r for r in settled if has_inj(r)], '有伤停(>=3人)')
stats([r for r in settled if not has_inj(r)], '无伤停/无数据')

print()
print('== 按方向 ==')
for d, name in [(('小','大'), '大小球'), (('让球',), '让球'), (('1X2',), '1X2')]:
    print('--', name, '--')
    g = [r for r in settled if any(r.get('bet_name','').startswith(x) for x in d)]
    stats([r for r in g if has_inj(r)], '有伤停')
    stats([r for r in g if not has_inj(r)], '无伤停')

print()
print('== 仅★出单(star>=1) ==')
s = [r for r in settled if (r.get('star') or '') not in ('','0')]
stats([r for r in s if has_inj(r)], '有伤停')
stats([r for r in s if not has_inj(r)], '无伤停')

print()
print('== 仅EV>=5%腿 ==')
e5 = [r for r in settled if fnum(r.get('ev')) >= 0.05]
stats([r for r in e5 if has_inj(r)], '有伤停')
stats([r for r in e5 if not has_inj(r)], '无伤停')

print()
print('== 大小球/让球 有伤停 vs 无伤停 明细 ==')
for name in ['大2.50','小2.50']:
    g = [r for r in settled if r.get('bet_name')==name]
    stats([r for r in g if has_inj(r)], f'有伤停[{name}]')
    stats([r for r in g if not has_inj(r)], f'无伤停[{name}]')
