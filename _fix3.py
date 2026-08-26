# -*- coding: utf-8 -*-
import sys, io, json, os, re, unicodedata
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
ROOT = r'D:\足球分析'
def norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', '', s.lower())

ADD = [('Sheffield Wednesday', 'Wolverhampton', '0-2', 'ESPN-EFL'),
       ('Juventude', 'Clube De Regatas Brasil', '2-1', 'ESPN-BR2'),
       ('C\u00facuta Deportivo', 'Alianza Valledupar FC', '1-0', 'ESPN-COL')]

p = os.path.join(ROOT, 'analysis_records', 'results_scan_20260826_final.json')
out = json.load(io.open(p, encoding='utf-8'))
for r in out:
    if r['score']: continue
    for eh, ea, sc, src in ADD:
        if norm(eh) == norm(r['home']) and norm(ea) == norm(r['away']):
            r['score'] = sc; r['status'] = 'post'; r['source'] = src

io.open(p, 'w', encoding='utf-8').write(json.dumps(out, ensure_ascii=False, indent=1))
matched = sum(1 for r in out if r['score'])
print('matched now:', matched, '/', len(out))
print('== missing (no source) ==')
for r in out:
    if not r['score']:
        print('  ', r['ko_bjt'], r['league'], r['home'], 'vs', r['away'])
