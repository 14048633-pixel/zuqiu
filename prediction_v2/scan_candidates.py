"""今日候选比赛扫描（the-odds-api 赔率 + prediction_v2 泊松模型）

口径(生产回测): 小球2.5 + edge>=5% + 赔率>=2.00
用法:
  python scan_candidates.py [--csv output/today_matches.csv] [--hours 96]
  python scan_candidates.py --match-only   # 只测队名匹配, 不跑预测
"""
import argparse
import json
import math
import os
import sys
import unicodedata

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd

from src.predict_api import feature_row_from_dataset, score_feature_row
from src.team_names_cn import to_cn, display

HERE = os.path.dirname(os.path.abspath(__file__))
MIN_ODDS = 2.00   # 生产口径: 赔率>=2.00
EDGE = 0.05       # 生产口径: 边际>=5%
OU_LINE = 2.5

# the-odds-api -> football-data 队名 手工别名(兜底)
ALIAS = {
    "wolverhampton wanderers": "Wolves",
    "wolverhampton": "Wolves",
    "blackburn rovers": "Blackburn",
    "blackburn": "Blackburn",
    "hertha berlin": "Hertha",
    "hertha": "Hertha",
    "1. fc nurnberg": "Nurnberg",
    "fc nurnberg": "Nurnberg",
    "nurnberg": "Nurnberg",
    "1. fc magdeburg": "Magdeburg",
    "magdeburg": "Magdeburg",
    "vfl bochum": "Bochum",
    "bochum": "Bochum",
    "fc st. pauli": "St Pauli",
    "st. pauli": "St Pauli",
    "st pauli": "St Pauli",
    "eintracht braunschweig": "Braunschweig",
    "braunschweig": "Braunschweig",
    "sc telstar": "Telstar",
    "telstar": "Telstar",
    "real sociedad b": "Sociedad B",
    "cd castellon": "Castellon",
    "castellon": "Castellon",
    "cadiz cf": "Cadiz",
    "cadiz": "Cadiz",
    "celta vigo": "Celta",
    "granada cf": "Granada",
    "granada": "Granada",
    "fc utrecht": "Utrecht",
    "utrecht": "Utrecht",
    "psv eindhoven": "PSV Eindhoven",
    "willem ii": "Willem II",
    "nec nijmegen": "Nijmegen",
    "nijmegen": "Nijmegen",
    "sheffield united": "Sheffield United",
    "queens park rangers": "QPR",
    "qpr": "QPR",
    "west bromwich albion": "West Brom",
    "west brom": "West Brom",
    "middlesbrough": "Middlesbrough",
    "norwich city": "Norwich",
    "bristol city": "Bristol City",
    "stoke city": "Stoke",
    "bolton wanderers": "Bolton",
    "bolton": "Bolton",
    "preston north end": "Preston",
    "preston": "Preston",
    "derby county": "Derby",
    "derby": "Derby",
    "swansea city": "Swansea",
    "portsmouth": "Portsmouth",
    "charlton athletic": "Charlton",
    "charlton": "Charlton",
    "lincoln city": "Lincoln",
    "millwall": "Millwall",
    "birmingham city": "Birmingham",
    "holstein kiel": "Holstein Kiel",
    "greuther furth": "Greuther Furth",
    "1. fc heidenheim": "Heidenheim",
    "heidenheim": "Heidenheim",
    "1. fc kaiserslautern": "Kaiserslautern",
    "kaiserslautern": "Kaiserslautern",
    "karlsruher sc": "Karlsruhe",
    "karlsruhe": "Karlsruhe",
    "vfl osnabruck": "Osnabruck",
    "osnabruck": "Osnabruck",
    "alaves": "Alaves",
    "getafe": "Getafe",
    "espanyol": "Espanol",
    "espanol": "Espanol",
    "paris saint germain": "Paris SG",
    "psg": "Paris SG",
    "borussia monchengladbach": "M'gladbach",
    "bayer leverkusen": "Leverkusen",
    "leverkusen": "Leverkusen",
    "vfl wolfsburg": "Wolfsburg",
    "wolfsburg": "Wolfsburg",
    "andorra cf": "Andorra",
    "ad ceuta fc": "Ceuta",
    "ceuta": "Ceuta",
    "oviedo": "Oviedo",
    "albacete": "Albacete",
    "las palmas": "Las Palmas",
    "troyes": "Troyes",
    "paris fc": "Paris FC",
    "fulham": "Fulham",
    "chelsea": "Chelsea",
}


