# -*- coding: utf-8 -*-
"""实盘台账: 累计 300 场样本, 用结果校准模型方向
================================================================
- scan:    python bet_ledger.py --scan [scan_json]     # 扫描best_bet落账(去重)
- settle:  python bet_ledger.py --settle [结算json...] # 结算结果回填
- status:  python bet_ledger.py --status               # 当前累计统计
台账: analysis_records/bet_ledger.csv
列: date,league,match,home,away,bet_name,prob,odds,ev,star,ev_tier,stake_factor,result,ret,pnl,status,src
"""
import argparse, csv, io, json, os, re, sys
from datetime import datetime

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LEDGER = os.path.join(ROOT, "analysis_records", "bet_ledger.csv")
COLS = ["date", "league", "match", "home", "away", "bet_name", "prob", "odds", "ev", "star",
        "ev_tier", "stake_factor", "result", "ret", "pnl", "status", "src",
        "veto", "risk_tags", "divergence_pp", "placed_odds", "bookmaker", "verified", "kickoff",
        "data_src", "snap_age_h", "upset_level", "data_note", "scan_ts",
        "coach_atk_mod", "coach_def_mod", "coach_sample_size"]
TARGET = 300

def _norm_team(t):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    return "".join(c.lower() for c in t if c.isalnum() or c.isspace())


def _team_key(t):
    """词序无关队名key: 连字符/空格都当分隔符, 'S-Pulse'=='S Pulse', 'Hiroshima Sanfrecce'=='Sanfrecce Hiroshima'."""
    import unicodedata
    t = unicodedata.normalize("NFKD", str(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    toks = sorted(x for x in re.split(r"[^a-z0-9]+", t.lower()) if x and x not in ("fc", "cf"))
    return "|".join(toks)



def _load():
    rows = []
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def _key(r):
    return (r.get("date"), r.get("league"), r.get("home"), r.get("away"), r.get("bet_name"))


def _is_post_kick_snap(r):
    """赛后才拉的盘(snap_age_h<0) = 防泄漏铁律中的作废行, 一律不入统计.
    snap缺失按不泄漏处理(保守保留), 与 ledger_backtest.py 口径一致."""
    try:
        return float(r.get("snap_age_h") or 999) < 0
    except (TypeError, ValueError):
        return False


def _save(rows):
    os.makedirs(os.path.dirname(LEDGER), exist_ok=True)
    with io.open(LEDGER, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLS)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in COLS})


def cmd_scan(scan_json):
    if not os.path.exists(scan_json):
        print("no scan file:", scan_json); return
    j = json.load(io.open(scan_json, encoding="utf-8"))
    try:
        scan_ts = datetime.fromtimestamp(os.path.getmtime(scan_json)).strftime("%Y%m%d_%H%M%S")
    except Exception:
        scan_ts = ""
    rows = _load()
    added = superseded = 0
    for m in j.get("matches", []):
        r = m.get("result") or {}
        bb = r.get("best_bet")
        if not bb:
            continue
        _rtags = r.get("risk_tags") or []
        _rtxt = ";".join(str(x) for x in _rtags)
        _veto = 1 if any("否决" in str(x) for x in _rtags) else 0
        nr = {
            "date": (m.get("ct") or "")[:10],
            "league": m.get("league", ""),
            "match": "%s vs %s" % (m.get("home", ""), m.get("away", "")),
            "home": m.get("home", ""), "away": m.get("away", ""),
            "bet_name": bb.get("name", ""),
            "prob": round(float(bb.get("prob") or 0), 4),
            "odds": bb.get("odds", ""), "ev": round(float(bb.get("ev") or 0), 4),
            "star": bb.get("star", ""), "ev_tier": bb.get("ev_tier", ""),
            "stake_factor": bb.get("stake_factor", ""),
            "result": "", "ret": "", "pnl": "", "status": "待结算", "src": "scan",
            "veto": _veto, "risk_tags": _rtxt, "kickoff": m.get("ct", ""),
            "data_src": ";".join(str(x) for x in ((r.get("data_src") or {}).values() if isinstance(r.get("data_src"), dict) else [])),
            "snap_age_h": r.get("snap_age_h", ""), "upset_level": (r.get("upset") or {}).get("level", ""),
            "data_note": "无伤病情报" if _rtxt else "",
            "scan_ts": scan_ts,
        }
        _cm = r.get("coach") or {}
        _atk = [v for v in (_cm.get("h_atk"), _cm.get("a_atk")) if v]
        _def = [v for v in (_cm.get("h_def"), _cm.get("a_def")) if v]
        _smp = [v for v in (_cm.get("h_sample"), _cm.get("a_sample")) if v]
        nr["coach_atk_mod"] = round(sum(_atk) / len(_atk), 4) if _atk else ""
        nr["coach_def_mod"] = round(sum(_def) / len(_def), 4) if _def else ""
        nr["coach_sample_size"] = min(_smp) if _smp else ""
        lg = nr["league"]
        hk, ak = _team_key(nr["home"]), _team_key(nr["away"])
        same_match = [i for i, x in enumerate(rows)
                      if x.get("league") == lg and _team_key(x.get("home", "")) == hk and _team_key(x.get("away", "")) == ak]
        if same_match and any(rows[i].get("status") == "已结算" for i in same_match):
            # 已结算场次禁止追加新腿(防开赛后扫描重复计注)
            continue
        pend = [i for i in same_match if rows[i].get("status") == "待结算"]
        if pend:
            # 新扫描取代旧腿(同一场只保留最新一代best_bet)
            for i in pend:
                rows[i] = dict(rows[i], **nr)
                superseded += 1
            continue
        rows.append(nr); added += 1
    _save(rows)
    print("落账新增 %d 条, 取代旧腿 %d 条, 台账累计 %d 条" % (added, superseded, len(rows)))


