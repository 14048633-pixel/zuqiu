import io, sys, glob, json, os
sys.stdout.reconfigure(encoding='utf-8')
fs = sorted(glob.glob('match_package/*.json'))
print('match_package json 数:', len(fs))
j1_hits = 0
lg_count = {}
for f in fs[-40:]:
    try:
        d = json.load(io.open(f, encoding='utf-8'))
    except Exception:
        continue
    # 结构可能是 {id: {...}} 或 list
    if isinstance(d, dict):
        items = d.values() if not any(isinstance(v, (int, str)) for v in list(d.values())[:3]) else [d]
    else:
        items = d
    for it in items:
        if not isinstance(it, dict): continue
        lg = it.get('league') or it.get('lg') or ''
        lg_count[lg] = lg_count.get(lg, 0) + 1
        h = it.get('home') or ''
        if 'J' in str(lg) or 'japan' in str(lg).lower() or 'Marinos' in str(h) or 'Kashima' in str(h):
            j1_hits += 1
print('联赛分布(末40文件):', dict(list(lg_count.items())[:20]))
print('J1相关命中:', j1_hits)
