# -*- coding: utf-8 -*-
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
d = json.load(open('analysis_records/research/tonight37_review_20260821.json', encoding='utf-8'))
# 每场统计有哪些方向腿
n_all=len(d)
n_1x2=0; n_ou=0; n_hc=0; n_star=0; n_drawwarn=0
for m in d:
    if '1X2主' in m or '1X2客' in m: n_1x2+=1
    if any(k.startswith(('小球','大球')) for k in m): n_ou+=1
    if any(k.startswith('让球') for k in m): n_hc+=1
    if m.get('star_leg'): n_star+=1
    if m.get('draw_warn'): n_drawwarn+=1
print('总场次:', n_all)
print('有1X2方向腿:', n_1x2)
print('有大小球方向腿:', n_ou)
print('有让球方向腿:', n_hc)
print('有星级腿:', n_star)
print('平局预警场次:', n_drawwarn)
