# -*- coding: utf-8 -*-
"""Bzzoiro Sports Data (BSD) 伤停数据拉取 + 合并进 matches_info
============================================================
用法:
  # 1) 拉取 + 合并(所有 analysis_records/matches_info_*.json)
  python prediction_v2/injuries_bzzoiro.py --date 2026-08-16
  # 2) 只合并已有 events json(不消耗接口)
  python prediction_v2/injuries_bzzoiro.py --date 2026-08-16 --no-fetch
  # 3) 指定单个 matches_info 文件
  python prediction_v2/injuries_bzzoiro.py --date 2026-08-16 --info analysis_records/matches_info_20260816.json

数据: GET https://sports.bzzoiro.com/api/events/?full=true&date_from=..&date_to=..
  Token: .env 的 BZZOIRO_API_KEY (Authorization: Token ...)
  Event.unavailable_players = {home:[{name,status,reason,expected_return}], away:[...]}
合并: 按侧覆盖 match["injuries"]{home,away,home_covered,away_covered,sources} + intel 文本
队名匹配: 复用 injuries_apifootball._team_key (词序无关, 忽略 fc/cf)
"""
import argparse, glob, io, json, os, sys, time
import requests

from injuries_apifootball import (ROOT, _team_key, summarize, intel_text,
                                  merge_into_info)

BASE = "https://sports.bzzoiro.com/api"
ENV_FILE = os.path.join(ROOT, ".env")


def load_token():
    if not os.path.exists(ENV_FILE):
        return ""
    for line in io.open(ENV_FILE, encoding="utf-8"):
        s = line.strip()
        if s.startswith("BZZOIRO_API_KEY="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


TOKEN = load_token()
HEADERS = {"User-Agent": "Mozilla/5.0", "Accept": "application/json",
           "Authorization": "Token " + TOKEN}


def fetch_events(date, tries=3, timeout=90):
    """GET /api/events/?full=true 分页拉取当天赛事 -> [event...]; 失败返回 None."""
    if not TOKEN:
        print("  ⚠️ 无 BZZOIRO_API_KEY(.env), 跳过拉取")
        return None
    for attempt in range(1, tries + 1):
        out = []
        try:
            off = 0
            while True:
                r = requests.get(BASE + "/events/", params={
                    "date_from": date + "T00:00:00Z", "date_to": date + "T23:59:59Z",
                    "limit": 50, "offset": off, "full": "true"}, headers=HEADERS, timeout=timeout)
                if r.status_code != 200:
                    print("  HTTP %s: %s" % (r.status_code, r.text[:150]))
                    raise RuntimeError("bad status %s" % r.status_code)
                res = r.json().get("results") or []
                out += res
                if len(res) < 50:
                    return out
                off += 50
                time.sleep(0.3)
        except Exception as e:
            print("  第%d/%d次失败: %s" % (attempt, tries, type(e).__name__))
            if attempt < tries:
                time.sleep(5)
    return None


def build_team_map(events):
    """events -> {team_key: [{name,status,reason,expected_return}, ...]} (按球员+队去重)."""
    m = {}
    seen = set()
    for ev in events:
        up = ev.get("unavailable_players") or {}
        for side, field in (("home_team", "home"), ("away_team", "away")):
            tname = ev.get(side)
            recs = up.get(field) or []
            if not tname or not recs:
                continue
            k = _team_key(tname)
            for rec in recs:
                dk = (rec.get("name"), k)
                if dk in seen:
                    continue
                seen.add(dk)
                m.setdefault(k, []).append({
                    "name": rec.get("name") or "?",
                    "status": (rec.get("status") or "injured").strip(),
                    "reason": (rec.get("reason") or "").strip(),
                    "expected_return": rec.get("expected_return"),
                })
    return m


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--date", required=True, help="YYYY-MM-DD")
    ap.add_argument("--no-fetch", action="store_true", help="只合并已有 bzzoiro_events json")
    ap.add_argument("--info", help="指定 matches_info json(默认全部 matches_info_*.json)")
    args = ap.parse_args()

    raw_path = os.path.join(ROOT, "analysis_records", "bzzoiro_events_%s.json" % args.date)
    if args.no_fetch:
        if not os.path.exists(raw_path):
            print("无已有 events 文件: %s" % raw_path)
            return
        events = json.load(io.open(raw_path, encoding="utf-8")).get("events") or []
        print("使用已有数据 %s (%d 场)" % (raw_path, len(events)))
    else:
        print("拉取 %s BSD赛事(全量full)..." % args.date)
        events = fetch_events(args.date)
        if events is None:
            print("拉取失败, 终止(可重试或 --no-fetch 复用已有文件)")
            return
        with io.open(raw_path, "w", encoding="utf-8") as f:
            json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                       "date": args.date, "n_events": len(events), "events": events},
                      f, ensure_ascii=False, indent=1)
        print("已存 %s (%d 场)" % (raw_path, len(events)))

    team_map = build_team_map(events)
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
        nh, na = merge_into_info(d.get("matches") or [], team_map, src="bsd")
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
        print("合并 %s: 主队命中%d 客队命中%d%s" % (p, nh, na, md_s))


if __name__ == "__main__":
    main()
