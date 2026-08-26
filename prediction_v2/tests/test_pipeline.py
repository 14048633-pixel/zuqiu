"""prediction_v2 测试 —— 无第三方测试框架，直接运行：
  python -m tests.test_pipeline
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import sys

sys.stdout.reconfigure(encoding="utf-8")

import numpy as np
import pandas as pd

from src.data_loader import load_football_data
from src.features import build_features, build_league_baselines, feature_matrix
from src.markets import (devig, devig2, settle_ah, settle_ou, kelly_fraction,
                         goal_matrix, p_1x2, p_over, p_ah, p_ah_quarter, p_ou_quarter)
from src.models import PoissonGoalModel

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CFG = {
    "features": {"elo_k": 32, "elo_home_adv": 100, "decay_half_life_days": 180,
                 "strength_prior": 8, "min_games_strength": 3, "max_goals": 10},
}

PASS = FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append(f"{name} {detail}")
        print(f"  ❌ {name} {detail}")


def test_devig():
    h, d, a = devig(2.0, 3.5, 4.0)
    check("devig sum=1", abs(h + d + a - 1.0) < 1e-9)
    check("devig order", h > d > a)


def test_ah_settlement():
    check("ah -0.5 win", settle_ah(-0.5, 2, 1) == 1.0)   # 净胜1 > 0.5
    check("ah -0.5 lose", settle_ah(-0.5, 1, 1) == -1.0)  # 平局
    check("ah 0 push", settle_ah(0.0, 1, 1) == 0.0)
    check("ah +0.5 win", settle_ah(0.5, 1, 1) == 1.0)     # 受让方平局赢
    check("ah -1 push", settle_ah(-1.0, 1, 0) == 0.0)     # 恰好净胜1
    check("ah -0.25 win full", settle_ah(-0.25, 2, 1) == 1.0)
    check("ah -0.25 draw lose_half", settle_ah(-0.25, 0, 0) == -0.5)
    check("ah +0.25 draw win_half", settle_ah(0.25, 0, 0) == 0.5)
    check("ah -0.75 净胜2赢全", settle_ah(-0.75, 2, 0) == 1.0)
    check("ah -0.75 净胜1赢半", settle_ah(-0.75, 2, 1) == 0.5)
    check("ah -0.75 平局全输", settle_ah(-0.75, 0, 0) == -1.0)


def test_ou_settlement():
    check("ou2.5 over", settle_ou(2.5, 3) == 1.0)
    check("ou2.5 under", settle_ou(2.5, 2) == -1.0)
    check("ou2.0 push", settle_ou(2.0, 2) == 0.0)
    check("ou2.25 over", settle_ou(2.25, 2) == -0.5)
    check("ou2.75 over3", settle_ou(2.75, 3) == 0.5)


def test_kelly():
    k = kelly_fraction(0.6, 2.0, frac=0.25, cap=0.10)
    # f* = (0.6*1 - 0.4)/1 = 0.2 → 0.25*0.2 = 0.05
    check("kelly 0.05", abs(k - 0.05) < 1e-9)
    k2 = kelly_fraction(0.9, 1.2, frac=0.25, cap=0.10)
    check("kelly cap", k2 <= 0.10)
    check("kelly no edge = 0", kelly_fraction(0.4, 2.0, frac=0.25) == 0.0)


def test_matrix():
    M = goal_matrix(1.5, 1.2, 10)
    check("matrix sum=1", abs(M.sum() - 1.0) < 1e-9)
    ph, pd_, pa = p_1x2(M)
    check("1x2 sum=1", abs(ph + pd_ + pa - 1.0) < 1e-9)
    check("1x2 plausible", ph > pa)
    # 整数线走水半权: p_over = P(>2) + 0.5*P(=2)
    M2 = goal_matrix(1.0, 1.0, 10)
    p_gt = sum(M2[i, j] for i in range(11) for j in range(11) if i + j > 2)
    p_eq = sum(M2[i, j] for i in range(11) for j in range(11) if i + j == 2)
    p_o = p_over(M2, 2.0)
    check("ou2.0 push half", abs(p_o - (p_gt + 0.5 * p_eq)) < 1e-9,
          f"p_o={p_o:.6f} expect={p_gt + 0.5*p_eq:.6f}")


def test_no_leakage():
    """核心：第k场比赛的特征必须与"只用前k-1场重算"一致。"""
    df = load_football_data(os.path.join(HERE, "..", "data", "raw", "football_data"),
                            min_date="2018-01-01", max_date="2018-12-31")
    feat = build_features(df, CFG["features"])
    k = 400
    # 前 k+1 场重算 → 最后一行特征 = 完整数据中第 k 场的快照（严格只用前 k 场）
    sub = df.iloc[:k + 1].reset_index(drop=True)
    feat_sub = build_features(sub, CFG["features"]).iloc[-1]
    row = feat.iloc[k]
    for c in ["elo_home", "elo_away", "att_home", "def_home", "att_away", "def_away",
              "gf_h5", "ga_h5", "pts_h5", "days_home", "league_avg_home",
              "gf_h10", "ga_h10", "pts_h10", "gf_home_h10", "ga_away_a10",
              "league_scoring_idx", "league_strength",
              "h2h_total3", "h2h_total5", "h2h_h_win3", "h2h_a_win5", "h2h_a_gf5"]:
        check(f"no-leak {c}", abs(feat_sub[c] - row[c]) < 1e-9,
              f"prefix={feat_sub[c]:.4f} full={row[c]:.4f}")
    # 技术统计/SoS（可能 None=无历史，None 与 None 视为一致）
    for c in ["home_shots5", "away_shots5", "home_corners5", "home_fouls5",
              "home_gf_sos", "home_ga_sos", "away_gf_sos", "away_ga_sos"]:
        a, b = feat_sub[c], row[c]
        ok = (a is None and b is None) or (a is not None and b is not None and abs(a - b) < 1e-9)
        check(f"no-leak {c}", ok, f"prefix={a} full={b}")


def test_ml_features():
    """旧系统移植特征：列存在、无泄漏语义、feature_matrix 可用。"""
    df = load_football_data(os.path.join(HERE, "..", "data", "raw", "football_data"),
                            min_date="2019-01-01", max_date="2019-06-30")
    feat = build_features(df, CFG["features"])
    for c in ["home_shots5", "away_shots5", "home_st5", "away_st5",
              "home_corners5", "away_corners5", "home_fouls5", "away_fouls5",
              "home_gf_sos", "home_ga_sos", "away_gf_sos", "away_ga_sos"]:
        check(f"ml-feat {c} exists", c in feat.columns)
    X = feature_matrix(feat, extra=["tech", "sos"])
    for c in ["home_shots5", "home_gf_sos", "away_ga_sos"]:
        check(f"ml-feat matrix {c}", c in X.columns and X[c].notna().all(),
              f"missing={int(X[c].isna().sum())}")
    check("ml-feat matrix no NaN", X.notna().all().all())
    # 默认(不启用)不应新增列
    X0 = feature_matrix(feat)
    check("ml-feat default closed", "home_shots5" not in X0.columns)


def _synth_df():
    """构造同一联赛 L1 内 A/B/C 三队的有序赛程。"""
    rows = []
    d = pd.Timestamp("2024-01-01")
    h2h_seq = [("A", "B", 2, 0), ("B", "A", 1, 1), ("A", "B", 0, 1),
               ("B", "A", 3, 2), ("A", "B", 1, 0), ("B", "A", 2, 2)]
    for i, (h, a, gh, ga) in enumerate(h2h_seq):
        rows.append({"league": "L1", "Date": d + pd.Timedelta(days=i),
                     "HomeTeam": h, "AwayTeam": a, "FTHG": gh, "FTAG": ga})
    # A 主场连打 12 场 C（A 进球序列用于测近10场窗口）
    a_scores = [2, 0, 3, 1, 2, 0, 3, 1, 2, 0, 3, 1]
    for i, g in enumerate(a_scores):
        rows.append({"league": "L1", "Date": d + pd.Timedelta(days=20 + i),
                     "HomeTeam": "A", "AwayTeam": "C", "FTHG": g, "FTAG": 1})
    # 第19场: 待预测的 A vs B（前18场为历史）
    rows.append({"league": "L1", "Date": d + pd.Timedelta(days=40),
                 "HomeTeam": "A", "AwayTeam": "B", "FTHG": 1, "FTAG": 1})
    return pd.DataFrame(rows)


def test_form_h2h_league():
    """近10场 / 交锋3-5 / 联赛基准：窗口与取值正确、无泄漏。"""
    df = _synth_df()
    feat = build_features(df, CFG["features"])
    row = feat.iloc[-1]  # 第19行: A vs B, 前18场为历史

    # 近10场（A 前12场打C, 后10场进15球失10球积分15, 且全部为主场）
    check("form10 gf_h10", abs(row["gf_h10"] - 16.0) < 1e-9, f"={row['gf_h10']}")
    check("form10 ga_h10", abs(row["ga_h10"] - 10.0) < 1e-9, f"={row['ga_h10']}")
    check("form10 pts_h10", abs(row["pts_h10"] - 18.0) < 1e-9, f"={row['pts_h10']}")
    check("form10 home split", abs(row["gf_home_h10"] - 16.0) < 1e-9
          and abs(row["ga_home_h10"] - 10.0) < 1e-9,
          f"gf_home={row['gf_home_h10']} ga_home={row['ga_home_h10']}")

    # 交锋窗口: 6 场历史 → n3=3, n5=5; 主队A视角胜/负/平
    check("h2h n3/n5", row["h2h_n3"] == 3 and row["h2h_n5"] == 5,
          f"n3={row['h2h_n3']} n5={row['h2h_n5']}")
    check("h2h total5", abs(row["h2h_total5"] - 13 / 5) < 1e-9, f"={row['h2h_total5']}")
    check("h2h win5", abs(row["h2h_h_win5"] - 1 / 5) < 1e-9
          and abs(row["h2h_a_win5"] - 2 / 5) < 1e-9
          and abs(row["h2h_draw5"] - 2 / 5) < 1e-9,
          f"hw={row['h2h_h_win5']} aw={row['h2h_a_win5']} dr={row['h2h_draw5']}")
    check("h2h win3", abs(row["h2h_h_win3"] - 1 / 3) < 1e-9
          and abs(row["h2h_a_win3"] - 1 / 3) < 1e-9
          and abs(row["h2h_draw3"] - 1 / 3) < 1e-9,
          f"hw3={row['h2h_h_win3']} aw3={row['h2h_a_win3']} dr3={row['h2h_draw3']}")
    check("h2h side goals5", abs(row["h2h_h_gf5"] - 6 / 5) < 1e-9
          and abs(row["h2h_h_ga5"] - 7 / 5) < 1e-9
          and abs(row["h2h_a_gf5"] - 7 / 5) < 1e-9
          and abs(row["h2h_a_ga5"] - 6 / 5) < 1e-9,
          f"hgf={row['h2h_h_gf5']} hga={row['h2h_h_ga5']} agf={row['h2h_a_gf5']} aga={row['h2h_a_ga5']}")

    # 联赛基准: 前18场 主场总进27/18=1.5, 客场18/18=1.0; 强弱系数=1.0
    check("league avg", abs(row["league_avg_home"] - 1.5) < 1e-9
          and abs(row["league_avg_away"] - 1.0) < 1e-9,
          f"h={row['league_avg_home']} a={row['league_avg_away']}")
    check("league scoring_idx", abs(row["league_scoring_idx"] - 1.0) < 1e-9,
          f"={row['league_scoring_idx']}")
    check("league strength sane", 1000 < row["league_strength"] < 2000,
          f"={row['league_strength']}")

    # ML 矩阵无 NaN
    X = feature_matrix(feat)
    for c in ["gf_h10", "pts_h10", "league_scoring_idx", "league_strength",
              "h2h_total3", "h2h_h_win3", "h2h_a_gf5", "h2h_draw5"]:
        check(f"matrix {c}", c in X.columns and X[c].notna().all())


def test_league_baselines():
    """联赛基准表：结构、主客均值、大2.5率、强弱系数。"""
    df = _synth_df()
    out = build_league_baselines(df.iloc[:18], None)
    row0 = out.iloc[0]
    check("baselines cols", all(c in out.columns for c in [
        "league", "season", "n", "avg_home_goals", "avg_away_goals",
        "avg_total_goals", "over25_rate", "home_win_rate", "draw_rate",
        "away_win_rate", "avg_elo", "scoring_idx", "strength_idx"]))
    check("baselines n", row0["n"] == 18, f"n={row0['n']}")
    check("baselines avg goals", abs(row0["avg_home_goals"] - 1.5) < 1e-9
          and abs(row0["avg_away_goals"] - 1.0) < 1e-9
          and abs(row0["avg_total_goals"] - 2.5) < 1e-9,
          f"h={row0['avg_home_goals']} a={row0['avg_away_goals']} t={row0['avg_total_goals']}")
    check("baselines over25", abs(row0["over25_rate"] - 8 / 18) < 1e-9,
          f"={row0['over25_rate']}")
    check("baselines win rates", abs(row0["home_win_rate"] - 9 / 18) < 1e-9
          and abs(row0["away_win_rate"] - 4 / 18) < 1e-9
          and abs(row0["draw_rate"] - 5 / 18) < 1e-9,
          f"hw={row0['home_win_rate']} aw={row0['away_win_rate']} dr={row0['draw_rate']}")
    check("baselines season", row0["season"] == 2023, f"season={row0['season']}")
    check("baselines scoring_idx", abs(row0["scoring_idx"] - 1.0) < 1e-9)


def test_model_smoke():
    row = pd.Series({"league_avg_home": 1.5, "league_avg_away": 1.2,
                     "att_home": 1.2, "def_home": 0.9,
                     "att_away": 1.0, "def_away": 1.1})
    m = PoissonGoalModel(max_goals=10)
    p = m.predict(row)
    check("poisson sums", abs(p["p_home"] + p["p_draw"] + p["p_away"] - 1.0) < 1e-9)
    check("poisson lam>0", p["lam_h"] > 0 and p["lam_a"] > 0)


def test_live_odds():
    """the-odds-api 快照/变化表/队名匹配（离线, 不联网）。"""
    from src.live_odds import (flatten_events, movement_table, match_event,
                               normalize_team, judge_text, append_snapshots,
                               load_snapshots)
    import tempfile
    check("normalize man utd", normalize_team("Man Utd") == "manchester united")
    check("normalize psg", normalize_team("PSG") == "paris saint germain")

    ev = {
        "id": "evt-1",
        "home_team": "Arsenal", "away_team": "Chelsea",
        "commence_time": "2026-08-16T19:00:00Z",
        "bookmakers": [
            {"key": "pinnacle", "title": "Pinnacle", "last_update": "2026-08-13T08:00:00Z",
             "markets": [
                 {"key": "h2h", "outcomes": [
                     {"name": "Arsenal", "price": 1.80}, {"name": "Draw", "price": 3.60},
                     {"name": "Chelsea", "price": 4.50}]},
                 {"key": "totals", "outcomes": [
                     {"name": "Over 2.5", "price": 1.95}, {"name": "Under 2.5", "price": 1.90}]},
                 {"key": "spreads", "outcomes": [
                     {"name": "Arsenal -0.5", "price": 2.00, "point": -0.5},
                     {"name": "Chelsea +0.5", "price": 1.85, "point": 0.5}]},
             ]},
        ],
    }
    rows1 = flatten_events([ev], "英超", "2026-08-13T08:00:00Z")
    rows2 = flatten_events([ev], "英超", "2026-08-15T12:00:00Z")
    for r in rows2:
        if r["market"] == "h2h" and r["side"] == "home":
            r["price"] = 1.70
    check("flatten 行数", len(rows1) == 7, f"={len(rows1)}")
    tmp = os.path.join(tempfile.mkdtemp(), "snap.csv")
    n = append_snapshots(tmp, rows1 + rows2)
    check("append 行数", n == 14, f"={n}")
    df = load_snapshots(tmp)
    mv = movement_table(df)
    check("movement 1 场", len(mv) == 1, f"={len(mv)}")
    r = mv.iloc[0]
    check("h2h home move -0.10", abs(float(r["pinnacle_h2h_home_move"]) - (-0.10)) < 1e-9,
          f"={r.get('pinnacle_h2h_home_move')}")
    check("h2h home first/last", float(r["pinnacle_h2h_home_first"]) == 1.80
          and float(r["pinnacle_h2h_home_last"]) == 1.70)
    check("totals over 不变", abs(float(r["pinnacle_totals_over@2.5_move"])) < 1e-9)
    check("spread home@-0.5 列存在", "pinnacle_spreads_home@-0.5_move" in r.index)
    check("n_snapshots=2", int(r["n_snapshots"]) == 2)
    check("match 精确", match_event(mv, "英超", "Arsenal", "Chelsea") is not None)
    check("match 模糊", match_event(mv, "英超", "Arsenal", "Chelsea FC") is not None)
    check("judge 文本", isinstance(judge_text(r), str) and len(judge_text(r)) > 0)
    check("match 无此场", match_event(mv, "英超", "Liverpool", "Everton") is None)


def test_knowledge_rules():
    """知识库补全规则(第二批 18条) 触发/不触发断言 + 清册一致性。"""
    rules_dir = os.path.join(HERE, "..", "src", "rules")
    sys.path.insert(0, rules_dir)
    from rule_engine_v2 import FootballRuleEngineV2
    import rules_inventory

    eng = FootballRuleEngineV2()
    new_ids = ["R4", "R5", "R6", "R10", "R18", "R51", "R71", "R79", "R81", "R89",
               "R96", "R98", "R108", "R110", "R112", "R124", "R125", "R127", "R132",
               "R136", "R137", "R143", "R145", "R147", "R167", "R186"]
    for rid in new_ids:
        check(f"注册 {rid}", rid in eng.rules)

    def trig(rid, data):
        return eng.rules[rid](data).triggered

    check("R4 生死盘-1触发", trig("R4", {"handicap_line": -1.0}))
    check("R4 平手盘不触发", not trig("R4", {"handicap_line": 0.0}))
    check("R5 低水诱客", trig("R5", {"away_water": 0.70, "odds_draw": 3.40, "odds_draw_initial": 3.60}))
    check("R6 欧亚矛盾看衰", trig("R6", {"handicap_line": -0.5, "handicap_initial": -1.0,
                                         "odds_home": 2.10, "odds_home_initial": 1.95}))
    check("R18 值博率<1.6", trig("R18", {"odds_home": 1.45}))
    check("R18 高赔不触发", not trig("R18", {"odds_home": 2.20, "odds_away": 3.10}))
    check("R51 公平OU浅开", trig("R51", {"ou_fair_line": 3.2, "ou_line": 2.5}))
    check("R71 始终适用", trig("R71", {}))
    check("R79 修正降权", trig("R79", {"correction_direction": "home", "odds_home": 2.20, "odds_home_initial": 2.00}))
    check("R81 未开胜平负", trig("R81", {"available_markets": ["让球"]}))
    check("R81 开胜平负不触发", not trig("R81", {"available_markets": ["胜平负", "让球"]}))
    check("R89 档位压制", trig("R89", {"home_tier": 0, "away_tier": 2}))
    check("R96 诱盘验证成立", trig("R96", {"odds_fall_periods": 3, "kelly_home": 1.10}))
    check("R96 三条件不满足=真热", trig("R96", {"odds_fall_periods": 3, "kelly_home": 0.95}))
    check("R108 集中度>40%", trig("R108", {"match_stake_pct": 0.55}))
    check("R108 低集中度不触发", not trig("R108", {"match_stake_pct": 0.30}))
    check("R110 SS退盘让负", trig("R110", {"ss_recede_count": 5, "odds_hdp_draw": 3.22, "odds_hdp_loss": 2.60}))
    check("R110 非5家不触发", not trig("R110", {"ss_recede_count": 3}))
    check("R112 稳定非确认", trig("R112", {"flat_periods": 4, "odds_home": 3.2, "odds_draw": 3.3, "odds_away": 2.1}))
    check("R125 伤病权重", trig("R125", {"injuries": {"门将": 1, "中卫": 2}}))
    check("R125 无伤病不触发", not trig("R125", {}))
    check("R132 连败缩减", trig("R132", {"daily_pnl": -150}))
    check("R137 xG反弹", trig("R137", {"home_xg": 2.3, "home_scored": 1}))
    check("R167 泊松>50%锁定", trig("R167", {"poisson_home": 0.55, "poisson_draw": 0.25, "poisson_away": 0.20}))
    check("R167 无强信号不触发", not trig("R167", {"poisson_home": 0.40, "poisson_draw": 0.30, "poisson_away": 0.30}))
    check("R186 临场升盘确认", trig("R186", {"hdp_initial": -1.0, "hdp_trough": -0.5, "hdp_last": -1.0}))
    check("R10 伤病执行", trig("R10", {"key_injuries": 3}))
    check("R10 伤缺2人不触发", not trig("R10", {"key_injuries": 2}))
    check("R98 东道主首战", trig("R98", {"is_host_opener": True}))
    check("R98 非首战不触发", not trig("R98", {}))
    check("R124 裁判风格", trig("R124", {"referee_style": "home_whistle"}))
    check("R124 无风格不触发", not trig("R124", {}))
    check("R127 赛程密集", trig("R127", {"home_rest_days": 2}))
    check("R127 休息充足不触发", not trig("R127", {"home_rest_days": 5, "away_rest_days": 5}))
    check("R136 出线算术", trig("R136", {"group_md": 2, "md1_result": "loss"}))
    check("R136 非MD2不触发", not trig("R136", {"group_md": 1, "md1_result": "win"}))
    check("R143 门将超预期", trig("R143", {"home_gk_psxg_ga": -0.8}))
    check("R143 正常不触发", not trig("R143", {"home_gk_psxg_ga": 0.1}))
    check("R145 歇大了", trig("R145", {"home_rest_days": 8}))
    check("R145 正常休息不触发", not trig("R145", {"home_rest_days": 4}))
    check("R147 战意不对称", trig("R147", {"home_motivation": 4, "away_motivation": 2}))
    check("R147 均等不触发", not trig("R147", {"home_motivation": 3, "away_motivation": 3}))
    check("清册含第三批规则", all(rules_inventory.by_id(rid) is not None for rid in
                                   ["R10", "R98", "R124", "R127", "R136", "R143", "R145", "R147"]))
    check("清册已实现>=59", len(rules_inventory.IMPLEMENTED) >= 59)

def test_intel_parser():
    """情报解析器: web_search 文本 -> 规则字段 (R10/R98/R124/R136/R147/R125)。"""
    rules_dir = os.path.join(HERE, "..", "src", "rules")
    sys.path.insert(0, rules_dir)
    from intel_parser import parse_web_intel

    f1 = parse_web_intel(
        "塞维利亚 vs 巴列卡诺: 塞维利亚伤停严重, 主力门将尼兰德缺席, 中卫马尔康缺阵, "
        "后腰阿德里安·门迪因伤无法出战, 前锋贾努扎伊伤疑。",
        {"home": "塞维利亚", "away": "巴列卡诺"})
    check("解析伤缺人数=4", f1.get("key_injuries") == 4, f"={f1.get('key_injuries')}")
    check("解析位置分布", f1.get("injuries") == {"门将": 1, "中卫": 1, "后腰": 1, "前锋": 1},
          f"={f1.get('injuries')}")

    f2 = parse_web_intel("揭幕战东道主首战, 美国 vs 加拿大, 裁判以严苛著称。",
                         {"home": "美国", "away": "加拿大"})
    check("解析东道主首战", f2.get("is_host_opener") is True)
    check("解析裁判严哨", f2.get("referee_style") == "strict", f"={f2.get('referee_style')}")

    f3 = parse_web_intel("小组赛第2轮, 首战告负的韩国必须赢下这场比赛, 否则出线无望; "
                         "对手日本已提前出线将大幅轮换。", {"home": "韩国", "away": "日本"})
    check("解析MD2", f3.get("group_md") == 2, f"={f3.get('group_md')}")
    check("解析首战告负", f3.get("md1_result") == "loss", f"={f3.get('md1_result')}")
    check("解析主队动机4档", f3.get("home_motivation") == 4, f"={f3.get('home_motivation')}")
    check("解析客队动机1档", f3.get("away_motivation") == 1, f"={f3.get('away_motivation')}")

    check("无情报空字段", parse_web_intel("天气不错, 双方状态良好。") == {})
    f5 = parse_web_intel("", {"home_last_match_days": 2, "away_last_match_days": 9})
    check("解析休息天数", f5 == {"home_rest_days": 2.0, "away_rest_days": 9.0}, f"={f5}")


def main():
    print("运行测试...")
    for fn in [test_devig, test_ah_settlement, test_ou_settlement, test_kelly,
               test_matrix, test_model_smoke, test_no_leakage, test_ml_features,
               test_form_h2h_league, test_league_baselines, test_live_odds,
               test_knowledge_rules, test_intel_parser]:
        fn()
    print(f"\n结果: {PASS} 通过, {FAIL} 失败")
    if FAILURES:
        print("失败项:")
        for f in FAILURES:
            print(" -", f)
        sys.exit(1)
    print("全部通过 ✅")


if __name__ == "__main__":
    main()
