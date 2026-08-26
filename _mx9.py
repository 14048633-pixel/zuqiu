# -*- coding: utf-8 -*-
import pandas as pd, io
mx = pd.read_csv('data/raw/football_data/matches_with_xg.csv', low_memory=False, usecols=['HomeTeam','AwayTeam']).dropna(subset=['HomeTeam'])
tmx = sorted(set(mx['HomeTeam'].astype(str)) | set(mx['AwayTeam'].astype(str)))
led = pd.read_csv('analysis_records/bet_ledger.csv', encoding='utf-8-sig')
led_9 = ['1. FC Heidenheim','1. FC Kaiserslautern','1. FC Nürnberg','Dynamo Dresden','Greuther Fürth','Hertha Berlin','Karlsruher SC','SV Darmstadt 98',
 'Birmingham City','Bristol City','Burnley','Charlton Athletic','Derby County','Middlesbrough','Millwall','Norwich City','Portsmouth','Preston North End','Queens Park Rangers','Sheffield United','Southampton','Stoke City','Swansea City','Watford','West Bromwich Albion','West Ham United',
 'ADO Den Haag','AZ Alkmaar','Ajax','Excelsior','FC Utrecht','Feyenoord','Fortuna Sittard','Go Ahead Eagles','Groningen','Heerenveen','NEC Nijmegen','PSV','SC Cambuur','Willem II',
 'CA Osasuna','Celta Vigo','Espanyol','Levante','Real Racing Club de Santander','Villarreal',
 'AD Ceuta FC','Albacete','Andorra CF','Burgos CF','Cádiz CF','Córdoba','Granada CF','Las Palmas','Mallorca','Oviedo','Real Valladolid CF','SD Eibar','Tenerife',
 'Bolton Wanderers','Exeter City','Lincoln City','Port Vale','Rotherham United']
import difflib
out = io.open('_mx9.txt','w',encoding='utf-8')
for t in led_9:
    if t in tmx:
        out.write('%-32s = %s (EXACT)\n' % (t, t))
        continue
    best=None;bs=0
    for x in tmx:
        r = difflib.SequenceMatcher(None, t.lower(), x.lower()).ratio()
        if r>bs: bs=r; best=x
    out.write('%-32s -> %-28s (%.2f)\n' % (t, best, bs))
out.close()
print('ok')
