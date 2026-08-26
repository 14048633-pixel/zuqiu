# -*- coding: utf-8 -*-
"""对回填文件做 HF队名 -> 账本约定名 重命名(仅账本球队)"""
import pandas as pd, io, json, collections
ROOT = r'D:\足球分析'
cfg = json.load(io.open(ROOT + r'\form_phase0\hf_backfill_map.json', encoding='utf-8'))
HF_MAP = cfg['hf_map']
# 反向: HF名 -> 账本名
rev = {}
for ledger_name, hf_names in HF_MAP.items():
    for hf in hf_names:
        rev[hf] = ledger_name
back = pd.read_csv(ROOT + r'\data\raw\football_data\hf_2025_26_backfill.csv', low_memory=False)
n_before = len(back)
back['HomeTeam'] = back['HomeTeam'].map(lambda x: rev.get(str(x).strip(), str(x).strip()))
back['AwayTeam'] = back['AwayTeam'].map(lambda x: rev.get(str(x).strip(), str(x).strip()))
# 重命名后去重(同一对阵可能因改名重复)
back = back.drop_duplicates(subset=['Date','HomeTeam','AwayTeam'])
back.to_csv(ROOT + r'\data\raw\football_data\hf_2025_26_backfill.csv', index=False, encoding='utf-8-sig')
print('renamed: %d -> %d rows' % (n_before, len(back)))
# 验证: 账本球队在回填中的出现
led = pd.read_csv(ROOT + r'\analysis_records\bet_ledger.csv', encoding='utf-8-sig')
led_teams = set(led['home']) | set(led['away'])
bteams = set(back['HomeTeam']) | set(back['AwayTeam'])
hit = led_teams & bteams
print('账本队数 %d, 回填同名命中 %d' % (len(led_teams), len(hit)))
print('未命中(%d): %s' % (len(led_teams-hit), sorted(list(led_teams-hit))))
