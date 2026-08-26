# -*- coding: utf-8 -*-
import sys, glob, io, os
sys.stdout.reconfigure(encoding='utf-8')
kws = ['Al-Fayha','Sheffield','Olimpia','Macara','Macará','LDU','Athletic Club','Novorizontino','Sanluqueno','Cundinamarca','Atlético Nacional','Corinthians','Botafogo','Bradford','Vasco','Santos','Mirassol','America Mineiro','Regatas']
files = []
for pat in ['analysis_records/*direction*.txt','analysis_records/*.txt','analysis_records/scan48h_*_clean.json','analysis_records/2026*.json']:
    files += glob.glob(pat)
files = sorted(set(files))
for fp in files:
    try:
        content = io.open(fp, encoding='utf-8', errors='replace').read()
    except Exception:
        continue
    hits = [k for k in kws if k in content]
    if hits:
        print(os.path.basename(fp), '->', ','.join(hits[:6]))
