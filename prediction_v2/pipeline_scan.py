# -*- coding: utf-8 -*-
"""统一流水线入口: 拉取/复用缓存 -> 合并(教练/阵型/伤停/BSD交叉) -> 模型扫描 -> 数据完整性卡 + 缺口清单
============================================================
用法:
  python prediction_v2/pipeline_scan.py                     # 默认: 用BSD v2缓存+BSD v1教练, 48h窗口
  python prediction_v2/pipeline_scan.py --live              # 临场口径: snap=开赛前30min
  python prediction_v2/pipeline_scan.py --json xxx.json     # 指定BSD v2缓存
  python prediction_v2/pipeline_scan.py --v1 yyy.json       # 指定BSD v1 events(教练)
  python prediction_v2/pipeline_scan.py --squads zzz.json   # 指定球队注册名单(伤停位置兜底)

输出: analysis_records/pipeline_YYYYMMDD_HHMM.json/.md
  - 每场: 数据完整性卡(攻防/赔率/BSD/教练/阵型/伤停) + λ/方向/EV/星级/否决
  - 缺口清单: 队名未匹配 / 教练未覆盖 / 阵型缺失 / 伤停位置未知 / 无独立攻防 / 无赔率
"""
import argparse, io, json, os, sys, collections
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "prediction_v2"))
import scan_upcoming as SC
import coach_quant as cq

BJT = timezone(timedelta(hours=8))
META_DIV = {"欧冠资格": "欧冠", "欧冠": "欧冠"}  # 教练缓存池联赛名映射(其余联赛名=缓存池名)


def load_json(path):
    if not path or not os.path.exists(path):
        return None
    try:
        return json.load(io.open(path, encoding="utf-8"))
    except Exception:
        return None


LEAGUE_MAP = {}
def _load_league_map():
    global LEAGUE_MAP
    p = os.path.join(ROOT, "strategy_data", "leagues_map.json")
    try:
        LEAGUE_MAP = json.load(io.open(p, encoding="utf-8")).get("map", {})
    except Exception:
        LEAGUE_MAP = {}

def build_coach_map(v1):
    """BSD v1 events -> {eid: {home: coach, away: coach}}"""
    out = {}
    for ev in (v1 or {}).get("events") or []:
        eid = str(ev.get("id"))
        out[eid] = {"home": ev.get("home_coach") or {}, "away": ev.get("away_coach") or {}}
    return out


def squad_pos_map(squads):
    """bsd_squads缓存 -> {team_id: {player_id: position}}"""
    out = {}
    for tid, rec in (squads or {}).items():
        m = {}
        for p in (rec.get("players") or []):
            if p.get("id") is not None:
                m[p["id"]] = (p.get("position") or "").strip() or "?"
        out[str(tid)] = m
    return out


def build_info(eid, v2rec, coach, squads_pos):
    """由BSD v2记录构建 matches_info 结构(教练/当场阵型/位置伤停/BSD交叉)."""
    pred = (v2rec or {}).get("prediction") or {}
    ev = pred.get("event") or {}
    od = ((v2rec or {}).get("odds") or {}).get("odds") or {}
    lus = (v2rec or {}).get("lineups") or {}
    lu = lus.get("lineups") or {}
    tid = {"home": (lu.get("home") or {}).get("team_id"), "away": (lu.get("away") or {}).get("team_id")}
    pos_of = {}
    for side in ("home", "away"):
        for p in ((lu.get(side) or {}).get("players") or []):
            pos_of[(side, p.get("id"))] = (p.get("position") or "").strip() or "?"
        for pid, pos in (squads_pos.get(str(tid[side])) or {}).items():
            pos_of.setdefault((side, pid), pos)
    inj = {"home": [], "away": []}
    for side in ("home", "away"):
        for rec in (lus.get("unavailable_players") or {}).get(side) or []:
            inj[side].append({"name": rec.get("name") or "?", "position": pos_of.get((side, rec.get("id")), "?"),
                              "status": rec.get("status") or "injured", "reason": rec.get("reason") or ""})
    mk = pred.get("markets") or {}
    return {
        "bsd_coaches": {"home": coach.get("home") or {}, "away": coach.get("away") or {}},
        "bsd_lineups": {
            "formation": {"home": (lu.get("home") or {}).get("formation") or "",
                          "away": (lu.get("away") or {}).get("formation") or ""},
            "coach": {"home": (coach.get("home") or {}).get("preferred_formation") or "",
                      "away": (coach.get("away") or {}).get("preferred_formation") or ""},
        },
        "injuries": inj,
        "bsd_prediction": {"expected_goals": mk.get("expected_goals") or {},
                           "recommendations": (pred.get("recommendations") or {}),
                           "confidence": (pred.get("model") or {}).get("confidence"),
                           "markets": mk},
        "bsd_odds": {"consensus": od},
        "_team_id": tid,
    }


