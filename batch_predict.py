# -*- coding: utf-8 -*-
"""新系统批量预测(正式版, 2026-09-03): 赛程 -> composite盘 -> match_model_report -> 1X2/OU.

用法:
  python batch_predict.py scan24h_20260903_1949.json [out.json] [--track]
输入: BSD scan24h JSON (由 D:\\足球分析\\_build_scan24h_generic.py 产出, 待迁移)
输出: 每场 best/legs (1X2 用 composite 实时盘优先, OU 价格始终 BSD),
      --track 时把正EV的 best(1X2 或 OU)写入 live_tracker.json (闭环, OU 按 mkt 结算).
规则: 平局预警>=26%禁主/客; 低样本(<60)禁主/客; 数据缺失禁1X2; OU 常规区间(35-65%)可参考.
"""
import sys, io, os, json
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
from pathlib import Path

import pandas as pd

from data_loader import load_data
from model import poisson_fit
from match_report import match_model_report
from league_router import has_data_missing
from shin_devig import devig_shin, devig3  # P1: Shin 法去水, devig3 保留 fallback 名
from lineup_intel import fetch_lineups, injury_coefs, injury_delta  # P0/P1/P5: 伤停λ修正 + 复盘明细

ROOT = Path(r"D:\足球分析")

# 加载 .env(父目录): BZZOIRO_API_KEY / THE_ODDS_API_KEY / FOOTBALL_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except Exception:
    pass

LG_KEY = {
    "Premier League": "E0", "La Liga": "SP1", "Bundesliga": "D1",
    "Serie A": "I1", "Ligue 1": "F1", "Eredivisie": "N1",
    "Liga Portugal Betclic": "P1", "Pro League": "B1",
    "Trendyol Super Lig": "T1", "Ekstraklasa": "POL",
    "Eliteserien": "NO1", "Danish Superliga": "DNK",
    "MLS": "MLS", "Liga MX Apertura": "MX1",
    "Brasileirão Serie A": "BR", "Segunda División": "SP2",
    "Championship": "E1", "League One": "E2", "League Two": "E3",
    "Coppa Italia": "I1", "DFB Pokal": "D1", "Copa do Brasil": "BR",
    "J1 League": "JP1", "Saudi Pro League": "SAU",
    "Super League": "SW1", "Puchar Polski": "POL",
}


def devig3(h, d, a):
    """Shin 法去水(2026-09-03 P1 替换简单归一). devig3 名保留兼容, 实现走 Shin."""
    return devig_shin(h, d, a)


def name_warnings(home, away):
    from odds_source import team_matcher
    tm = team_matcher()
    out = []
    for side, name in (("主", home), ("客", away)):
        if not tm.resolve(name):
            out.append("%s队'%s'本地无匹配(用联赛均值兜底)" % (side, name))
    return out


