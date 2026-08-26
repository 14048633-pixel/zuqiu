# -*- coding: utf-8 -*-
"""拉取已完赛结果 + 方向对账 (v2: 队名+时间匹配, 不依赖id)"""
import sys, os, json, io, re, unicodedata, urllib.request, collections
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import settle_batch as sb

BJT = timezone(timedelta(hours=8))
TOK = ""
for l in io.open(os.path.join(ROOT, ".env"), encoding="utf-8"):
    if l.startswith("BZZOIRO_API_KEY="):
        TOK = l.split("=", 1)[1].strip().strip('"').strip("'")

def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^a-z0-9]+", "", s.lower())

def bsd_events(league_id, date_from, date_to):
    out, off = [], 0
    while True:
        u = ("https://sports.bzzoiro.com/api/v2/events/?league_id=%d&status=finished"
             "&date_from=%s&date_to=%s&limit=100&offset=%d" % (league_id, date_from, date_to, off))
        req = urllib.request.Request(u, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + TOK})
        d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
        rows = d.get("results") or []
        out.extend(rows)
        if not d.get("next") or not rows:
            break
        off += len(rows)
    return out

def main():
    ana_f = sorted([x for x in os.listdir(os.path.join(ROOT, "analysis_records"))
                    if x.startswith("scan24h_analysis_") and x.endswith(".json")])[-1]
    ana = json.load(io.open(os.path.join(ROOT, "analysis_records", ana_f), encoding="utf-8"))
    val = json.load(io.open(os.path.join(ROOT, "analysis_records", "scan24h_valuable_20260822_0105.json"), encoding="utf-8"))
    # 场次 -> league_id (按队名)
    def key(h, a): return (norm(h), norm(a))
    id_map = {}
    for m in val["matches"]:
        id_map[key(m["home"], m["away"])] = m["league_id"]
    now = datetime.now(BJT)
    date_from = (now - timedelta(days=2)).strftime("%Y-%m-%dT00:00:00Z")
    date_to = (now + timedelta(days=1)).strftime("%Y-%m-%dT23:59:59Z")
    league_ids = {m["league_id"] for m in val["matches"]}
    all_ev = []
    for lid in sorted(league_ids):
        try:
            evs = bsd_events(lid, date_from, date_to)
            all_ev.extend(evs)
            print("league_id=%d -> %d finished" % (lid, len(evs)))
        except Exception as e:
            print("league_id=%d ERR %r" % (lid, e))
    ev_index = collections.defaultdict(list)
    for ev in all_ev:
        h, a = ev.get("home_team"), ev.get("away_team")
        if h and a:
            ev_index[key(h, a)].append(ev)
    settled = []
    for m in ana["matches"]:
        h, a = m["home"], m["away"]
        k = key(h, a)
        cands = ev_index.get(k, [])
        if not cands:
            # 模糊: home 匹配 + 时间接近
            for hh, lst in ev_index.items():
                if hh[0] == norm(h) and abs(len(hh[0]) - len(norm(h))) <= 6:
                    cands.extend(lst)
        best_ev = None
        for ev in cands:
            try:
                kt = datetime.fromisoformat((ev.get("event_date") or "").replace("Z", "+00:00")).astimezone(BJT)
            except Exception:
                continue
            try:
                kt_m = datetime.strptime(m["ct"], "%m-%d %H:%M").replace(year=2026, tzinfo=BJT)
            except Exception:
                continue
            if abs((kt - kt_m).total_seconds()) <= 4 * 3600 and norm(ev.get("away_team")) == norm(a):
                best_ev = ev
                break
            if best_ev is None and abs((kt - kt_m).total_seconds()) <= 4 * 3600 and norm(ev.get("home_team")) == norm(h):
                best_ev = ev
        if not best_ev:
            continue
        hg, ag = best_ev.get("home_score"), best_ev.get("away_score")
        if hg is None or ag is None:
            continue
        di = m.get("direction") or {}
        name = di.get("name")
        res = sb.settle_leg(name, di.get("odds") or 1.0, int(hg), int(ag)) if name else None
        settled.append({
            "ct": m["ct"], "league": m["league"], "home": h, "away": a,
            "score": "%d-%d" % (hg, ag), "hg": int(hg), "ag": int(ag),
            "direction_name": name, "direction_odds": di.get("odds"),
            "wdl_name": di.get("wdl_name"), "wdl_prob": di.get("wdl_prob"),
            "dir_result": res[0] if res else None,
            "vetoed": bool(di.get("vetoed")), "veto_reason": di.get("veto_reason"),
            "risk": m.get("risk_tags", []), "best_bet": m.get("best_bet"),
        })
    settled.sort(key=lambda x: x["ct"])
    outp = os.path.join(ROOT, "analysis_records", "scan24h_settle_%s.json" % now.strftime("%Y%m%d_%H%M"))
    json.dump({"ts": now.isoformat(), "n_settled": len(settled), "settled": settled},
              open(outp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    n_dir = sum(1 for s in settled if s["direction_name"])
    n_win = sum(1 for s in settled if s["dir_result"] == "win")
    n_push = sum(1 for s in settled if s["dir_result"] == "push")
    n_lose = sum(1 for s in settled if s["dir_result"] == "lose")
    n_half = sum(1 for s in settled if s["dir_result"] == "half")
    n_unk = sum(1 for s in settled if s["direction_name"] and s["dir_result"] is None)
    print("\n== 已完赛 %d 场 (有方向 %d) ==" % (len(settled), n_dir))
    print("方向: 命中 %d / 走水 %d / 半赢 %d / 未中 %d / 未知 %d" % (n_win, n_push, n_half, n_lose, n_unk))
    if n_dir - n_push > 0:
        print("方向命中率(不含走水): %.1f%%" % (100.0 * (n_win + 0.5 * n_half) / (n_dir - n_push)))
    print("saved:", outp)

if __name__ == "__main__":
    main()
