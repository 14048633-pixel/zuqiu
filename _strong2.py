# -*- coding: utf-8 -*-
import json, io, sys, collections, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
recs = json.load(io.open(r'analysis_records/20260824_stage300_review.json', encoding='utf-8'))
lam_map = {}
def load_lam(f, is_result=False):
    try: d = json.load(io.open(f, encoding='utf-8'))
    except Exception: return
    for m in d.get('matches', []):
        r = m.get('result') if is_result else m
        if not r: r = m
        lam = (r.get('lambda') or {})
        h, a, lg = m.get('home'), m.get('away'), m.get('league')
        if h and a and lam.get('home') is not None:
            lam_map[(lg, h, a)] = (lam.get('home'), lam.get('away'))
for f, ir in ((r'analysis_records/20260815_scan_upcoming.json', False),
              (r'analysis_records/20260816_scan_upcoming.json', False),
              (r'analysis_records/20260817_scan_upcoming.json', False),
              (r'analysis_records/20260821_scan_upcoming.json', False),
              (r'analysis_records/20260823_scan_upcoming.json', False),
              (r'analysis_records/scan24h_analysis_20260822_2136.json', False),
              (r'analysis_records/scan24h_analysis_20260823_1824.json', True),
              (r'analysis_records/scan24h_analysis_20260822_0139.json', False),
              (r'analysis_records/scan24h_analysis_20260822_0141.json', False),
              (r'analysis_records/scan24h_analysis_20260822_2046.json', False)):
    load_lam(f, ir)
G = defaultdict(lambda: {'n':0,'w':0,'pnl':0.0})
def hit(res): return {'win':1,'half':0.5,'push':0,'lose':0}.get(res,0)
n_lambda = n_total = 0
for r in recs:
    b = r['bet']
    if not b.startswith('让球'): continue
    n_total += 1
    lam = lam_map.get((r['lg'], r['h'], r['a']))
    if not lam: continue
    n_lambda += 1
    lh, la = lam
    m = re.match(r'让球(主|客)\(([+-]?[\d.]+)\)', b)
    if not m: continue
    side, hdp = m.group(1), float(m.group(2))
    fav_home = lh >= la
    if side == '主':
        if hdp < 0: group = '主让-号 主强' if fav_home else '主让-号 客强'
        else: group = '主受+号 主强' if fav_home else '主受+号 客强'
    else:
        if hdp < 0: group = '客让-号 主强' if fav_home else '客让-号 客强'
        else: group = '客受+号 主强' if fav_home else '客受+号 客强'
    g = G[group]; g['n'] += 1; g['w'] += hit(r['res']); g['pnl'] += r['pnl']
print('让球总 %d, 有λ %d' % (n_total, n_lambda))
tot = sum(g['n'] for g in G.values())
print('分组覆盖:', tot)
print()
print('%-16s %4s %6s %8s' % ('分组','场','命中','ROI'))
for k, g in sorted(G.items(), key=lambda x: -x[1]['n']):
    print('%-16s %4d %5.1f%% %+7.1f%%' % (k, g['n'], g['w']/g['n']*100, g['pnl']/g['n']*100))
# 强弱一致 vs 不一致汇总
cons = defaultdict(lambda: {'n':0,'w':0,'pnl':0.0})
for r in recs:
    b = r['bet']
    if not b.startswith('让球'): continue
    lam = lam_map.get((r['lg'], r['h'], r['a']))
    if not lam: continue
    m = re.match(r'让球(主|客)\(([+-]?[\d.]+)\)', b)
    if not m: continue
    side, hdp = m.group(1), float(m.group(2))
    fav_home = lam[0] >= lam[1]
    if side=='主': agree = (hdp<0)==fav_home
    else: agree = (hdp<0)==(not fav_home)
    key = '方向与强弱一致' if agree else '方向与强弱相反'
    g = cons[key]; g['n']+=1; g['w']+=hit(r['res']); g['pnl']+=r['pnl']
print()
for k, g in cons.items():
    print('%-18s %4d 命中率%5.1f%% ROI%+6.1f%%' % (k, g['n'], g['w']/g['n']*100, g['pnl']/g['n']*100))
