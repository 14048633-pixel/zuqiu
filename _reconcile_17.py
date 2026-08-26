# -*- coding: utf-8 -*-
import json, io, re
def norm(s): return re.sub(r'[^a-z0-9]+', '', (s or '').lower())
odds = json.load(io.open(r'D:/足球分析/analysis_records/48h_full_odds_20260817.json', encoding='utf-8'))['rows']
fin = json.load(io.open(r'D:/足球分析/analysis_records/scan48h_0818_finished_check_20260819.json', encoding='utf-8'))
fin = [o for o in fin if o['status'] == 'finished']
def find_row(h, a):
    for r in odds:
        if norm(r.get('home')) == norm(h) and norm(r.get('away')) == norm(a): return r
    for r in odds:
        if norm(r.get('away')) == norm(h) and norm(r.get('home')) == norm(a): return r
    return None
def d1x2_hit(pred, hg, ag):
    if not pred or pred in ('—', ''): return None
    if '主胜' in pred: exp = 'home'
    elif '客胜' in pred: exp = 'away'
    elif '平' in pred: exp = 'draw'
    else: return None
    act = 'draw' if hg == ag else ('home' if hg > ag else 'away')
    return (exp == act, exp, act)
def ou_hit(pred, hg, ag):
    if not pred or pred in ('—', ''): return None
    m = re.search(r'(大|小)2\.5', pred)
    if not m: return None
    exp = 'over' if m.group(1) == '大' else 'under'
    act = 'over' if (hg + ag) > 2.5 else 'under'
    return (exp == act, exp, act)
print('%-38s %-7s %-11s %-4s %-11s %-4s' % ('比赛', '比分', '1X2预测', '果', 'OU预测', '果'))
print('-' * 80)
n1 = n2 = h1 = h2 = 0
for o in fin:
    h, a, lg = o['home'], o['away'], o['league']
    sc = o.get('score')
    hg, ag = sc if sc else (None, None)
    r = find_row(h, a)
    d = r.get('d1x2') if r else None
    ou = r.get('ou') if r else None
    dhit = d1x2_hit(d, hg, ag) if hg is not None else None
    ohit = ou_hit(ou, hg, ag) if hg is not None else None
    if dhit: n1 += 1; h1 += int(dhit[0])
    if ohit: n2 += 1; h2 += int(ohit[0])
    dres = ('OK' if dhit[0] else 'X') if dhit else '-'
    ores = ('OK' if ohit[0] else 'X') if ohit else '-'
    dshow = d if (d and d != '—') else '无预测'
    oshow = ou if (ou and ou != '—') else '无预测'
    score = ('%s-%s' % (hg, ag)) if hg is not None else '-'
    print('%-38s %-7s %-11s %-4s %-11s %-4s' % ((lg + ' ' + h[:13] + 'vs' + a[:13]), score, str(dshow), dres, str(oshow), ores))
print('-' * 80)
print('1X2 对账: %d/%d 命中 | 大小球对账: %d/%d 命中' % (h1, n1, h2, n2))