# 共享别名库(第二类): 与 scan_upcoming 共用 strategy_data/teams_alias.json, 归一化后合并进本地ALIAS
def _load_shared_aliases():
    try:
        _p = os.path.join(HERE, "..", "strategy_data", "teams_alias.json")
        if not os.path.exists(_p):
            return
        _d = json.load(io.open(_p, encoding="utf-8")).get("alias", {})
    except Exception:
        return
    for _ext, _std in _d.items():
        _nk = norm_name(_ext)
        if _nk and _nk not in ALIAS:
            ALIAS[_nk] = _std

def norm_name(s):
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))  # 去重音
    s = s.lower().replace(".", "").replace("&", "and").strip()
    for pre in ("1. fc ", "fc ", "cf ", "cd ", "sc ", "vfl ", "sv ", "bv ", "ss ",
                "as ", "ac ", "ud ", "de ", "club ", "real ", "borussia ", "royal "):
        if s.startswith(pre):
            s = s[len(pre):]
            break
    return s


_load_shared_aliases()


def match_team(league, name, teams_by_league):
    """把 the-odds-api 队名匹配到 football-data 数据集队名。"""
    key = norm_name(name)
    if key in ALIAS:
        return ALIAS[key]
    cands = teams_by_league.get(league, [])
    for c in cands:
        if norm_name(c) == key:
            return c
    # 子串/包含匹配
    for c in cands:
        cn = norm_name(c)
        if cn and (cn in key or key in cn) and len(cn) >= 3 and len(key) >= 3:
            return c
    # 别名表未命中且无候选时, 全联赛找一次
    for c in cands:
        cn = norm_name(c)
        if cn and (cn.split()[-1] == key.split()[-1] and len(key.split()[-1]) >= 4):
            return c
    return None