def build_match(league, home, away, ct, od, snap_iso):
    return {
        "league": league, "home": home, "away": away, "ct": ct, "snap": snap_iso,
        "h2h": {"home": od.get("home_win"), "draw": od.get("draw"), "away": od.get("away_win")},
        "totals": {"line": 2.5, "over_price": od.get("over_25_goals"), "under_price": od.get("under_25_goals")},
    }


def src_label(src):
    return {"cur": "当季", "prev": "上季", "old": "旧季", "market": "市场兜底",
            "baseline": "联赛基准", "bsd": "BSD兜底", None: "缺失"}.get(src, src or "缺失")


def merge_bsd_stats(team_stats, index, bsd):
    """BSD历史攻防兜底: 数据池无覆盖联赛(保甲/希腊超等)的球队并入 team_stats(div=BSD)."""
    stats = (bsd or {}).get("stats") or {}
    n = 0
    for k, rec in stats.items():
        if not k or not rec.get("n_home") and not rec.get("n_away"):
            continue
        if k not in team_stats:
            team_stats[k] = {}
        if "BSD" not in team_stats[k]:
            team_stats[k]["BSD"] = dict(rec)
            n += 1
        index.setdefault(k, k)
    return n


def make_card(m, r, info, coach_mods, snap_age_h, league_cal):
    """数据完整性卡: 每项标注有/无/过期/未知, 绝不静默."""
    ds = r.get("data_src") or {}
    card = {"attack": {"home": src_label(ds.get("home")), "away": src_label(ds.get("away"))}}
    od_ok = bool((m.get("h2h") or {}).get("home"))
    tt_ok = bool((m.get("totals") or {}).get("line"))
    sp_ok = bool((m.get("spread") or {}).get("home_price"))
    if snap_age_h is None:
        age_s = "未知"
    elif snap_age_h > SC.SNAPSHOT_STALE_HOURS:
        age_s = "过期%.1fh" % snap_age_h
    elif snap_age_h < 0:
        age_s = "赛后才拉"
    else:
        age_s = "新鲜%.1fh" % snap_age_h
    card["odds"] = {"1x2": ("有(" + age_s + ")" if od_ok else "缺失"),
                    "大小": ("有" if tt_ok else "缺失"), "让球": ("有" if sp_ok else "缺失"),
                    "snap_age_h": snap_age_h}
    bsd = r.get("bsd") or {}
    card["bsd"] = {"odds": bool((info or {}).get("bsd_odds", {}).get("consensus")),
                   "prediction": bool((info or {}).get("bsd_prediction", {}).get("expected_goals")),
                   "lineups": bool((info or {}).get("bsd_lineups")),
                   "lam_dev": bsd.get("lam_dev")}
    cm = coach_mods or {}
    card["coach"] = {"home": cm.get("h_name", "未覆盖"), "away": cm.get("a_name", "未覆盖"),
                     "h_atk": cm.get("h_atk"), "a_atk": cm.get("a_atk"),
                     "h_sample": cm.get("h_sample"), "a_sample": cm.get("a_sample")}
    fm = r.get("formation") or {}
    card["formation"] = {"home": (fm.get("home") or "缺失") + ("(当场)" if fm.get("home") else ""),
                         "away": (fm.get("away") or "缺失") + ("(当场)" if fm.get("away") else ""),
                         "src": fm.get("src")}
    injp = r.get("injury_pos") or {}
    inj = (info or {}).get("injuries") or {}
    def _inj_disp(n, unknown):
        if not n:
            return "0"
        return ("%d人(位置未知%d)" % (n, unknown)) if unknown else "%d人" % n
    card["injury"] = {"home": _inj_disp(len(inj.get("home") or []), injp.get("unknown", 0)),
                      "away": _inj_disp(len(inj.get("away") or []), injp.get("unknown", 0)),
                      "critical": bool(injp.get("critical"))}
    indep = not any("非独立数据" in t for t in r.get("risk_tags", []))
    card["independent"] = indep
    return card


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", default="analysis_records/bsd_v2_2026-08-17.json")
    ap.add_argument("--v1", default="analysis_records/bzzoiro_events_2026-08-17.json")
    ap.add_argument("--squads", default="analysis_records/bsd_squads_2026-08-17.json")
    ap.add_argument("--live", action="store_true", help="临场口径: snap=开赛前30分钟")
    ap.add_argument("--bsd-stats", default="data/raw/football_data/bsd_league_stats.json")
    ap.add_argument("--odds", default="", help="the-odds-api 最新盘口 overlay JSON, 覆盖BSD共识盘")
    ap.add_argument("--out", default="")
    args = ap.parse_args()

    v2 = load_json(os.path.join(ROOT, args.json))
    v1 = load_json(os.path.join(ROOT, args.v1))
    squads = load_json(os.path.join(ROOT, args.squads))
    if not v2 or not v2.get("data"):
        print("❌ BSD v2 缓存缺失或为空: %s" % args.json)
        return
    team_stats, lavg, index = SC.load_team_stats()
    bsd_stats = load_json(os.path.join(ROOT, args.bsd_stats))
    _n_bsd = merge_bsd_stats(team_stats, index, bsd_stats)
    if _n_bsd:
        print("✔ BSD历史攻防兜底: %d 队并入数据池" % _n_bsd)
    coach_cache = cq.load_cache()
    _load_league_map()
    coach_map = build_coach_map(v1)
    squads_pos = squad_pos_map(squads)
    overlay = {}
    if args.odds and os.path.exists(os.path.join(ROOT, args.odds)):
        overlay = (load_json(os.path.join(ROOT, args.odds)) or {}).get("overlay") or {}
        print("✔ the-odds-api 盘口 overlay: %d 场" % len(overlay))
    now = datetime.now(timezone.utc)
    t0 = now.strftime("%Y%m%d_%H%M")

    results = []
    for eid, d in v2["data"].items():
        pred = d.get("prediction") or {}
        ev = pred.get("event") or {}
        home = ev.get("home_team") or "?"
        away = ev.get("away_team") or "?"
        league_raw = ev.get("league_name") or "?"
        league = LEAGUE_MAP.get(league_raw, league_raw)
        if league == league_raw and league_raw not in ("?", ""):
            league = "未知联赛:" + league_raw
        od = (d.get("odds") or {}).get("odds") or {}
        ov = overlay.get(eid)
        odds_src = "BSD共识"
        if ov and (ov.get("h2h") or {}).get("home"):
            od = {"home_win": ov["h2h"]["home"], "draw": ov["h2h"]["draw"], "away_win": ov["h2h"]["away"],
                  "over_25_goals": (ov.get("totals") or {}).get("over"),
                  "under_25_goals": (ov.get("totals") or {}).get("under")}
            odds_src = "the-odds-api(" + (ov.get("source") or "?") + ")"
        try:
            ct = datetime.fromisoformat(str(ev.get("event_date") or "").replace("Z", "+00:00"))
        except Exception:
            ct = now
        snap = (ct - timedelta(minutes=30)).isoformat() if args.live else \
               ((ov.get("snap_iso") or now.isoformat()) if ov else now.isoformat())
        info = build_info(eid, d, coach_map.get(eid) or {}, squads_pos)
        lg_coach = META_DIV.get(league, league)
        cm = cq.match_mods(coach_cache, info, lg_coach) if (info and coach_cache) else {}
        m = build_match(league, home, away, ct, od, snap)
        if ov and (ov.get("spread") or {}).get("home_price"):
            sp = ov["spread"]
            m["spread"] = {"hdp_home": sp["hdp_home"], "home_price": sp["home_price"],
                           "away_price": sp["away_price"]}
            odds_src += "+让球"
        m["coach_mods"] = cm
        r = SC.analyze_match(m, team_stats, lavg, index)
        r["info"] = info
        r["coach"] = cm
        r["bsd"] = SC._bsd_cross_check(r, info)
        r["formation"] = SC._formation_check(r, info)
        r["injury_pos"] = SC._injury_pos_check(r, info)
        try:
            _sd = datetime.fromisoformat(str(m["snap"]).replace("Z", "+00:00"))
            if _sd.tzinfo is None:
                _sd = _sd.replace(tzinfo=timezone.utc)
            snap_age_h = round((m["ct"] - _sd).total_seconds() / 3600.0, 1)
        except Exception:
            snap_age_h = None
        card = make_card(m, r, info, cm, snap_age_h, None)
        results.append({"id": eid, "league": league, "home": home, "away": away,
                        "odds_src": odds_src,
                        "ct": ct.astimezone(BJT).strftime("%m-%d %H:%M"),
                        "card": card, "result": {k: r[k] for k in
                            ("lambda", "wdl", "market_fair", "best_bet", "direction",
                             "star", "ev_tier", "risk_tags", "notes")}})

    # ===== 打印 =====
    print("== 流水线扫描: %d 场 | 模式: %s ==" % (len(results), "临场(T-30min)" if args.live else "快照"))
    gaps = collections.Counter()
    for x in results:
        r = x["result"]; lam = r["lambda"]; bb = r["best_bet"]; di = r["direction"]; c = x["card"]
        line = "%s %-6s %s vs %s | λ%.2f/%.2f | " % (x["ct"], x["league"], x["home"][:16], x["away"][:14],
                                                     lam["home"], lam["away"])
        line += "[%s] " % x["odds_src"]
        if di:
            line += "方向:%s(ev%+.1f%%)" % (di["name"], di["ev"] * 100)
            if di.get("vetoed"):
                line += " ⛔" + di.get("veto_reason", "")
        else:
            line += "方向:无盘"
        if bb:
            line += " | BEST:%s ★%d[%s]" % (bb["name"], bb.get("star", 0), bb.get("ev_tier", "?"))
        print(line)
        # 缺口统计
        for side in ("home", "away"):
            if c["attack"][side] in ("市场兜底", "联赛基准", "缺失"):
                gaps["%s无独立攻防(%s)" % (side, x["home"] if side == "home" else x["away"])] += 1
        if not c["odds"]["1x2"].startswith("有"):
            gaps["无1X2盘口"] += 1
        if c["coach"]["home"] == "未覆盖":
            gaps["主教练未覆盖(%s)" % x["home"]] += 1
        if c["coach"]["away"] == "未覆盖":
            gaps["客教练未覆盖(%s)" % x["away"]] += 1
        if c["formation"]["home"].startswith("缺失") or c["formation"]["away"].startswith("缺失"):
            gaps["阵型缺失"] += 1
        for side in ("home", "away"):
            if c["injury"][side] != "0" and "位置未知" in c["injury"][side]:
                gaps["伤停位置未知(%s)" % x["home" if side == "home" else "away"]] += 1
    print("\n== 缺口清单 ==")
    for k, v in gaps.most_common():
        print("  ⚠ %s × %d" % (k, v))
    if not gaps:
        print("  ✔ 无缺口")
    n_bet = sum(1 for x in results if x["result"].get("best_bet"))
    print("\n可出best_bet: %d/%d" % (n_bet, len(results)))

    out_path = args.out or os.path.join(ROOT, "analysis_records", "pipeline_%s.json" % t0)
    with io.open(out_path, "w", encoding="utf-8") as f:
        json.dump({"ts": now.isoformat(), "mode": "live" if args.live else "snapshot",
                   "gaps": dict(gaps), "results": results}, f, ensure_ascii=False, indent=1)
    print("saved:", out_path)


if __name__ == "__main__":
    main()
