# -*- coding: utf-8 -*-
import sys, re
sys.stdout.reconfigure(encoding='utf-8')
txt = open('analysis_records/tonight37_ledger_detail.txt', encoding='utf-8').read()
blocks = txt.split('▶ ')
n=0; n_x2=0; n_ou=0; n_hc=0; n_hc_real=0; n_hc_sim=0; n_star=0; n_neg=0
neg_matches=[]
for b in blocks[1:]:
    lines=[l for l in b.strip().split('\n') if l.strip()]
    n+=1
    has_x2=False; has_ou=False; has_hc=False; has_hc_real=False; has_hc_sim=False; has_star=False
    for l in lines[1:]:
        if re.match(r'\s+1X2', l): has_x2=True
        if re.match(r'\s+(小球|大球)\(', l):
            has_ou=True
            if '★' in l: has_star=True
        if re.match(r'\s+让球', l):
            has_hc=True
            if '推演' in l: has_hc_sim=True
            else: has_hc_real=True
        if '否决' in l: has_neg=True
    if has_x2: n_x2+=1
    if has_ou: n_ou+=1
    if has_hc: n_hc+=1
    if has_hc_real: n_hc_real+=1
    if has_hc_sim: n_hc_sim+=1
    if has_star: n_star+=1
print('总场次:', n)
print('有1X2腿(实盘赔率):', n_x2)
print('有大小球腿(实盘赔率):', n_ou)
print('有让球腿:', n_hc, '| 其中实盘:', n_hc_real, '| 纯推演:', n_hc_sim)
print('有星级腿:', n_star)
