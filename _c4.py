import json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
for f in ('scan24h_analysis_20260822_0139.json','scan24h_analysis_20260822_2136.json','scan24h_analysis_20260823_1824.json','pending_43_20260823.json'):
    try:
        d = json.load(io.open(r'analysis_records/'+f, encoding='utf-8'))
        if isinstance(d, dict):
            print(f, 'keys:', list(d.keys())[:10])
            for k in list(d.keys())[:3]:
                v = d[k]
                if isinstance(v, list) and v:
                    print('   sample:', json.dumps(v[0], ensure_ascii=False)[:400])
                    break
    except Exception as e:
        print(f, 'ERR', e)
