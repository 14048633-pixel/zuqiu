# -*- coding: utf-8 -*-
import re, io as _io
def io_text(p): return _io.open(p, encoding='utf-8').read()
def norm(s): return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
rows = []
for line in io_text('D:/足球分析/analysis_records/48h_23_table_20260818.md').splitlines():
    if not line.startswith('| 08-'): continue
    c = [x.strip() for x in line.strip('|').split('|')]
    rows.append({'ko': c[0], 'league': c[1], 'match': c[2], 'd1x2': c[3], 'handi': c[4], 'ou': c[5], 'model': c[6], 'star': c[7]})
settle = {}
for line in io_text('D:/足球分析/analysis_records/settle_48h_20260818.md').splitlines():
    if not line.startswith('| 08-'): continue
    c = [x.strip() for x in line.strip('|').split('|')]
    settle[norm(c[2])] = {'score': c[3], 'd_hit': c[6], 'ou_hit': c[8], 'm_hit': c[10]}
ucl = {norm('GNK Dinamo Zagreb vs Viking FK'): (2,2), norm('Fenerbahçe vs Olympique Lyonnais'): (1,1), norm('Levski Sofia vs AEK Athens'): (0,0)}
def hit_d(pred, hg, ag):
    if '主胜' in pred: exp='H'
    elif '客胜' in pred: exp='A'
    elif '平' in pred: exp='D'
    else: return '-'
    act = 'D' if hg==ag else ('H' if hg>ag else 'A')
    return 'OK' if exp==act else 'X'
def hit_ou(pred, hg, ag):
    m = re.search(r'(大|小)([\d.]+)', pred)
    if not m: return '-'
    line = float(m.group(2)); tot = hg+ag
    act = 'over' if tot>line else 'under'
    exp = 'over' if m.group(1)=='大' else 'under'
    return 'OK' if exp==act else 'X'
def hit_model(pred, hg, ag):
    n = pred.replace(' ', '')
    m = re.match(r'让球主\(([+-][\d.]+)\)', n)
    if m:
        hdp = float(m.group(1)); d = (hg+hdp)-ag
        return 'OK' if d>1e-9 else ('P' if abs(d)<=1e-9 else 'X')
    m = re.match(r'让球客\(([+-][\d.]+)\)', n)
    if m:
        hdp = float(m.group(1)); d = hg-(ag+hdp)
        return 'OK' if d<-1e-9 else ('P' if abs(d)<=1e-9 else 'X')
    m = re.match(r'(大|小)([\d.]+)', n)
    if m:
        line=float(m.group(2)); tot=hg+ag
        if m.group(1)=='大': return 'OK' if tot>line else ('P' if abs(tot-line)<1e-9 else 'X')
        return 'OK' if tot<line else ('P' if abs(tot-line)<1e-9 else 'X')
    return '-'
print('%-3s %-32s %-6s %-9s %-3s %-9s %-3s %-16s %-3s' % ('#','比赛','比分','1X2','D','大小球','O','模型腿','M'))
print('-'*96)
s1=[0,0]; s2=[0,0]; s3=[0,0]
for i, r in enumerate(rows, 1):
    k = norm(r['match'])
    if k in settle:
        hg,ag = map(int, settle[k]['score'].split('-'))
        d,o,m = settle[k]['d_hit'], settle[k]['ou_hit'], settle[k]['m_hit']
    elif k in ucl:
        hg,ag = ucl[k]
        d = hit_d(r['d1x2'], hg, ag); o = hit_ou(r['ou'], hg, ag); m = hit_model(r['model'], hg, ag)
    else:
        sc='?'; d=o=m='-'; hg=ag=None
    for s, hit in ((s1,d),(s2,o),(s3,m)):
        if hit=='OK': s[0]+=1
        if hit in ('OK','X'): s[1]+=1
    print('%-3d %-32s %-6s %-9s %-3s %-9s %-3s %-16s %-3s' % (i, r['match'][:30], ('%d-%d'%(hg,ag) if hg is not None else '?'), r['d1x2'], d, r['ou'], o, r['model'], m))
print('-'*96)
n=len(rows)
print('1X2: %d/%d = %.1f%% | 大小球: %d/%d = %.1f%% | 模型腿: %d/%d = %.1f%%' % (s1[0],s1[1],100.0*s1[0]/max(s1[1],1), s2[0],s2[1],100.0*s2[0]/max(s2[1],1), s3[0],s3[1],100.0*s3[0]/max(s3[1],1)))