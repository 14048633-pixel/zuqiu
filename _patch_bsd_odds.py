import io, datetime
p = r'prediction_v2\scan_upcoming.py'
src = io.open(p, encoding='utf-8').read()
bak = p + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
io.open(bak, 'w', encoding='utf-8').write(src)
print('backup ->', bak)

# 1) _load_pkg_attacks: rec 增加 consensus + pulled_at; 有consensus也建索引
old1 = """        rec = {
            "home": (h.get("stats") or {}) if h.get("have") else None,
            "away": (a.get("stats") or {}) if a.get("have") else None,
            "home_inj_n": len(hi), "away_inj_n": len(ai),
            "home_inj": [x.get("name") or x.get("short_name") for x in hi][:6],
            "away_inj": [x.get("name") or x.get("short_name") for x in ai][:6],
        }
        if d.get("id") is not None:
            _eid = str(d["id"])
            by_id[int(d["id"])] = rec
            by_id[_eid] = rec
            if _eid.startswith("apifb"):
                by_id[_eid[5:]] = rec
        if rec["home"]:
            by_name["home"].setdefault(_norm(d.get("home") or ""), []).append(rec)
        if rec["away"]:
            by_name["away"].setdefault(_norm(d.get("away") or ""), []).append(rec)
    return {"by_id": by_id, "by_name": by_name}"""
new1 = """        rec = {
            "home": (h.get("stats") or {}) if h.get("have") else None,
            "away": (a.get("stats") or {}) if a.get("have") else None,
            "home_inj_n": len(hi), "away_inj_n": len(ai),
            "home_inj": [x.get("name") or x.get("short_name") for x in hi][:6],
            "away_inj": [x.get("name") or x.get("short_name") for x in ai][:6],
            "consensus": (d.get("odds") or {}).get("consensus") or {},
            "pulled_at": d.get("pulled_at"),
        }
        if d.get("id") is not None:
            _eid = str(d["id"])
            by_id[int(d["id"])] = rec
            by_id[_eid] = rec
            if _eid.startswith("apifb"):
                by_id[_eid[5:]] = rec
        if rec["home"] or rec["consensus"]:
            by_name["home"].setdefault(_norm(d.get("home") or ""), []).append(rec)
        if rec["away"] or rec["consensus"]:
            by_name["away"].setdefault(_norm(d.get("away") or ""), []).append(rec)
    return {"by_id": by_id, "by_name": by_name}"""
c1 = src.count(old1)
print('part1 occurrences:', c1)
if c1 != 1:
    raise SystemExit('part1 mismatch')
src = src.replace(old1, new1)

# 2) 新增 bsd_odds_merge 函数: 放在 parse_snapshots 之后(match_stats 之前)
old2 = """def match_stats(team, div, team_stats, index):"""
new2 = """def bsd_odds_merge(events):
    \"\"\"BSD consensus 免费盘源 -> 覆盖 1X2/大小球 (扫描主盘源, the-odds-api 降为临场专用).
    命中 match_package 的场次: h2h/totals 用 BSD 共识价, snap 更新为包拉取时间, 防过期误否决.
    返回覆盖场次数. 亚盘(让球)BSD 不提供, 保持原快照或缺亚盘标注.\"\"\"
    try:
        _pa = pkg_attacks()
    except Exception:
        return 0
    _bn = _pa.get("by_name") or {}
    _bid = _pa.get("by_id") or {}
    n = 0

    def _cands(d, names):
        out = []
        for nm in names:
            if nm and d.get(nm):
                out.extend(d[nm])
        if out:
            return out
        for nm in names:
            if not nm:
                continue
            ws = set(nm.split())
            for _k, _vs in d.items():
                wk = set(_k.split())
                if ws and wk and (ws <= wk or wk <= ws):
                    small, big = (ws, wk) if len(ws) <= len(wk) else (wk, ws)
                    if len(small) == 1 or len(small) / len(big) >= 0.6:
                        out.extend(_vs)
        return out

    for m in events:
        try:
            _pkg = None
            _eid = str(m.get("id") or "")
            _stripped = _eid[5:] if _eid.startswith("apifb") else _eid
            _pkg = _bid.get(_eid) or _bid.get(_stripped)
            try:
                if _pkg is None:
                    _pkg = _bid.get(int(_stripped or 0))
            except Exception:
                pass
            if _pkg is None:
                _nh = _norm(m.get("home") or "")
                _na = _norm(m.get("away") or "")
                _nh2 = _norm(_resolve_alias(m.get("home") or "")) or _nh
                _na2 = _norm(_resolve_alias(m.get("away") or "")) or _na
                _hc = _cands(_bn.get("home") or {}, [_nh, _nh2])
                _ac = _cands(_bn.get("away") or {}, [_na, _na2])
                _both = [r for r in _hc if r in _ac]
                _pkg = _both[0] if _both else None
                if _pkg is None and _hc and _ac:
                    _pkg = _hc[0]
            if not _pkg:
                continue
            cons = _pkg.get("consensus") or {}
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
                n += 1
        except Exception:
            continue
    return n


def match_stats(team, div, team_stats, index):"""
c2 = src.count(old2)
print('part2 occurrences:', c2)
if c2 != 1:
    raise SystemExit('part2 mismatch')
src = src.replace(old2, new2)

# 3) 主循环调用: for m in events 前
old3 = """    results = []
    for m in events:
        _info = info_map.get((m["league"], m["home"], m["away"]))"""
new3 = """    results = []
    try:
        _merged_n = bsd_odds_merge(events)
        if _merged_n:
            print("✔ BSD consensus 免费盘源覆盖 %d 场 (1X2/大小球), the-odds-api 降为临场专用。" % _merged_n)
    except Exception:
        pass
    for m in events:
        _info = info_map.get((m["league"], m["home"], m["away"]))"""
c3 = src.count(old3)
print('part3 occurrences:', c3)
if c3 != 1:
    raise SystemExit('part3 mismatch')
src = src.replace(old3, new3)

io.open(p, 'w', encoding='utf-8').write(src)
print('patched OK')
