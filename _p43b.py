import json, io, sys, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d = json.load(io.open(r'analysis_records/pending_43_20260823.json', encoding='utf-8'))
ms = d['matches']
c = collections.Counter((m.get('final_status') or '?') for m in ms)
print('final_status:', dict(c))
print()
for m in ms:
    fs = m.get('final_status')
    if fs != 'settled':
        print('非settled:', m.get('ct'), m.get('league'), m.get('home'), 'vs', m.get('away'), '| final_status=', fs, '| score=', m.get('score'), '| settle=', m.get('settle_result'))
