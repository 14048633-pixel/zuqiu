import io
p = r'_scan_next24h.py'
src = io.open(p, encoding='utf-8').read()
old = """    recs, fs = su.parse_snapshots()
    print("events:", len(recs))"""
new = """    recs, fs = su.parse_snapshots()
    try:
        _m = su.bsd_odds_merge(recs)
        print("BSD consensus 覆盖场次:", _m)
    except Exception as _e:
        print("bsd_odds_merge skip:", _e)
    print("events:", len(recs))"""
c = src.count(old)
print('occurrences:', c)
if c != 1:
    raise SystemExit('mismatch')
io.open(p, 'w', encoding='utf-8').write(src.replace(old, new))
print('patched OK')
