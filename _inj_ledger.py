import csv, collections, io

p = 'analysis_records/bet_ledger.csv'
rows = []
with open(p, encoding='utf-8-sig', errors='replace') as f:
    for r in csv.DictReader(f):
        rows.append(r)

def cls(row):
    tags = row.get('risk_tags') or ''
    if '伤停' in tags and '纯数据无伤病情报' not in tags:
        return '有伤停报告'
    if '纯数据无伤病情报' in tags:
        return '无伤停'
    if '伤停' in tags:
        return '有伤停(带无情报)'
    return '其他'

settled = [r for r in rows if r.get('status') == '已结算']
groups = collections.defaultdict(list)
for r in settled:
    groups[cls(r)].append(r)

def stats(rs, label):
    n = len(rs)
    if n == 0:
        print(f'{label}: n=0'); return
    win = sum(1 for r in rs if r.get('result') in ('win','half'))
    lose = sum(1 for r in rs if r.get('result') == 'lose')
    push = sum(1 for r in rs if r.get('result') == 'push')
    dec = win + lose
    hit = win/dec*100 if dec else 0
    def fnum(x):
        try: return float(x)
        except: return 0.0
    pnl = sum(fnum(r.get('pnl')) for r in rs)
    roi = pnl/n*100 if n else 0
    print(f'{label}: n={n} 命中={win}/{dec}={hit:.1f}% 走水={push} PnL={pnl:+.1f} ROI={roi:+.1f}%')
    return hit, roi, n

print('== 全部已结算 ==')
for k in ['有伤停报告','无伤停','有伤停(带无情报)','其他']:
    if groups[k]: stats(groups[k], k)

print()
print('== 仅★出单(star>=1 或 ev_tier非空) ==')
star_rs = [r for r in settled if (r.get('star') or '') not in ('','0') or (r.get('ev_tier') or '') != '']
sg = collections.defaultdict(list)
for r in star_rs:
    sg[cls(r)].append(r)
for k in ['有伤停报告','无伤停','有伤停(带无情报)','其他']:
    if sg[k]: stats(sg[k], k)
