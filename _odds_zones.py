# -*- coding: utf-8 -*-
import csv, collections
rows = list(csv.DictReader(open(r'analysis_records/bet_ledger.csv', encoding='utf-8-sig')))
settled = [r for r in rows if r.get('result') in ('win','lose','push','half')]

def roi(pnl, n): return pnl/max(1,n)*100

print('===== 1X2 主胜 按赔率区间 =====')
g = collections.defaultdict(lambda: [0,0,0.0])
for r in settled:
    if r['bet_name'] == '1X2主胜':
        o = float(r['odds']); n,w,pnl = g[o]
        n+=1; w+=(r['result']=='win'); pnl+=float(r['pnl'] or 0); g[o]=[n,w,pnl]
for o in sorted(g):
    n,w,pnl = g[o]; imp = 1/o*100
    print('  主胜赔率%.2f n=%3d 真实胜率%5.1f%% vs 隐含%5.1f%% 差值%+5.1fpp  ROI%+6.1f%%' % (o,n,w/n*100,imp,w/n*100-imp,roi(pnl,n)))

print('\n===== 1X2 客胜 按赔率区间 =====')
g = collections.defaultdict(lambda: [0,0,0.0])
for r in settled:
    if r['bet_name'] == '1X2客胜':
        o = float(r['odds']); n,w,pnl = g[o]
        n+=1; w+=(r['result']=='win'); pnl+=float(r['pnl'] or 0); g[o]=[n,w,pnl]
for o in sorted(g):
    n,w,pnl = g[o]; imp = 1/o*100
    print('  客胜赔率%.2f n=%3d 真实胜率%5.1f%% vs 隐含%5.1f%% 差值%+5.1fpp  ROI%+6.1f%%' % (o,n,w/n*100,imp,w/n*100-imp,roi(pnl,n)))

print('\n===== 平局 按平局赔率区间 (真实平局率 vs 隐含) =====')
g = collections.defaultdict(lambda: [0,0])
for r in settled:
    if r['bet_name'] == '1X2平局':
        o = float(r['odds'])
        n,d = g[o]; n+=1; d += (r.get('is_draw')=='1' or (r.get('is_draw')=='1'))
        # 用比分判断平局更稳
        sc = r.get('score') or ''
        d = 0
        n,w,pnl = 0,0,0.0
        # 重新组织
for r in settled:
    if r['bet_name'] == '1X2平局':
        o = float(r['odds']); sc = r.get('score') or ''
        isd = 1 if (sc and len(sc.split('-'))==2 and sc.split('-')[0]==sc.split('-')[1]) else 0
        n,w,pnl = g[o] if o in g else [0,0,0.0]
        n+=1; w+=isd; pnl+=float(r['pnl'] or 0); g[o]=[n,w,pnl]
for o in sorted(g):
    n,w,pnl = g[o]; imp = 1/o*100
    print('  平赔%.2f n=%3d 真实平局率%5.1f%% vs 隐含%5.1f%% 差值%+5.1fpp  ROI%+6.1f%%' % (o,n,w/n*100,imp,w/n*100-imp,roi(pnl,n)))

print('\n===== 让球腿 按盘口深度 (赢盘率, 全让球主+客合并, 平手另列) =====')
g = collections.defaultdict(lambda: [0,0,0.0])
for r in settled:
    bn = r['bet_name'] or ''
    if bn.startswith('让球'):
        try: h = float(bn.split('(')[1].split(')')[0])
        except Exception: continue
        key = ('平手' if h==0 else ('受让+%.1f' % h if h>0 else '让球%.1f' % h))
        n,w,pnl = g[key]; n+=1; w+=(r['result'] in ('win','half')); pnl+=float(r['pnl'] or 0); g[key]=[n,w,pnl]
for k in sorted(g, key=lambda x: (x[0]!='平手', x)):
    n,w,pnl = g[k]
    print('  %-8s n=%3d 赢盘率%5.1f%%  ROI%+6.1f%%' % (k,n,w/n*100,roi(pnl,n)))