RULES_DIMS = {
    "盘口信号": {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R9", "R69", "R70", "R71", "R79", "R110", "R112", "R186"},
    "量化模型": {"R49", "R50", "R51", "R52", "R89", "R96", "R119", "R120"},
    "平局ELO": {"R7_draw", "R_draw_balance", "R_draw_elasticity", "R_elo_close", "R_elo_mid"},
    "大小球": {"R46", "R47", "R48"},
    "基本面": {"R125", "R137"},
    "资金风控": {"R18", "R108", "R117", "R118", "R132", "R154"},
    "分析纪律": {"R81", "R105", "R107", "R167"},
}

_rule_engine = None


def _get_rule_engine():
    global _rule_engine
    if _rule_engine is None:
        sys.path.insert(0, os.path.join(HERE, "..", "src", "rules"))
        from rule_engine_v2 import FootballRuleEngineV2
        _rule_engine = FootballRuleEngineV2()
    return _rule_engine


def build_rule_data(home, away, odds, elo_home, elo_away, p_over, lam_h, lam_a,
                    odds_initial=None, poisson=None):
    """构造规则引擎输入(初盘缺失时用现盘, 变盘类规则不触发)。"""
    oh, od, oa = odds
    init = odds_initial or odds
    btts = (1 - math.exp(-lam_h)) * (1 - math.exp(-lam_a))
    rd = {
        "home_team": home, "away_team": away,
        "odds_home": oh, "odds_draw": od, "odds_away": oa,
        "odds_home_initial": init[0], "odds_draw_initial": init[1], "odds_away_initial": init[2],
        "pinnacle_home": oh, "home_elo": elo_home or 1500, "away_elo": elo_away or 1500,
        "ou_line": OU_LINE, "ou_line_initial": OU_LINE,
        "ou_over_prob": p_over, "btts_prob": btts,
        "draw_concentration": 0, "draw_bet_count": 0, "total_bet_count": 0,
    }
    if poisson:
        rd["poisson_home"], rd["poisson_draw"], rd["poisson_away"] = poisson
    return rd


def run_rules(rule_data):
    """跑规则引擎, 返回 (触发信号列表, 按维度汇总 dict)。"""
    eng = _get_rule_engine()
    result = eng.analyze_match(rule_data)
    signals = result.get("signals", [])
    dim_sum = {}
    for dim, ids in RULES_DIMS.items():
        trig = [s for s in signals if s.rule_id in ids]
        dim_sum[dim] = {
            "n": len(trig),
            "strength": sum(s.strength for s in trig),
            "rules": [s.rule_id for s in trig],
        }
    return signals, dim_sum, result.get("direction", "?")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", default=os.path.join(HERE, "output", "today_matches.csv"))
    ap.add_argument("--hours", type=float, default=96, help="开赛窗口(小时, 从当前UTC)")
    ap.add_argument("--match-only", action="store_true")
    ap.add_argument("--date", default="2026-08-14", help="特征构建统一日期(最早开赛日)")
    args = ap.parse_args()

    tm = json.load(open(os.path.join(HERE, "teams_map.json"), encoding="utf-8"))
    teams_by_league = tm["football_data_teams_by_league"]

    df = pd.read_csv(args.csv, encoding="utf-8-sig")
    print(f"总场次: {len(df)}")

    # 匹配
    df["fd_home"] = df.apply(lambda r: match_team(r["league"], r["home"], teams_by_league), axis=1)
    df["fd_away"] = df.apply(lambda r: match_team(r["league"], r["away"], teams_by_league), axis=1)
    miss = df[(df["fd_home"].isna()) | (df["fd_away"].isna())]
    print(f"队名匹配失败: {len(miss)} 场")
    for _, r in miss.iterrows():
        print(f"  [{r['league']}] {display(r['home'])}({r['fd_home']}) vs {display(r['away'])}({r['fd_away']}) {r['kickoff_utc']}")

    if args.match_only:
        return

    # 开赛窗口过滤
    df["kickoff"] = pd.to_datetime(df["kickoff_utc"], format="%m-%d %H:%M")
    now = df["kickoff"].min()  # 用最早比赛做参考(避免系统时间歧义)
    window = df[df["kickoff"] <= now + pd.Timedelta(hours=args.hours)]
    print(f"开赛窗口 {args.hours:.0f}h 内: {len(window)} 场")

    # 跑预测(生产口径: 小球2.5 + edge>=5% + 赔率>=2.00)
    rows = []
    for _, r in window.iterrows():
        odds = (r["odds_h"], r["odds_d"], r["odds_a"])
        ou = (r["ou_over25"], r["ou_under25"])
        if any(pd.isna(x) for x in odds) or ou is None or any(pd.isna(x) for x in ou):
            continue
        try:
            row = feature_row_from_dataset(r["league"], r["fd_home"], r["fd_away"], args.date)
            res = score_feature_row(row, odds=odds, ou_line=OU_LINE, ou=ou)
        except Exception as e:
            print(f"  [预测失败] {r['league']} {r['home']} vs {r['away']}: {e}")
            continue
        bets = {b["side"]: b for b in res["bets"]}
        u = bets.get(f"under{OU_LINE}")
        if not u:
            continue
        # 多维度规则引擎评估(162条规则系统 v2 的 25 条可自动化规则)
        rdata = build_rule_data(r["home"], r["away"], odds,
                                row.get("elo_home"), row.get("elo_away"),
                                res["p_over"], res["lam_h"], res["lam_a"],
                                poisson=(res["p_home"], res["p_draw"], res["p_away"]))
        try:
            signals, dim_sum, direction = run_rules(rdata)
        except Exception as e:
            print(f"  [规则引擎异常] {e}")
            signals, dim_sum, direction = [], {}, "?"
        trig_ids = ",".join(s.rule_id for s in signals)
        # 大小球维度是否触发"低进球"信号(R46/R47)
        ou_dim = dim_sum.get("大小球", {})
        ou_support = 0
        for s in signals:
            if s.rule_id in ("R46", "R47", "R48"):
                if s.reason and ("低进球" in s.reason or "下调" in s.reason or "小球" in s.reason):
                    ou_support += 1
        rows.append({
            "league": r["league"], "home": r["home"], "away": r["away"],
            "home_cn": to_cn(r["home"]), "away_cn": to_cn(r["away"]),
            "fd_home": r["fd_home"], "fd_away": r["fd_away"],
            "kickoff_utc": r["kickoff_utc"],
            "odds_h": r["odds_h"], "odds_d": r["odds_d"], "odds_a": r["odds_a"],
            "ou_over": r["ou_over25"], "ou_under": r["ou_under25"],
            "lam_h": res["lam_h"], "lam_a": res["lam_a"],
            "p_over": round(res["p_over"], 4),
            "under_prob": u["prob"], "under_mkt": u["market_prob"],
            "under_edge": u["edge"], "under_odds": u["odds"],
            "under_ev": u["ev"], "under_kelly": u["kelly"],
            "rule_direction": direction,
            "rule_n": len(signals),
            "rule_ids": trig_ids,
            "ou_support": ou_support,
            "rule_盘口": dim_sum.get("盘口信号", {}).get("strength", 0),
            "rule_量化": dim_sum.get("量化模型", {}).get("strength", 0),
            "rule_平局ELO": dim_sum.get("平局ELO", {}).get("strength", 0),
            "rule_大小球": dim_sum.get("大小球", {}).get("n", 0),
        })
    out = pd.DataFrame(rows)
    if out.empty:
        print("无候选(窗口内没有可预测场次)")
        return
    out = out.sort_values("under_edge", ascending=False)
    cand = out[(out["under_edge"] >= EDGE) & (out["under_odds"] >= MIN_ODDS)]
    path = os.path.join(HERE, "output", "candidates.csv")
    out.to_csv(path, index=False, encoding="utf-8-sig")
    print(f"\n可预测场次: {len(out)}, 候选(小球edge>=5% & 赔率>=2.00): {len(cand)}")
    print(f"全部预测已存: {path}")
    def _print_row(r):
        print(f"  [{r['league']}] {display(r['home'])} vs {display(r['away'])} ({r['kickoff_utc']} UTC)")
        print(f"    小球2.5: 概率{r['under_prob']:.1%} 市场{r['under_mkt']:.1%} "
              f"edge={r['under_edge']:+.1%} 赔率{r['under_odds']:.2f} "
              f"EV={r['under_ev']:+.1%} Kelly={r['under_kelly']:.1%} "
              f"λ={r['lam_h']:.2f}/{r['lam_a']:.2f}")
        print(f"    规则: 触发{r['rule_n']}条 方向={r['rule_direction']} "
              f"盘口={r['rule_盘口']:+.0f} 量化={r['rule_量化']:+.0f} "
              f"平局ELO={r['rule_平局ELO']:+.0f} 大小球={r['rule_大小球']}条 "
              f"小球支持={r['ou_support']}条 | {r['rule_ids']}")

    if not cand.empty:
        print("\n===== 候选比赛(生产口径) =====")
        for _, r in cand.iterrows():
            _print_row(r)
    print("\n===== 全部可预测场次(按 edge 排序) =====")
    for _, r in out.iterrows():
        _print_row(r)


if __name__ == "__main__":
    main()