# -*- coding: utf-8 -*-
"""API-Football 伤停数据拉取 + 合并进 matches_info
============================================================
用法:
  # 1) 拉取 + 合并(所有 analysis_records/matches_info_*.json)
  python prediction_v2/injuries_apifootball.py --date 2026-08-16
  # 2) 只合并已有 injuries json(不消耗配额)
  python prediction_v2/injuries_apifootball.py --date 2026-08-16 --no-fetch
  # 3) 指定单个 matches_info 文件
  python prediction_v2/injuries_apifootball.py --date 2026-08-16 --info analysis_records/matches_info_20260816.json

数据: GET https://v3.football.api-sports.io/injuries?date=YYYY-MM-DD
  Key: .env 的 FOOTBALL_API_KEY(x-apisports-key, Free 100次/日)
  每次全量拉取=1次请求; 网络不稳已内置重试(默认3次)
合并: 每条 match 增加 injuries{home:[],away:[]} + 更新 intel 文本
队名匹配: 复用 bet_ledger._team_key(词序无关, 忽略 fc/cf)
"""
import argparse, glob, io, json, os, re, sys, time, unicodedata
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASE = "https://v3.football.api-sports.io"
ENV_FILE = os.path.join(ROOT, ".env")
MAX_LIST = 8


def load_api_key():
    if not os.path.exists(ENV_FILE):
        return ""
    for line in io.open(ENV_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("FOOTBALL_API_KEY="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


API_KEY = load_api_key()
HEADERS = {"x-apisports-key": API_KEY}


def _team_key(t):
    """词序无关队名key(与 bet_ledger._team_key 一致)."""
    t = unicodedata.normalize("NFKD", str(t))
    t = "".join(c for c in t if not unicodedata.combining(c))
    toks = sorted(x for x in re.split(r"[^a-z0-9]+", t.lower()) if x and x not in ("fc", "cf"))
    return "|".join(toks)


def fetch_injuries(date, tries=3, timeout=150):
    """GET /injuries?date=YYYY-MM-DD -> response 列表; 失败返回 None."""
    if not API_KEY:
        print("  ⚠️ 无 FOOTBALL_API_KEY(.env), 跳过拉取")
        return None
    for i in range(1, tries + 1):
        try:
            r = requests.get(BASE + "/injuries", params={"date": date},
                             headers=HEADERS, timeout=timeout)
            if r.status_code == 200:
                d = r.json()
                return d.get("response") or []
            print("  HTTP %s: %s" % (r.status_code, r.text[:150]))
        except Exception as e:
            print("  第%d/%d次失败: %s" % (i, tries, type(e).__name__))
        if i < tries:
            time.sleep(5)
    return None


def build_team_map(injuries):
    """injuries -> {team_key: [{name,status,reason}, ...]} (按球员id去重, API原始数据每条重复两次)."""
    m = {}
    seen = set()
    for it in injuries:
        p = it.get("player") or {}
        t = it.get("team") or {}
        k = _team_key(t.get("name") or "")
        if not k:
            continue
        pid = p.get("id")
        if pid is not None:
            dk = (pid, k)
        else:
            dk = (p.get("name"), p.get("reason"), p.get("type"))
        if dk in seen:
            continue
        seen.add(dk)
        m.setdefault(k, []).append({
            "name": p.get("name") or "?",
            "status": (p.get("type") or "Missing Fixture").strip(),
            "reason": (p.get("reason") or "").strip(),
        })
    return m


STATUS_CN = {"missing fixture": "缺", "questionable": "疑",
             "injured": "伤", "suspended": "停", "doubtful": "疑"}


def _fmt_rec(rec, max_reason=16):
    s = STATUS_CN.get((rec.get("status") or "").lower(), rec.get("status") or "缺")
    reason = (rec.get("reason") or "").strip()
    if len(reason) > max_reason:
        reason = reason[:max_reason] + "…"
    ret = rec.get("expected_return")
    ret_s = ""
    if ret:
        ret_s = "~" + str(ret)[5:10]
    pos_s = "[%s]" % rec.get("position") if rec.get("position") else ""
    return "%s%s(%s%s%s)" % (rec.get("name") or "?", pos_s, s, ("-" + reason) if reason else "", ret_s)


def summarize(recs):
    """-> 精简列表(最多 MAX_LIST 条)."""
    out = []
    for r in (recs or [])[:MAX_LIST]:
        _item = {"name": r.get("name"), "status": r.get("status"),
                 "reason": (r.get("reason") or "")[:40],
                 "expected_return": r.get("expected_return")}
        if r.get("position") is not None:
            _item["position"] = r.get("position")
        out.append(_item)
    return out


def intel_text(h_covered, h_recs, a_covered, a_recs):
    """可读中文情报文本. covered=False=该队无本数据源; recs=[] 表示匹配但无伤停."""
    def side(tag, cov, recs):
        if not cov:
            return "%s:无数据" % tag
        if not recs:
            return "%s:0人" % tag
        tail = "等%d人" % (len(recs) - MAX_LIST) if len(recs) > MAX_LIST else ""
        return "%s:%d人[%s%s]" % (tag, len(recs),
                                  "、".join(_fmt_rec(x) for x in recs[:MAX_LIST]), tail)
    total = (len(h_recs or []) + len(a_recs or []))
    return "伤停[共%d] %s %s" % (total, side("主", h_covered, h_recs), side("客", a_covered, a_recs))


def _get_by_keys(team_map, keys):
    for k in keys:
        if k in team_map:
            return team_map[k]
    return None


def merge_into_info(info_matches, team_map, src="apifootball"):
    """按侧合并伤停: 只覆盖本数据源命中的侧, 保留另一侧已有数据. 返回(主队命中, 客队命中)."""
    nh = na = 0
    for m in info_matches:
        h_recs = _get_by_keys(team_map, [_team_key(m.get("home") or ""),
                                         _team_key(m.get("home_espn") or "")])
        a_recs = _get_by_keys(team_map, [_team_key(m.get("away") or ""),
                                         _team_key(m.get("away_espn") or "")])
        inj = m.setdefault("injuries", {})
        inj.setdefault("home", [])
        inj.setdefault("away", [])
        inj.setdefault("home_covered", False)
        inj.setdefault("away_covered", False)
        inj.setdefault("sources", {"home": None, "away": None})
        if h_recs is not None:
            inj["home"] = summarize(h_recs)
            inj["home_covered"] = True
            inj["sources"]["home"] = src
            nh += 1
        if a_recs is not None:
            inj["away"] = summarize(a_recs)
            inj["away_covered"] = True
            inj["sources"]["away"] = src
            na += 1
        m["intel"] = intel_text(inj["home_covered"], inj["home"],
                                inj["away_covered"], inj["away"])
    return nh, na


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--no-fetch", action="store_true", help="只合并已有 injuries json")
    ap.add_argument("--info", help="指定 matches_info json(默认全部 matches_info_*.json)")
    args = ap.parse_args()

    inj_path = os.path.join(ROOT, "analysis_records", "apifootball_injuries_%s.json" % args.date)
    if args.no_fetch:
        if not os.path.exists(inj_path):
            print("无已有 injuries 文件: %s" % inj_path)
            return
        injuries = json.load(io.open(inj_path, encoding="utf-8")).get("response") or []
        print("使用已有数据 %s (%d 条)" % (inj_path, len(injuries)))
    else:
        print("拉取 %s 伤停(API-Football)..." % args.date)
        injuries = fetch_injuries(args.date)
        if injuries is None:
            print("拉取失败, 终止(可重试或 --no-fetch 复用已有文件)")
            return
        with io.open(inj_path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "date": args.date, "results": len(injuries), "response": injuries},
                      f, ensure_ascii=False, indent=1)
        print("已存 %s (%d 条)" % (inj_path, len(injuries)))

    team_map = build_team_map(injuries)
    print("伤停覆盖球队数: %d" % len(team_map))
    if args.info:
        targets = [args.info if os.path.isabs(args.info) else os.path.join(ROOT, args.info)]
    else:
        targets = sorted(glob.glob(os.path.join(ROOT, "analysis_records", "matches_info_*.json")))
    for p in targets:
        if not os.path.exists(p):
            print("  ⚠️ 文件不存在, 跳过: %s" % p)
            continue
        d = json.load(io.open(p, encoding="utf-8"))
        nh, na = merge_into_info(d.get("matches") or [], team_map)
        with io.open(p, "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False, indent=1)
        md = os.path.splitext(p)[0] + ".md"
        try:
            sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
            from _batch_match_info import render_md
            with io.open(md, "w", encoding="utf-8") as f:
                f.write("\n".join(render_md(d.get("matches") or [])))
            md_s = " + md"
        except Exception as e:
            md_s = " (md更新失败: %s)" % type(e).__name__
        print("合并 %s: 主队匹配%d 客队匹配%d%s" % (p, nh, na, md_s))


if __name__ == "__main__":
    main()