def cmd_settle(settle_jsons):
    rows = _load()
    added = updated = 0
    for sj in settle_jsons:
        if not os.path.exists(sj):
            print("no settle file:", sj); continue
        j = json.load(io.open(sj, encoding="utf-8"))
        for s in j.get("rows", []):
            bb = s.get("bb") or {}
            nh, na = _team_key(s.get("home", "")), _team_key(s.get("away", ""))
            # 队名归一化匹配(容忍 - / FC / 词序差异), 同场同盘才回填
            cand = [i for i, r in enumerate(rows)
                    if r.get("league") == s.get("league")
                    and _team_key(r.get("home", "")) == nh
                    and _team_key(r.get("away", "")) == na
                    and r.get("bet_name") == bb.get("name")]
            if cand:
                i = cand[0]
                new_status = s.get("status", "已结算")
                # 防泄漏铁律(2026-08-26审计落地): 赛后拉盘的行结算时标无效, 不入已结算统计
                if new_status == "已结算" and _is_post_kick_snap(rows[i]):
                    new_status = "无效(snap<0赛后盘)"
                rows[i]["status"] = new_status
                rows[i]["result"] = s.get("result", "")
                rows[i]["ret"] = s.get("ret", "")
                rows[i]["pnl"] = s.get("pnl", "")
                rows[i]["odds"] = bb.get("odds", rows[i].get("odds", ""))
                updated += 1
            else:
                # 台账缺该注单(多腿/重分析) -> 补录
                rows.append({
                    "date": (s.get("score") and "") or "",
                    "league": s.get("league", ""),
                    "match": "%s vs %s" % (s.get("home", ""), s.get("away", "")),
                    "home": s.get("home", ""), "away": s.get("away", ""),
                    "bet_name": bb.get("name", ""),
                    "prob": bb.get("prob", ""), "odds": bb.get("odds", ""),
                    "ev": bb.get("ev", ""), "star": bb.get("star", ""),
                    "ev_tier": bb.get("ev_tier", ""), "stake_factor": bb.get("stake_factor", ""),
                    "result": s.get("result", ""), "ret": s.get("ret", ""),
                    "pnl": s.get("pnl", ""), "status": s.get("status", "已结算"), "src": "settle档案",
                    "veto": "", "risk_tags": "", "divergence_pp": "", "placed_odds": "",
                    "bookmaker": "", "verified": "", "kickoff": "", "data_src": "",
                    "snap_age_h": "", "upset_level": "", "data_note": "无比分源(补录)", "scan_ts": "",
                })
                added += 1
    _save(rows)
    print("结算回填 %d 条(补录 %d), 台账累计 %d 条" % (updated, added, len(rows)))