def bsd_odds_fallback(event_id):
    """BSD 共识盘: 直接请求 BSD(不依赖旧系统 bsd_extra), 含 1X2 + OU 价格.
    返回 (1X2, over25价, under25价, src, est); 缺项为 None."""
    try:
        import requests
        key = os.environ.get("BZZOIRO_API_KEY", "")
        if not key:
            return None, None, None, None, None
        r = requests.get("https://sports.bzzoiro.com/api/v2/events/%d/odds/" % int(event_id),
                         headers={"Authorization": "Token " + key, "Accept": "application/json"},
                         timeout=10)
        od = (r.json() or {}).get("odds") or {}
        need = ("home_win", "draw", "away_win", "over_25_goals", "under_25_goals")
        if all(k in od for k in need):
            return ((od["home_win"], od["draw"], od["away_win"]),
                    od.get("over_25_goals"), od.get("under_25_goals"), "bsd", False)
    except Exception:
        pass
    return None, None, None, None, None


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return 1
    in_fp = ROOT / "analysis_records" / sys.argv[1]
    out_fp = sys.argv[2] if len(sys.argv) > 2 and not sys.argv[2].startswith("--") \
        else ROOT / "analysis_records" / in_fp.name.replace("scan24h_", "v2_best_scan_")
    track = "--track" in sys.argv

    d = json.load(io.open(in_fp, encoding="utf-8"))
    ms = [m for m in d["matches"] if m.get("league") in LG_KEY]
    print("可跑场次(有本地数据):", len(ms), "/", len(d["matches"]))

    df = load_data()
    match_date = pd.Timestamp.now().normalize()
    train = df[df["date"] < match_date]
    fit = poisson_fit(train)
    print("拟合完成, 联赛数:", len(fit), flush=True)

    from odds_source import fetch_odds

    out = []
    for i, m in enumerate(ms, 1):
        lg = LG_KEY[m["league"]]
        print("[%d/%d] %s %s vs %s ..." % (i, len(ms), m["league"], m["home"], m["away"]), flush=True)
        ko = pd.Timestamp(m.get("kickoff_iso") or m.get("ct") or match_date)
        if getattr(ko, "tzinfo", None) is not None:  # BSD ISO 带 UTC -> 转 naive, 对齐本地库
            ko = ko.tz_localize(None)
        odds = over_price = under_price = None
        src = None
        est = False
        # OU 价格始终从 BSD 拿(composite/theoddsapi 只给 1X2 无 OU); 顺带拿 BSD 1X2 作兜底
        bsd_1x2, over_price, under_price, bsrc, best_ = bsd_odds_fallback(m.get("id"))
        if os.getenv("BATCH_ODDS_SRC", "composite") == "composite":
            try:
                od = fetch_odds(m["home"], m["away"], lg, ko)
                if od and od.get("odds"):
                    odds, src, est = tuple(od["odds"]), "composite", bool(od.get("estimated"))
            except Exception:
                odds = None
        if not odds:
            odds, src, est = bsd_1x2, bsrc, best_
        if not odds:
            print("  NOODDS", flush=True)
            continue
        if not all(isinstance(x, (int, float)) and x > 1 for x in odds[:3]):
            print("  无效赔率(跳过)", flush=True)
            continue
        # P0(2026-09-05): 批量路径接入 BSD 伤停λ修正(单场 generate_report 已有, 批量此前是裸统计)
        injury_coef = (1.0, 1.0)
        injury_note = None
        injury_detail = {"home": {}, "away": {}}  # P5-fix(09-05 18:06): 用 dict 而非 list, 兼容 fetch_lineups=None
        _eid = m.get("id")
        try:
            _lu = fetch_lineups(_eid) if _eid else None
            if _lu:
                injury_coef = injury_coefs(_lu)
                injury_detail = injury_delta(_lu)
                _sig = [d for d in (injury_detail.get("home", {}).get("detail") or []) +
                        (injury_detail.get("away", {}).get("detail") or []) if d]
                if injury_coef != (1.0, 1.0):
                    injury_note = "伤停λ修正 主x%.3f 客x%.3f (%d人)" % (
                        injury_coef[0], injury_coef[1], len(_sig))
        except Exception as _ie:
            print("  伤停拉取失败 %s" % repr(_ie)[:80], flush=True)
        row = {"league": lg, "home": m["home"], "away": m["away"], "date": ko}
        try:
            r = match_model_report(fit, train, row, market_odds=tuple(odds),
                                   injury_coef=injury_coef)
        except Exception as e:
            print("  ERR", repr(e)[:100], flush=True)
            continue
        warns = (r.get("data_warnings") or []) + name_warnings(m["home"], m["away"])
        missing = has_data_missing(warns)
        ens = r["ensemble"]
        ph, pd_, pa = ens["home"], ens["draw"], ens["away"]
        fh, fd, fa = devig3(*odds)
        draw_warn = (fd * 100.0) >= 26.0
        fc = ((fit or {}).get(lg) or {}).get("teams", {})
        legs = []
        for name, p, pr, fair in (("主胜", ph, odds[0], fh),
                                  ("平局", pd_, odds[1], fd),
                                  ("客胜", pa, odds[2], fa)):
            if not (isinstance(pr, (int, float)) and pr > 1):
                continue
            ev = p * pr - 1.0
            if ev <= 0:
                continue
            # P0.1(2026-09-04): star 双条件 - 3星需"高置信(校准后p>=45%)+高价值(ev>=15%)",
            # 2星需 p>=34%+ev>=10%; 低概率冷门腿不再因 EV 虚高而升 3 星
            star = 3 if (ev >= 0.15 and p >= 0.45) else (2 if (ev >= 0.10 and p >= 0.34) else 1)
            l2 = {"name": name, "prob": round(p * 100, 1), "odds": pr,
                  "ev": round(ev * 100, 1), "star": star, "mkt": "1x2"}
            # P0.2(2026-09-04): 模型 vs 市场去水概率 大分歧(>18pp) 封顶2星 + 风控标注
            _disp = p - fair
            if abs(_disp) > 0.18:
                l2["note_big_div"] = "模型vs市场大分歧(%.0fpp)封顶2星" % (abs(_disp) * 100)
                l2["star"] = min(l2["star"], 2)
            if missing:
                l2["veto_data"] = "数据缺失禁1X2: " + missing
                l2["star"] = 0
            elif draw_warn and name in ("主胜", "客胜"):
                l2["veto_draw"] = "平局预警%.1f%%禁主/客胜" % (fd * 100)
                l2["star"] = 0
            elif fc and name in ("主胜", "客胜"):
                try:
                    from odds_source import team_matcher as _tm_mod
                    _tm = _tm_mod.team_matcher()
                    _hm = _tm.resolve(m["home"]) or m["home"]
                    _am = _tm.resolve(m["away"]) or m["away"]
                    if _hm not in fc and m["home"] in fc:
                        _hm = m["home"]
                    if _am not in fc and m["away"] in fc:
                        _am = m["away"]
                    _nh = fc.get(_hm, {}).get("n", 999)
                    _na = fc.get(_am, {}).get("n", 999)
                    if min(_nh, _na) < 60:
                        l2["veto_low"] = "低样本(<60)禁主/客胜"
                        l2["star"] = 0
                except Exception:
                    pass
            if l2["star"] > 0:
                legs.append(l2)
        best = max(legs, key=lambda x: x["ev"]) if legs else None
        po = r["over_2_5"]
        # OU 腿(仅 BSD 盘提供大小球价格时): 数据缺失只放行常规区间(35-65%); OU 互斥取一
        ou_legs = []
        for nm, p, pr in (("大2.5", po, over_price), ("小2.5", 1.0 - po, under_price)):
            if not (isinstance(pr, (int, float)) and pr > 1):
                continue
            ev = p * pr - 1.0
            if ev <= 0:
                continue
            # P0.1(2026-09-04): OU 与 1X2 同款 star 双条件
            star = 3 if (ev >= 0.15 and p >= 0.45) else (2 if (ev >= 0.10 and p >= 0.34) else 1)
            l2 = {"name": nm, "prob": round(p * 100, 1), "odds": pr,
                  "ev": round(ev * 100, 1), "star": star, "mkt": "ou"}
            # P0.2(2026-09-04): OU 模型 vs 市场隐含(1/价, 含margin粗略) 大分歧封顶2星
            _mki = 1.0 / pr
            if abs(p - _mki) > 0.18:
                l2["note_big_div"] = "模型vs市场大分歧(%.0fpp)封顶2星" % (abs(p - _mki) * 100)
                l2["star"] = min(l2["star"], 2)
            if missing:
                if not (0.35 <= p <= 0.65):
                    l2["veto_data"] = "数据缺失+极端OU(%s)拦截" % nm
                    l2["star"] = 0
                else:
                    l2["note_data_ou"] = "数据缺失场放行OU"
            if l2["star"] > 0:
                ou_legs.append(l2)
        if len(ou_legs) > 1:
            _keep = max(ou_legs, key=lambda x: x["ev"])
            for l in ou_legs:
                if l is not _keep:
                    ou_legs.remove(l)
                    _keep["conflict_same_mkt"] = "OU组二选一, 丢弃%s" % l["name"]
        legs.extend(ou_legs)
        legs = [l for l in legs if l.get("star", 0) > 0]
        best = max(legs, key=lambda x: x["ev"]) if legs else None
        rec = {
            "ko_bjt": m["kickoff"], "league": m["league"], "home": m["home"],
            "away": m["away"], "model_wdl": [round(ph * 100, 1), round(pd_ * 100, 1),
                                             round(pa * 100, 1)],
            "market_wdl": [round(fh * 100, 1), round(fd * 100, 1), round(fa * 100, 1)],
            "xg": [round(r["expected_goals"]["home"], 2), round(r["expected_goals"]["away"], 2),
                   round(r["expected_goals"]["total"], 2)],
            "over25": round(po * 100, 1), "data_warnings": warns,
            "draw_warn_pct": round(fd * 100, 1), "bets": legs, "best": best,
            "injury_coef": list(injury_coef), "injury_note": injury_note,
            "injury_detail": {
                "home": (injury_detail.get("home", {}) or {}).get("detail")
                        if isinstance(injury_detail.get("home"), dict) else [],
                "away": (injury_detail.get("away", {}) or {}).get("detail")
                        if isinstance(injury_detail.get("away"), dict) else []},
            "odds_estimated": est,
            "odds_src": src,
        }
        out.append(rec)
        bbs = ("%s p%.0f%% @%.2f EV%+.1f%% ★%d" % (best["name"], best["prob"], best["odds"],
                                                    best["ev"], best["star"])) if best else "无正EV"
        print("  %s | 模型%.0f/%.0f/%.0f 市场%.0f/%.0f/%.0f | 大%.0f%% | BEST: %s%s%s"
              % (m["kickoff"], rec["model_wdl"][0], rec["model_wdl"][1], rec["model_wdl"][2],
                 rec["market_wdl"][0], rec["market_wdl"][1], rec["market_wdl"][2],
                 rec["over25"], bbs, " [est]" if est else "",
                 (" | " + injury_note) if injury_note else ""), flush=True)
        if track and best and best["star"] >= 1 and not est and odds:
            try:
                from tracker import record
                if best.get("mkt") == "ou":
                    # OU 腿: 市场隐含概率=1/价; odds 单元素; mkt=ou line=2.5
                    _price = best["odds"]
                    _edge = max(0.0, best["prob"] / 100.0 - 1.0 / _price) * 100.0
                    _tr = {"best_pick": best["name"], "ev_unit": best["ev"] / 100.0,
                           "stars": best["star"], "edge": _edge, "mkt": "ou", "line": 2.5,
                           "model_prob": [best["prob"] / 100.0],
                           "market_prob": [round(1.0 / _price, 4)],
                           "market_odds": [_price], "odds_estimated": False}
                else:
                    _edge = max(0.0, (best["prob"] / 100.0 -
                                      {"主胜": fh, "平局": fd, "客胜": fa}[best["name"]]) * 100.0)
                    _tr = {"best_pick": best["name"], "ev_unit": best["ev"] / 100.0,
                           "stars": best["star"], "edge": _edge, "mkt": "1x2", "line": None,
                           "model_prob": [ph, pd_, pa], "market_prob": [fh, fd, fa],
                           "market_odds": list(odds), "odds_estimated": False}
                record({"home": m["home"], "away": m["away"], "league": lg,
                        "date": ko, **_tr})
            except Exception as te:
                print("  TRACK FAIL", repr(te)[:100], flush=True)

    json.dump(out, io.open(out_fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved ->", out_fp)
    n = sum(1 for r in out if r["best"])
    print("有BEST:", n, "/", len(out), "| 总腿数:", sum(len(r.get("bets") or []) for r in out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
