import io
# --- patch 1: scan_upcoming.py 标签语义 ---
p = r'prediction_v2\scan_upcoming.py'
src = io.open(p, encoding='utf-8').read()
old = """    if not HAS_INTEL:
        risk_tags.append("纯数据无伤病情报")"""
new = """    if not HAS_INTEL:
        _has_bsd_inj = bool(_pkg) and (_pkg.get("home_inj_n", 0) + _pkg.get("away_inj_n", 0)) > 0
        if not _has_bsd_inj:
            risk_tags.append("纯数据无伤病情报")"""
c = src.count(old)
print('scan patch occurrences:', c)
if c != 1:
    raise SystemExit('scan patch mismatch')
io.open(p, 'w', encoding='utf-8').write(src.replace(old, new))

# --- patch 2: _gen_best9.py 标题动态场次 ---
p2 = r'_gen_best9.py'
src2 = io.open(p2, encoding='utf-8').read()
old2 = 'L.append("# ⚽ 未来24小时 BEST 9 场完整明细（%s）" % os.path.basename(p).replace(".json", ""))'
new2 = 'L.append("# ⚽ 未来24小时 BEST %d 场完整明细（%s）" % (len(bests), os.path.basename(p).replace(".json", "")))'
c2 = src2.count(old2)
print('gen patch occurrences:', c2)
if c2 != 1:
    raise SystemExit('gen patch mismatch')
io.open(p2, 'w', encoding='utf-8').write(src2.replace(old2, new2))
print('patched OK')
