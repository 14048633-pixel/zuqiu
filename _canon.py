# -*- coding: utf-8 -*-
"""构建统一队名规范化映射 team_name_canon.json"""
import json, io, pandas as pd
ROOT = r'D:\足球分析'
cfg = json.load(io.open(ROOT + r'\form_phase0\hf_backfill_map.json', encoding='utf-8'))
HF_MAP = cfg['hf_map']
HF_MAP['Exeter City'] = ['Exeter']
HF_MAP['Lincoln City'] = ['Lincoln']
HF_MAP['Fortuna Sittard'] = ['For Sittard', 'Fortuna Sittard']
HF_MAP['NEC Nijmegen'] = ['Nijmegen', 'NEC Nijmegen']
hf_to_canon = {}
for canon, names in HF_MAP.items():
    for n in names:
        hf_to_canon[n] = canon

MX_TO_CANON = {
    'Heidenheim': '1. FC Heidenheim', 'Kaiserslautern': '1. FC Kaiserslautern', 'Nurnberg': '1. FC Nürnberg',
    'Dresden': 'Dynamo Dresden', 'Greuther Furth': 'Greuther Fürth', 'Hertha': 'Hertha Berlin',
    'Karlsruhe': 'Karlsruher SC', 'Darmstadt': 'SV Darmstadt 98',
    'Birmingham': 'Birmingham City', 'Charlton': 'Charlton Athletic', 'Derby': 'Derby County',
    'Norwich': 'Norwich City', 'Preston': 'Preston North End', 'Stoke': 'Stoke City',
    'Swansea': 'Swansea City', 'West Brom': 'West Bromwich Albion', 'West Ham': 'West Ham United',
    'Den Haag': 'ADO Den Haag', 'Utrecht': 'FC Utrecht', 'For Sittard': 'Fortuna Sittard',
    'Nijmegen': 'NEC Nijmegen', 'PSV Eindhoven': 'PSV Eindhoven', 'Cambuur': 'SC Cambuur',
    'Osasuna': 'CA Osasuna', 'Celta': 'Celta Vigo', 'Espanol': 'Espanyol',
    'Santander': 'Real Racing Club de Santander', 'Ceuta': 'AD Ceuta FC', 'Andorra': 'Andorra CF',
    'Burgos': 'Burgos CF', 'Cadiz': 'Cádiz CF', 'Cordoba': 'Córdoba', 'Granada': 'Granada CF',
    'Valladolid': 'Real Valladolid CF', 'Eibar': 'SD Eibar', 'Bolton': 'Bolton Wanderers',
    'Rotherham': 'Rotherham United',
}
out = {'hf_to_canon': hf_to_canon, 'mx_to_canon': MX_TO_CANON}
json.dump(out, io.open(ROOT + r'\form_phase0\team_name_canon.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

back = pd.read_csv(ROOT + r'\data\raw\football_data\hf_2025_26_backfill.csv', low_memory=False)
back['HomeTeam'] = back['HomeTeam'].map(lambda x: hf_to_canon.get(str(x).strip(), str(x).strip()))
back['AwayTeam'] = back['AwayTeam'].map(lambda x: hf_to_canon.get(str(x).strip(), str(x).strip()))
back = back.drop_duplicates(subset=['Date','HomeTeam','AwayTeam'])
back.to_csv(ROOT + r'\data\raw\football_data\hf_2025_26_backfill.csv', index=False, encoding='utf-8-sig')
led = pd.read_csv(ROOT + r'\analysis_records\bet_ledger.csv', encoding='utf-8-sig')
led_teams = set(led['home']) | set(led['away'])
bt = set(back['HomeTeam']) | set(back['AwayTeam'])
print('backfill rows:', len(back), '| 账本命中:', len(led_teams & bt), '/', len(led_teams))
print('未命中:', sorted(led_teams - bt))
