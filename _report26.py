# -*- coding: utf-8 -*-
import sys, io, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
out = json.load(io.open('analysis_records/results_scan_20260826_final.json', encoding='utf-8'))
FINAL = ('FT','AET','PEN','post','finished')

def total(r):
    try:
        h, a = r['score'].split('-')
        return int(h) + int(a)
    except Exception:
        return None

def leg_ok(r):
    b = r.get('best')
    if not b or not r['score']: return None
    t = total(r)
    if t is None: return None
    if b.startswith('大'):
        line = float(b[1:])
        return 'win' if t > line else ('push' if t == line else 'lose')
    if b.startswith('小'):
        line = float(b[1:])
        return 'win' if t < line else ('push' if t == line else 'lose')
    if b.startswith('1X2'):
        h, a = r['score'].split('-')
        if '主' in b: return 'win' if int(h) > int(a) else 'lose'
        if '客' in b: return 'win' if int(h) < int(a) else 'lose'
        if '平' in b: return 'win' if int(h) == int(a) else 'lose'
    return None

print('===== BEST 4 对账 =====')
pnl = 0.0; n = 0
for r in sorted(out, key=lambda x: x['ko_bjt']):
    if not r['best']: continue
    ok = leg_ok(r)
    if ok is None:
        print('  %s %s vs %s | %s EV%+.1f | 比分 %s (%s) | 待定' % (r['ko_bjt'], r['home'], r['away'], r['best'], (r['best_ev'] or 0)*100, r['score'] or '-', r['status'] or '-'))
        continue
    n += 1
    net = {'win': 1, 'lose': -1, 'push': 0}[ok]
    pnl += net
    mark = {'win': 'WIN', 'lose': 'LOSE', 'push': 'PUSH'}[ok]
    print('  %s %s vs %s | %s EV%+.1f | %s (总%d) | %s' % (r['ko_bjt'], r['home'], r['away'], r['best'], (r['best_ev'] or 0)*100, r['score'], total(r), mark))
print('  PnL(等额注): %+.2f / %d = ROI %+.1f%%' % (pnl, n, pnl/n*100 if n else 0))

print()
print('===== 全部 68 场结果 =====')
live = 0; miss = 0
for r in sorted(out, key=lambda x: x['ko_bjt']):
    if not r['score']:
        miss += 1
        tag = '无数据'
    elif r['status'] in FINAL:
        tag = '终局'
    else:
        live += 1
        tag = 'LIVE(%s)' % (r['status'] or '?')
    bb = ' BEST:%s' % r['best'] if r['best'] else ''
    print('  %-12s %-6s %-24s vs %-24s %s %s%s' % (r['ko_bjt'], r['league'], (r['home'] or '')[:22], (r['away'] or '')[:22], r['score'] or '----', tag, bb))
print('统计: 终局=%d 进行中=%d 无数据=%d' % (sum(1 for r in out if r['score'] and r['status'] in FINAL), live, miss))
