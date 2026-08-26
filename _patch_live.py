import io
p = r'prediction_v2\_pull_best_live.py'
src = io.open(p, encoding='utf-8').read()
old = """OU_MAP = {"大2.50": ("over_25_goals", "under_25_goals"), "小2.50": ("over_25_goals", "under_25_goals"),
          "大3.00": ("over_35_goals", "under_35_goals"), "小3.00": ("over_35_goals", "under_35_goals")}"""
new = """OU_MAP = {"大2.50": ("over_25_goals", "under_25_goals", False), "小2.50": ("over_25_goals", "under_25_goals", False),
          "大3.00": ("over_35_goals", "under_35_goals", True), "小3.00": ("over_35_goals", "under_35_goals", True)}"""
c = src.count(old)
print('map occurrences:', c)
old2 = """def live_ev(name, prob, cons):
    if name in OU_MAP:
        ov, un = OU_MAP[name]
        p = cons.get(ov) or cons.get(un)
        return p if p else None
    if name in X2_MAP:
        return cons.get(X2_MAP[name])
    return None  # 让球: BSD 无亚盘"""
new2 = """def live_ev(name, prob, cons):
    if name in OU_MAP:
        ov, un, approx = OU_MAP[name]
        p = cons.get(ov) or cons.get(un)
        return (p, approx) if p else (None, approx)
    if name in X2_MAP:
        return (cons.get(X2_MAP[name]), False)
    return (None, False)  # 让球: BSD 无亚盘"""
c2 = src.count(old2)
print('live_ev occurrences:', c2)
old3 = """            new_price = live_ev(bb["name"], bb["prob"], cons)
            if new_price:
                n_ev = bb["prob"] * new_price - 1
                row["live_odds"] = new_price
                row["live_ev"] = round(n_ev, 4)
                row["delta_ev"] = round(n_ev - bb["ev"], 4)
                row["status"] = "临场确认" if n_ev >= 0.05 else "临场掉出"
            else:
                row["status"] = "BSD无此市场(让球/缺盘)"
        out.append(row)"""
new3 = """            new_price, approx = live_ev(bb["name"], bb["prob"], cons)
            if new_price:
                n_ev = bb["prob"] * new_price - 1
                row["live_odds"] = new_price
                row["approx_ou"] = approx
                row["live_ev"] = round(n_ev, 4)
                row["delta_ev"] = round(n_ev - bb["ev"], 4)
                row["status"] = ("临场确认(近似3.5线)" if approx and n_ev >= 0.05
                                 else "临场掉出" if n_ev < 0.05 else "临场确认")
            else:
                row["status"] = "BSD无此市场(让球/缺盘)"
        out.append(row)"""
c3 = src.count(old3)
print('main occurrences:', c3)
if c != 1 or c2 != 1 or c3 != 1:
    raise SystemExit('mismatch')
io.open(p, 'w', encoding='utf-8').write(src.replace(old, new).replace(old2, new2).replace(old3, new3))
print('patched OK')
