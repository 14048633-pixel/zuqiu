# -*- coding: utf-8 -*-
import json, io, sys, collections, re
from collections import defaultdict
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
# 从扫描里统计: 市场盘口主让 vs 客让 的分布, 以及 λ 强弱 vs 盘口强弱一致性
scan = json.load(io.open(r'analysis_records/20260823_scan_upcoming.json', encoding='utf-8'))
c = defaultdict(int)
agree = 0; disagree = 0; n = 0
for m in scan['matches']:
    r = m.get('result') or {}
    bets = r.get('bets') or []
    lam = r.get('lambda') or {}
    lh, la = lam.get('home'), lam.get('away')
    # 从 bets 推断市场盘口: 让球主/客腿的盘口
    hdps = []
    for b in bets:
        mm = re.match(r'让球主\(([+-]?[\d.]+)\)', b.get('name',''))
        if mm: hdps.append(float(mm.group(1)))
    if not hdps or lh is None: continue
    mkt_hdp = hdps[0]  # 主队让球盘
    n += 1
    if mkt_hdp < 0: mkt_side = '主让(市场主强)'
    elif mkt_hdp > 0: mkt_side = '客让(市场客强)'
    else: mkt_side = '平手'
    c[mkt_side] += 1
    if mkt_hdp < 0 and lh >= la: agree += 1
    elif mkt_hdp > 0 and la > lh: agree += 1
    else: disagree += 1
print('市场盘口分布(扫描761场有盘口的):', dict(c))
print('λ强弱与市场盘口一致:', agree, '| 不一致:', disagree, '| 一致率: %.1f%%' % (agree/(agree+disagree)*100))
