# -*- coding: utf-8 -*-
"""通用虚拟结算器: 读台账待结算 -> the-odds-api /scores 拉比分 -> settle_leg 结算 -> 回填 -> 命中率汇总
用法:
  python paper_settle.py                # 结算全部联赛已完赛场次
  python paper_settle.py --league 荷甲  # 只结算单联赛
  python paper_settle.py --key 1e6c...  # 指定key(默认读.env ODDS_API_KEY_1)
"""
import argparse, csv, io, json, os, re, sys, unicodedata
import urllib.request
from datetime import datetime, timezone, timedelta

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = HERE
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "prediction_v2"))
sys.path.insert(0, os.path.join(HERE, "prediction_v2", "src"))
sys.stdout.reconfigure(encoding="utf-8")

from settle_batch import settle_leg, pnl_for_result  # 复用结算判定+盈亏
from src.live_odds import LEAGUE_SPORT_KEYS
from dotenv import load_dotenv

BJT = timezone(timedelta(hours=8))
LEDGER = os.path.join(ROOT, "analysis_records", "bet_ledger.csv")
SPORT = dict(LEAGUE_SPORT_KEYS)
SPORT["西乙"] = "soccer_spain_segunda_division"
SPORT["英冠"] = "soccer_efl_champ"
SPORT["德乙"] = "soccer_germany_bundesliga2"


def norm(s):
    return re.sub(r"[^a-z0-9]+", "", (s or "").lower())


def tokens(s):
    return set(re.findall(r"[a-z]{3,}", (s or "").lower()))


def match_name(a, b):
    na, nb = tokens(a), tokens(b)
    if not na or not nb:
        return norm(a) == norm(b)
    return na == nb or na <= nb or nb <= na


