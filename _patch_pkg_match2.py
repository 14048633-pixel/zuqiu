import io, datetime
p = r'prediction_v2\scan_upcoming.py'
src = io.open(p, encoding='utf-8').read()

# 1) by_name 值改列表
old1 = """        if rec["home"]:
            by_name["home"].setdefault(_norm(d.get("home") or ""), rec)
        if rec["away"]:
            by_name["away"].setdefault(_norm(d.get("away") or ""), rec)"""
new1 = """        if rec["home"]:
            by_name["home"].setdefault(_norm(d.get("home") or ""), []).append(rec)
        if rec["away"]:
            by_name["away"].setdefault(_norm(d.get("away") or ""), []).append(rec)"""
c1 = src.count(old1)
print('part1 occurrences:', c1)

# 2) 回退逻辑: 候选 + 同包交集优先
old2 = """            if not _pkg:
                _bn = _pa["by_name"]
                _nh, _na = _norm(m["home"]), _norm(m["away"])
                _nh2 = _norm(_resolve_alias(m["home"])) or _nh
                _na2 = _norm(_resolve_alias(m["away"])) or _na
                _hk = _bn["home"].get(_nh) or _bn["home"].get(_nh2)
                _ak = _bn["away"].get(_na) or _bn["away"].get(_na2)

                def _pkg_subset(d, n):
                    if not n:
                        return None
                    ws = set(n.split())
                    for _k, _v in d.items():
                        wk = set(_k.split())
                        if ws and wk and (ws <= wk or wk <= ws):
                            small, big = (ws, wk) if len(ws) <= len(wk) else (wk, ws)
                            if len(small) == 1 or len(small) / len(big) >= 0.6:
                                return _v
                    return None

                if not _ak:
                    _ak = _pkg_subset(_bn["away"], _na) or _pkg_subset(_bn["away"], _na2)
                if not _hk:
                    _hk = _pkg_subset(_bn["home"], _nh) or _pkg_subset(_bn["home"], _nh2)
                if _hk and _ak:
                    _pkg = {"home": _hk["home"], "away": _ak["away"],
                            "home_inj_n": _hk.get("home_inj_n", 0), "away_inj_n": _ak.get("away_inj_n", 0),
                            "home_inj": _hk.get("home_inj", []), "away_inj": _ak.get("away_inj", [])}"""
new2 = """            if not _pkg:
                _bn = _pa["by_name"]
                _nh, _na = _norm(m["home"]), _norm(m["away"])
                _nh2 = _norm(_resolve_alias(m["home"])) or _nh
                _na2 = _norm(_resolve_alias(m["away"])) or _na

                def _pkg_cands(d, names):
                    out = []
                    for n in names:
                        if n and d.get(n):
                            out.extend(d[n])
                    if out:
                        return out
                    for n in names:
                        if not n:
                            continue
                        ws = set(n.split())
                        for _k, _vs in d.items():
                            wk = set(_k.split())
                            if ws and wk and (ws <= wk or wk <= ws):
                                small, big = (ws, wk) if len(ws) <= len(wk) else (wk, ws)
                                if len(small) == 1 or len(small) / len(big) >= 0.6:
                                    out.extend(_vs)
                    return out

                _hc = _pkg_cands(_bn["home"], [_nh, _nh2])
                _ac = _pkg_cands(_bn["away"], [_na, _na2])
                # 同名队多包时, 优先同一包同时匹配主客(防跨场错配: Botafogo 旧包223326)
                _both = [r for r in _hc if r in _ac]
                _pkg = _both[0] if _both else None
                if _pkg is None and _hc and _ac:
                    _pkg = {"home": _hc[0]["home"], "away": _ac[0]["away"],
                            "home_inj_n": _hc[0].get("home_inj_n", 0), "away_inj_n": _ac[0].get("away_inj_n", 0),
                            "home_inj": _hc[0].get("home_inj", []), "away_inj": _ac[0].get("away_inj", [])}"""
c2 = src.count(old2)
print('part2 occurrences:', c2)

if c1 != 1 or c2 != 1:
    raise SystemExit('pattern mismatch')
io.open(p, 'w', encoding='utf-8').write(src.replace(old1, new1).replace(old2, new2))
print('patched OK')
