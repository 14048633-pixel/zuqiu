import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d = json.load(io.open(r'analysis_records/scan24h_analysis_20260822_2136.json', encoding='utf-8'))
m = d['matches'][0]
print('match keys:', list(m.keys()))
print(json.dumps({k: m.get(k) for k in ('league','home','away','kickoff','lambda','direction')}, ensure_ascii=False)[:600])
# 找大小球相关字段
for k in m.keys():
    if 'ball' in k or 'over' in k or 'ou' in k.lower() or 'bet' in k:
        print('FIELD:', k, '=', json.dumps(m.get(k), ensure_ascii=False)[:300])
