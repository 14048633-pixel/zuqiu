import io
p = r'prediction_v2\scan_upcoming.py'
src = io.open(p, encoding='utf-8').read()
old = """            cons = _pkg.get("consensus") or {}
            changed = False
            if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
                m["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
                m.setdefault("books_used", {})["h2h"] = "bsd_consensus"
                changed = True
            if cons.get("over_25_goals") and cons.get("under_25_goals"):
                m["totals"] = {"line": 2.5, "over_price": cons["over_25_goals"], "under_price": cons["under_25_goals"]}
                m.setdefault("books_used", {})["totals"] = "bsd_consensus(2.5)"
                changed = True
            if changed and _pkg.get("pulled_at"):
                m["snap"] = _pkg["pulled_at"]
                n += 1"""
new = """            cons = _pkg.get("consensus") or {}
            changed = False
            # 1X2: BSD 共识价为主源优先覆盖(the-odds 降为临场专用)
            if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
                m["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
                m.setdefault("books_used", {})["h2h"] = "bsd_consensus"
                changed = True
            # 大小球: 仅当无 totals 时用 BSD 2.5 补缺. BSD 只有 2.5 单线,
            # 覆盖会丢掉原市场线(如3.00)且抽水口径不同致EV失真(Neom大3.00消失/GilVicente误否决)
            if not m.get("totals") and cons.get("over_25_goals") and cons.get("under_25_goals"):
                m["totals"] = {"line": 2.5, "over_price": cons["over_25_goals"], "under_price": cons["under_25_goals"]}
                m.setdefault("books_used", {})["totals"] = "bsd_consensus(2.5)"
                changed = True
            if changed and _pkg.get("pulled_at"):
                m["snap"] = _pkg["pulled_at"]
                n += 1"""
c = src.count(old)
print('occurrences:', c)
if c != 1:
    raise SystemExit('mismatch')
io.open(p, 'w', encoding='utf-8').write(src.replace(old, new))
print('patched OK')
