# 修改 _fetch_bsd_next24h.py 日期为 8/25-8/26, 输出结构检查
import io, sys
src = io.open(r"D:\足球分析\_fetch_bsd_next24h.py", encoding="utf-8").read()
old = """F = datetime(2026, 8, 24, 15, 0, tzinfo=timezone.utc)
T = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
events = []
for date in ("2026-08-24", "2026-08-25"):"""
new = """F = datetime(2026, 8, 25, 15, 0, tzinfo=timezone.utc)
T = datetime(2026, 8, 26, 15, 0, tzinfo=timezone.utc)
events = []
for date in ("2026-08-25", "2026-08-26"):"""
assert old in src
src = src.replace(old, new)
io.open(r"D:\足球分析\_fetch_bsd_next24h.py", "w", encoding="utf-8").write(src)
print("dates updated")