def fetch_scores(sport_key, api_key, base_url, days=2):
    url = "%s/sports/%s/scores/?apiKey=%s&daysFrom=%d&dateFormat=iso" % (base_url, sport_key, api_key, days)
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def load_ledger():
    rows = []
    if os.path.exists(LEDGER):
        with io.open(LEDGER, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


def save_ledger(rows):
    cols = list(rows[0].keys()) if rows else ["date", "league", "match", "home", "away", "bet_name", "prob", "odds", "ev", "star", "ev_tier", "stake_factor", "result", "ret", "pnl", "status", "src"]
    for _c in ("home_score", "away_score", "score", "is_draw"):
        if _c not in cols:
            cols.append(_c)
    for r in rows:
        for c in cols:
            r.setdefault(c, "")
    with io.open(LEDGER, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def main():
    load_dotenv(os.path.join(ROOT, ".env"))
    ap = argparse.ArgumentParser()
    ap.add_argument("--league", default="ALL")
    ap.add_argument("--key", default=os.environ.get("ODDS_API_KEY_1", ""))
    ap.add_argument("--base", default="https://api.the-odds-api.com/v4")
    args = ap.parse_args()

    rows = load_ledger()
    now_utc = datetime.now(timezone.utc)
    pend = [r for r in rows if r.get("status") == "待结算"]
    if args.league != "ALL":
        want = {x.strip() for x in args.league.split(",") if x.strip()}
        pend = [r for r in pend if r.get("league") in want]
    by_lg = {}
    for r in pend:
        by_lg.setdefault(r.get("league"), []).append(r)
    print("== 虚拟结算: 待结算 %d 条, 联赛 %d 个 ==" % (len(pend), len(by_lg)))

    score_cache = {}
    for lg in sorted(by_lg):
        sk = SPORT.get(lg)
        if not sk:
            print("  ⚠️ %s 无sport映射, 跳过" % lg)
            continue
        try:
            evs = fetch_scores(sk, args.key, args.base)
            score_cache[lg] = evs
            done = sum(1 for e in evs if e.get("completed"))
            print("  ✔ %s 比分 %d 条(完赛%d)" % (lg, len(evs), done))
        except Exception as e:
            print("  ⚠️ %s 拉比分失败: %r" % (lg, e))

    n_settled = n_unfin = n_nomatch = 0
    results = []
    for r in pend:
        lg = r.get("league")
        evs = score_cache.get(lg) or []
        ev = None
        for e in evs:
            if e.get("completed") and match_name(e.get("home_team"), r.get("home")) and match_name(e.get("away_team"), r.get("away")):
                ev = e
                break
        if not ev:
            # 区分原因: 按本注单开球时间判断; 去重避免多轮重复
            ko = None
            try:
                if r.get("kickoff"):
                    ko = datetime.fromisoformat(str(r.get("kickoff")).replace("Z", "+00:00"))
            except Exception:
                ko = None
            if ko and now_utc > ko + timedelta(minutes=130):
                note = "无比分源(开球超130min仍未匹配, 疑似队名问题)"
            else:
                note = "无比分源(未开赛/比分未出)"
            cur = r.get("data_note") or ""
            if note not in cur:
                r["data_note"] = cur + (";" + note if cur else note)
            n_nomatch += 1
            results.append((r, None, "未匹配", None, None))
            continue
        sc = {s["name"]: int(s["score"]) for s in (ev.get("scores") or [])}
        hg, ag = sc.get(ev["home_team"], 0), sc.get(ev["away_team"], 0)
        try:
            res, ret = settle_leg(r.get("bet_name", ""), float(r.get("odds") or 0), hg, ag)
        except Exception as ex:
            res, ret = "未知", None
        pnl = pnl_for_result(res, ret)
        r["home_score"] = hg
        r["away_score"] = ag
        r["score"] = "%d-%d" % (hg, ag)
        r["is_draw"] = 1 if hg == ag else 0  # 输单必须-1(修复: 曾把输单算成0致ROI虚高)
        if "比分源:the-odds-api" not in (r.get("data_note") or ""):
            r["data_note"] = (r.get("data_note") or "") + (";比分源:the-odds-api" if r.get("data_note") else "比分源:the-odds-api")
        results.append((r, "%d-%d" % (hg, ag), res, ret, pnl))
        if res in ("win", "half", "push", "lose"):
            r["status"] = "已结算"
            r["result"] = res
            r["ret"] = ret
            r["pnl"] = "%.4f" % pnl
            n_settled += 1
        else:
            n_unfin += 1

    save_ledger(rows)
    settled = [x for x in results if x[2] in ("win", "half", "push", "lose")]
    wins = sum(1 for x in settled if x[2] == "win")
    halves = sum(1 for x in settled if x[2] == "half")
    pushes = sum(1 for x in settled if x[2] == "push")
    losses = sum(1 for x in settled if x[2] == "lose")
    pnl = sum(x[4] for x in settled)
    roi = pnl / len(settled) if settled else None
    print()
    print("== 命中率汇总(方向) ==")
    print("已结算 %d | 赢 %d / 半 %d / 走水 %d / 输 %d" % (len(settled), wins, halves, pushes, losses))
    if settled:
        print("方向命中率(赢+半*0.5)/n: %.1f%%" % (100 * (wins + 0.5 * halves) / len(settled)))
        print("未输率(含走水): %.1f%%" % (100 * (wins + halves + pushes) / len(settled)))
        print("单注ROI: %+.1f%%" % (roi * 100))
    # 统计口径(2026-08-23 规则6C): 区分"全部腿"与"有效出单(star非空)" —— scan24h对账无条件参考腿(负EV)不计入方向命中率
    starred = [x for x in settled if str(x[0].get("star", "")).strip() not in ("", "0", "None")]
    if starred:
        _sw = sum(1 for x in starred if x[2] == "win")
        _sh = sum(1 for x in starred if x[2] == "half")
        _sp = sum(1 for x in starred if x[2] == "push")
        _sl = sum(1 for x in starred if x[2] == "lose")
        _spnl = sum(x[4] for x in starred)
        print("== 有效出单(star非空, 剔除无条件参考腿) ==")
        print("已结算 %d | 赢 %d / 半 %d / 走水 %d / 输 %d" % (len(starred), _sw, _sh, _sp, _sl))
        print("方向命中率(赢+半*0.5)/n: %.1f%%" % (100 * (_sw + 0.5 * _sh) / len(starred)))
        print("单注ROI: %+.1f%%" % (100 * _spnl / len(starred)))
    else:
        print("有效出单(star非空): 0 注")

    print("未完成/未匹配: %d 条(稍后重跑)" % (n_unfin + n_nomatch))
    out = os.path.join(ROOT, "analysis_records", "paper_settle_%s.json" % datetime.now(BJT).strftime("%Y%m%d_%H%M"))
    with io.open(out, "w", encoding="utf-8") as f:
        json.dump({"time": datetime.now(BJT).isoformat(), "n_settled": len(settled),
                   "wins": wins, "halves": halves, "pushes": pushes, "losses": losses,
                   "pnl": pnl, "roi": roi, "rows": [
                       {"league": x[0].get("league"), "match": x[0].get("match"), "bet": x[0].get("bet_name"),
                        "score": x[1], "result": x[2], "ret": x[3], "pnl": x[4]} for x in results]}, f, ensure_ascii=False, indent=1)
    print("存档: %s" % out)


if __name__ == "__main__":
    main()
