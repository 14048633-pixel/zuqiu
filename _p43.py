import json, io, sys, collections
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
d = json.load(io.open(r'analysis_records/pending_43_20260823.json', encoding='utf-8'))
print('keys:', list(d.keys()))
print('note:', d.get('note'))
fs = d.get('final_summary') or {}
print('final_summary:', json.dumps(fs, ensure_ascii=False)[:400])
ms = d.get('matches') or []
print('matches:', len(ms))
if ms:
    print('sample keys:', list(ms[0].keys()))
    c = collections.Counter()
    for m in ms:
        st = (m.get('status') or m.get('result_status') or m.get('result') or '?')
        c[st] += 1
    print('状态分布:', dict(c))
