# -*- coding: utf-8 -*-
import csv, io, glob, os

files = sorted(glob.glob(r'data/raw/football_data/espn_*_results.csv'))
out = []
for fp in files:
    lg = os.path.basename(fp).replace('espn_','').replace('_results.csv','')
    rs = list(csv.DictReader(io.open(fp, encoding='utf-8-sig')))
    n=0; hw=0; dr=0; aw=0; hg=0; ag=0
    for r in rs:
        try:
            fh=int(r['FTHG']); fa=int(r['FTAG'])
        except: continue
        n+=1; hg+=fh; ag+=fa
        if fh>fa: hw+=1
        elif fh==fa: dr+=1
        else: aw+=1
    if n < 20: continue
    out.append((lg, n, hw/n*100, dr/n*100, aw/n*100, (hg+ag)/n, hg/n, ag/n))

print('league  n    HW%   DR%   AW%   avg   home   away   HA')
for lg, n, hw, dr, aw, avg, hg, ag in out:
    print('%-6s %4d %5.1f %5.1f %5.1f %5.2f  %4.2f  %4.2f  %4.2f' % (lg, n, hw, dr, aw, avg, hg, ag, hg/ag))
