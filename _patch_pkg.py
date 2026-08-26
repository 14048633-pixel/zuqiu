# 1) 改 build_package: league 兜底优先用 detail league_name
import io
src = io.open(r"D:\足球分析\prediction_v2\pull_match_package.py", encoding="utf-8").read()
old = """        if not pkg.get("league") and ev.get("league_id"):
            pkg["league"] = _league_name(ev.get("league_id"))"""
new = """        if not pkg.get("league"):
            pkg["league"] = ev.get("league_name") or _league_name(ev.get("league_id"))"""
assert old in src
src = src.replace(old, new)
io.open(r"D:\足球分析\prediction_v2\pull_match_package.py", "w", encoding="utf-8").write(src)
print("build_package patched")
