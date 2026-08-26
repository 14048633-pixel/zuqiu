import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
for f in ('scan24h_analysis_20260823_1824.json',):
    d = json.load(io.open(r'analysis_records/'+f, encoding='utf-8'))
    print(f, 'window:', d.get('window'), 'n:', len(d.get('matches', [])))
    m = d['matches'][0]
    print('keys:', list(m.keys()))
    print(json.dumps({k: m.get(k) for k in ('league','home','away','lambda','direction','best_bet')}, ensure_ascii=False)[:700])
