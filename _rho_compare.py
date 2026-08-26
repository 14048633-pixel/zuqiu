# -*- coding: utf-8 -*-
import sys, io, json, csv, glob, os
sys.path.insert(0, r'src/models')
from poisson_lambda import dixon_coles_prob

# 实际统计
files = sorted(glob.glob(r'data/raw/football_data/espn_*_results.csv'))
actual = {}
for fp in files:
    lg = os.path.basename(fp).replace('espn_','').replace('_results.csv','')
    rs = list(csv.DictReader(io.open(fp, encoding='utf-8-sig')))
    n=0; hw=0; dr=0; aw=0
    for r in rs:
        try: fh=int(r['FTHG']); fa=int(r['FTAG'])
        except: continue
        n+=1
        if fh>fa: hw+=1
        elif fh==fa: dr+=1
        else: aw+=1
    if n>=20: actual[lg]=(n,hw/n*100,dr/n*100,aw/n*100)

# 配置
cal = json.load(io.open(r'strategy_data/league_calib.json', encoding='utf-8'))['leagues']

name_map = {'英超':'英超','西甲':'西甲','德甲':'德甲','意甲':'意甲','法甲':'法甲','英冠':'英冠','德乙':'德乙','荷甲':'荷甲','西乙':'西乙','J1':'J1','中超':'中超','葡超':'葡超','比甲':'比甲','英乙':'英乙','瑞超':'瑞超','挪超':'挪超','巴甲':'巴甲','阿甲':'阿甲','美职':'美职','土超':'土超','墨超':'墨超','智利甲':'智利甲','丹超':'丹超','意乙':'意乙','法乙':'法乙'}

print('league  actual(H/D/A)      model(H/D/A)        A-HW   A-DR   A-AW')
for lg, (n, ah, ad, aa) in sorted(actual.items(), key=lambda x: x[1][1], reverse=True):
    cfg = cal.get(name_map.get(lg))
    if not cfg: continue
    avg_atk = cfg['league_avg']/2.0
    lh = avg_atk*cfg['home']
    la = avg_atk*cfg['away']
    sp, mp = dixon_coles_prob(lh, la, cfg['rho'])
    mh, md, ma = mp['win']*100, mp['draw']*100, mp['lose']*100
    print('%-4s %4d %5.1f %5.1f %5.1f | %5.1f %5.1f %5.1f | %+5.1f %+5.1f %+5.1f' % (lg, n, ah, ad, aa, mh, md, ma, ah-mh, ad-md, aa-ma))
