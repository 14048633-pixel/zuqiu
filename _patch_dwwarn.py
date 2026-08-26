import io
p = r'prediction_v2\scan_upcoming.py'
src = io.open(p, encoding='utf-8').read()

# 1) bsd_odds_merge: 覆盖 h2h 前保留旧 the-odds h2h
old1 = """            if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
                m["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
                m.setdefault("books_used", {})["h2h"] = "bsd_consensus"
                changed = True"""
new1 = """            if cons.get("home_win") and cons.get("draw") and cons.get("away_win"):
                if m.get("h2h") and "h2h_prev" not in m:
                    m["h2h_prev"] = dict(m["h2h"])
                m["h2h"] = {"home": cons["home_win"], "draw": cons["draw"], "away": cons["away_win"]}
                m.setdefault("books_used", {})["h2h"] = "bsd_consensus"
                changed = True"""
c1 = src.count(old1)
print('part1 occurrences:', c1)

# 2) draw_warn: 双源去水平局取更高(防平优先, 源切换不跳变)
old2 = """    # ---- 平局预警(2026-08-19 3万场实证): 市场去水平局概率>=26% 提前计算, 供规则①让球+号过滤/规则③降星使用 ----
    draw_warn = None
    if fair and fair[1] >= DRAW_WARN_MIN:
        draw_warn = {"market_draw_prob": round(fair[1] * 100, 1), "strong": fair[1] >= DRAW_WARN_STRONG}"""
new2 = """    # ---- 平局预警(2026-08-19 3万场实证): 市场去水平局概率>=26% 提前计算, 供规则①让球+号过滤/规则③降星使用 ----
    # 双源并集: BSD consensus(主源) 与 the-odds 旧快照(h2h_prev) 去水平局取更高, 防源切换导致阈值临界跳变
    draw_warn = None
    _dw_prob = fair[1] if fair else 0.0
    _h2h_prev = m.get("h2h_prev") or {}
    if _h2h_prev.get("home"):
        try:
            _s2 = 1 / _h2h_prev["home"] + 1 / _h2h_prev["draw"] + 1 / _h2h_prev["away"]
            _dw_prob = max(_dw_prob, (1 / _h2h_prev["draw"]) / _s2)
        except Exception:
            pass
    if _dw_prob >= DRAW_WARN_MIN:
        draw_warn = {"market_draw_prob": round(_dw_prob * 100, 1), "strong": _dw_prob >= DRAW_WARN_STRONG}"""
c2 = src.count(old2)
print('part2 occurrences:', c2)
if c1 != 1 or c2 != 1:
    raise SystemExit('mismatch')
io.open(p, 'w', encoding='utf-8').write(src.replace(old1, new1).replace(old2, new2))
print('patched OK')
