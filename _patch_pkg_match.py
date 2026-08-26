import io, datetime
p = r'prediction_v2\scan_upcoming.py'
src = io.open(p, encoding='utf-8').read()
bak = p + '.bak_' + datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
io.open(bak, 'w', encoding='utf-8').write(src)
print('backup ->', bak)

old = """            if not _pkg:
                _bn = _pa["by_name"]
                _nh, _na = _norm(m["home"]), _norm(m["away"])
                _hk, _ak = _bn["home"].get(_nh), _bn["away"].get(_na)
                if not _ak and _na:
                    for _k, _v in _bn["away"].items():
                        if _na in _k or _k in _na:
                            _ak = _v; break
                if not _hk and _nh:
                    for _k, _v in _bn["home"].items():
                        if _nh in _k or _k in _nh:
                            _hk = _v; break
                if _hk and _ak:"""

new = """            if not _pkg:
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
                if _hk and _ak:"""

cnt = src.count(old)
print('occurrences:', cnt)
if cnt != 1:
    raise SystemExit('pattern not unique/found')
io.open(p, 'w', encoding='utf-8').write(src.replace(old, new))
print('patched OK')