def cmd_status():
    rows = _load()
    settled = [r for r in rows if r.get("status") == "已结算"]
    # 防泄漏铁律: snap_age_h<0(赛后拉盘)一律作废, 主口径=合规行(与ledger_backtest一致)
    leak = [r for r in settled if _is_post_kick_snap(r)]
    clean = [r for r in settled if not _is_post_kick_snap(r)]
    voided = [r for r in rows if str(r.get("status", "")).startswith("无效")]

    def _stat(rs, label):
        if not rs:
            print("%s: 0 场" % label)
            return
        wins = [r for r in rs if r.get("result") == "win"]
        halves = [r for r in rs if r.get("result") == "half"]
        losses = [r for r in rs if r.get("result") in ("loss", "lose")]
        pushes = [r for r in rs if r.get("result") == "push"]
        pnl = sum(float(r.get("pnl") or 0) for r in rs)
        roi = pnl / len(rs)
        print("%s: %d 场 | 胜 %d / 半 %d / 走 %d / 负 %d | 净胜 %+.2f (每注1单位) | ROI: %+.1f%%"
              % (label, len(rs), len(wins), len(halves), len(pushes), len(losses), pnl, roi * 100))

    print("== 实盘台账 ==")
    print("累计落账: %d 场 | 目标 300 场 | 还差 %d 场" % (len(rows), max(0, TARGET - len(rows))))
    _stat(clean, "已结算(合规口径)")
    if leak:
        print("⚠️ 赛后拉盘行 snap<0: %d 条 -> 已按防泄漏铁律作废, 不入统计(明细见 ledger_backtest)" % len(leak))
    if voided:
        print("累计无效行(含历史迁移): %d 条" % len(voided))
    print("台账: %s" % LEDGER)



def cmd_place(place_json):
    """手动落账: 用户实际下单的注单(真实成交价/机构/核验状态)。place_json 为列表文件。"""
    if not os.path.exists(place_json):
        print("no place file:", place_json); return
    rows = _load()
    seen = {_key(r) for r in rows}
    j = json.load(io.open(place_json, encoding="utf-8"))
    added = 0
    for b in j if isinstance(j, list) else j.get("bets", []):
        nr = {
            "date": (b.get("kickoff") or b.get("date") or "")[:10],
            "league": b.get("league", ""),
            "match": "%s vs %s" % (b.get("home", ""), b.get("away", "")),
            "home": b.get("home", ""), "away": b.get("away", ""),
            "bet_name": b.get("bet_name", ""),
            "prob": round(float(b.get("prob") or 0), 4),
            "odds": b.get("placed_odds", b.get("odds", "")),
            "ev": round(float(b.get("ev") or 0), 4),
            "star": b.get("star", ""), "ev_tier": b.get("ev_tier", ""),
            "stake_factor": b.get("stake_factor", ""),
            "result": "", "ret": "", "pnl": "", "status": "待结算", "src": b.get("src", "手动"),
            "veto": int(b.get("veto") or 0),
            "risk_tags": ";".join(b.get("risk_tags") or []),
            "divergence_pp": b.get("divergence_pp", ""),
            "placed_odds": b.get("placed_odds", b.get("odds", "")),
            "bookmaker": b.get("bookmaker", ""),
            "verified": b.get("verified", ""),
            "kickoff": b.get("kickoff", ""),
        }
        k = _key(nr)
        if k not in seen:
            rows.append(nr); seen.add(k); added += 1
    _save(rows)
    print("手动落账新增 %d 条, 台账累计 %d 条" % (added, len(rows)))


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan", help="扫描json落账")
    ap.add_argument("--place", help="手动落账json(真实成交价/机构/核验)")
    ap.add_argument("--settle", nargs="*", help="结算json回填")
    ap.add_argument("--status", action="store_true")
    args = ap.parse_args()
    if args.place:
        cmd_place(args.place)
    if args.scan:
        cmd_scan(args.scan)
    if args.settle:
        cmd_settle(args.settle)
    cmd_status()


if __name__ == "__main__":
    main()
