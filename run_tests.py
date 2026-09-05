# -*- coding: utf-8 -*-
"""新系统回归测试: 运行各模块自检 + 小型集成回测。

用法: python football_analyzer/run_tests.py
退出码 0 = 全绿。
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np
import pandas as pd

import devig, asian_handicap, elo, features, strategy, model, search, ark_search
import odds_source, tracker, over_under, ah_backtest
import score_matrix, home_away_layer, ensemble_calib, match_report
import report_rules, report_renderer


def run_module_tests() -> int:
    fails = 0
    # model 自检用随机数据训练 XGB/泊松, 纳入回归以保护模型逻辑
    for mod in (devig, asian_handicap, elo, features, model, strategy, search,
                ark_search, odds_source, tracker, over_under, ah_backtest,
                score_matrix, home_away_layer, ensemble_calib, match_report,
                report_rules, report_renderer):
        name = mod.__name__.rsplit(".", 1)[-1]
        try:
            mod._self_test()
            print(f"[OK] {name}")
        except Exception as exc:
            fails += 1
            print(f"[FAIL] {name}: {exc}")
    return fails


def run_ah_semantics() -> int:
    """回归: football-data AHh 符号统一(负=主让 -> 内部正=主让)。
    防止有人把 _neg 反转逻辑改回导致亚盘方向全反(2026-08-29 曾因此产出假 +35% ROI)。"""
    from data_loader import load_master
    df = load_master(include_espn=False)
    d = df[(df["ah_line"].notna() & df["odds_h"].notna() & (df["ah_line"] != 0))].copy()
    if len(d) < 1000:
        print(f"[FAIL] AH 语义: 有效样本过少 {len(d)}")
        return 1
    c = d["ah_line"].corr(d["odds_h"])
    # 反转后 line 大=主让多=主强=主胜赔率低 -> 应强负相关
    if c > -0.5:
        print(f"[FAIL] AH 符号语义: corr(ah_line, odds_h)={c:.3f}, 应为强负相关")
        return 1
    print(f"[OK] AH 符号语义: corr(ah_line, odds_h)={c:.3f} (负相关=主让, 正确)")
    return 0


def run_integration() -> int:
    from data_loader import load_master
    from backtest import walk_forward

    # 固定 seed, 保证回测数字可复现、可与基线对照(此前无 seed 导致数字漂移,
    # 无法区分"回归破坏"与"正常波动")。基线: head(4000) 开盘结算 ROI≈-16.6%(2026-08-28)。
    np.random.seed(42)
    t0 = time.time()
    df = load_master(include_espn=False)
    df = df[df["odds_h"].notna()].head(4000).copy()
    df = features.build_features(df)
    print(f"[OK] 特征构建 {len(df)} 场 ({time.time()-t0:.1f}s)")

    t0 = time.time()
    bets, summary = walk_forward(df, train_days=180, test_days=60, step_days=90,
                                 min_train=200, use_calibration=True, verbose=False)
    print(f"[OK] 回测 {len(bets)} 注 ROI={summary['roi']:.2%} ({time.time()-t0:.1f}s)")
    if summary["n_bets"] < 10:
        print("[FAIL] 回测投注数过少")
        return 1
    if not np.isfinite(summary["roi"]):
        print("[FAIL] ROI 非有限值")
        return 1
    return 0


def run_single_match() -> int:
    from analyze import analyze_match, load_data
    df = load_data()
    try:
        res = analyze_match("Arsenal", "Chelsea", "E0", "2024-04-23", df=df, verbose=False)
        assert res["has_result"] is True
        assert res["stars"] >= 0 and res["stars"] <= 5
        print(f"[OK] 单场分析: {res['home']} vs {res['away']} 打星={res['stars']}")
        return 0
    except Exception as exc:
        print(f"[FAIL] 单场分析: {exc}")
        return 1


def run_team_match() -> int:
    """回归: 队名匹配链(normalize 增强/中文别名/margin 唯一性/alias 不回归)。
    防止 normalize_team 改动破坏已有匹配或引入 Celta/Ceuta 类误配(2026-08-30)。"""
    from odds_source import normalize_team, TeamMatcher

    # 1) 字符规范化 + 停用词
    assert normalize_team("Tromsø IL") == "tromso", normalize_team("Tromsø IL")
    assert normalize_team("Widzew Łódź") == "widzew lodz"
    assert normalize_team("SSC Napoli") == "napoli"
    assert normalize_team("Kasımpaşa") == "kasimpasa"
    assert normalize_team("Aalesunds FK") == "aalesunds"
    # 不退化: 保留有区分作用的词
    assert normalize_team("Real Madrid") == "real madrid"
    assert normalize_team("Manchester United") == "manchester united"
    assert normalize_team("Manchester City") != normalize_team("Manchester United")

    # 2) 构造小型匹配器验证匹配链
    canon = ["Tromso", "Ceuta", "Celta", "Man City", "Real Madrid"]
    m = TeamMatcher(canon, alias={"Olympique de Marseille": "Marseille"},
                    cn_alias={"曼城": "Man City"})
    assert m.resolve("Tromsø IL") == "Tromso", m.resolve("Tromsø IL")
    assert m.resolve("曼城") == "Man City"
    assert m.resolve("Olympique de Marseille") == "Marseille"
    assert m.resolve("Celta") == "Celta"
    assert m.resolve("Real Madrid CF") == "Real Madrid"  # 去 CF 后缀后精确命中
    assert m.resolve("Nonexistent FC") is None

    # 3) margin 唯一性: 两个近名候选时应拒绝(避免误配)
    m2 = TeamMatcher(["ABC DEF", "ABC DEG"])
    assert m2.resolve("ABC DEH") is None, "近名候选应被 margin 拒绝"

    # 4) 真实库 alias 回归(需 load_data, 只验证之前修复过的关键队)
    from odds_source import team_matcher
    tm = team_matcher()
    for bsd_name, local in [("Olympique de Marseille", "Marseille"),
                            ("SSC Napoli", "Napoli"),
                            ("Deportivo de A Coruña", "La Coruna"),
                            ("Başakşehir FK", "Buyuksehyr"),
                            ("Royale Union Saint-Gilloise", "St. Gilloise")]:
        got = tm.resolve(bsd_name)
        assert got == local, f"{bsd_name} -> {got} (期望 {local})"
    print("[OK] 队名匹配链: normalize/中文别名/margin/alias 回归全过")
    return 0


def run_conf_modulate() -> int:
    """回归: 连续仓位调制(confidence_modulate) + apply_strategy 的 n_eff 接入。
    防止有人把半饱和公式改坏、或删掉 apply_strategy 里的调制导致不确定性失效。
    """
    import numpy as np
    from strategy import confidence_modulate, apply_strategy

    # 纯函数: 无数据不调制 / 平滑缩放 / 无样本不下注 / 单调
    assert confidence_modulate(0.05, None) == 0.05
    assert abs(confidence_modulate(0.05, 15, k=10) - 0.05 * 15 / 25) < 1e-9
    assert abs(confidence_modulate(0.05, 1, k=10) - 0.05 * 1 / 11) < 1e-9
    assert confidence_modulate(0.05, 0, k=10) == 0.0
    assert confidence_modulate(0.05, 30, k=10) > confidence_modulate(0.05, 5, k=10)

    # apply_strategy 接入: 带 n_eff 列时仓位被连续缩放, 不带时保持原逻辑
    import pandas as pd
    df = pd.DataFrame([
        # league,date,home,away,hg,ag, ph,pd,pa, odds_h,odds_d,odds_a, n_eff
        {"league": "E0", "date": "2026-01-01", "home": "A", "away": "B",
         "hg": 1, "ag": 0, "ph": 0.60, "pd": 0.25, "pa": 0.15,
         "odds_h": 1.8, "odds_d": 3.5, "odds_a": 6.0, "n_eff": 1.0},
        {"league": "E0", "date": "2026-01-02", "home": "C", "away": "D",
         "hg": 2, "ag": 1, "ph": 0.60, "pd": 0.25, "pa": 0.15,
         "odds_h": 1.8, "odds_d": 3.5, "odds_a": 6.0, "n_eff": 15.0},
    ])
    out = apply_strategy(df, est_cols=("ph", "pd", "pa"),
                         odds_cols=("odds_h", "odds_d", "odds_a"))
    # 两场同 EV, n_eff=1 的应显著小于 n_eff=15 的仓位
    s1 = float(out.iloc[0]["stake"])
    s2 = float(out.iloc[1]["stake"])
    assert s1 > 0 and s2 > 0, (s1, s2)
    assert s2 > s1 * 3, f"n_eff 调制未生效: n_eff=1 仓位{s1}, n_eff=15 仓位{s2}"

    # 无 n_eff 列时(旧路径)不报错且不调制
    df2 = df.drop(columns=["n_eff"])
    out2 = apply_strategy(df2, est_cols=("ph", "pd", "pa"),
                          odds_cols=("odds_h", "odds_d", "odds_a"))
    assert float(out2.iloc[0]["stake"]) == float(out2.iloc[1]["stake"]), "无 n_eff 时应等额"

    print("[OK] 连续仓位调制: 公式/接入/兼容 回归全过")
    return 0


def run_mc_sim() -> int:
    """回归: 蒙特卡洛比分采样(单场解析对照 + 串关联合模拟).
    防止采样逻辑/对照阈值被改坏(2026-09-01 V4.5 扩展)."""
    try:
        from mc_sim import _self_test
        _self_test()
        print("[OK] 蒙特卡洛: 解析对照/串关联合 回归全过")
        return 0
    except Exception as exc:
        print(f"[FAIL] 蒙特卡洛: {exc}")
        return 1


def run_jp1_rules_change() -> int:
    """回归: J1 2026 跨年改制数据口径(2026-09-02).

    1) 过渡赛季(2026-02~07, 分区+点球制+无升降级)已从 load_master 剔除;
    2) poisson_fit 对 JP1 只允许新规则场次(2026-08+)进入 OU 校准;
    3) 新规则样本充足时生成进球中枢平移系数(新/旧场均比), 抬高 J1 大小球中枢。
    """
    import pandas as pd
    from data_loader import load_master, JP1_TRANSITION_START, JP1_TRANSITION_END
    from model import poisson_fit, poisson_predict, NEW_RULES_LEAGUES

    df = load_master(include_espn=False)
    j = df[df["league"] == "JP1"].copy()
    d = pd.to_datetime(j["date"], errors="coerce")
    n_trans = int(((d >= JP1_TRANSITION_START) & (d <= JP1_TRANSITION_END)).sum())
    assert n_trans == 0, f"JP1 过渡赛季残留 {n_trans} 场"
    start = pd.Timestamp(NEW_RULES_LEAGUES["JP1"]["start"])
    n_new = int((d >= start).sum())
    assert n_new >= 20, f"JP1 新规则场次过少 {n_new}"

    train = df[df["date"] < pd.Timestamp("2099-01-01")]
    fit = poisson_fit(train)
    era = (fit.get("_league_era") or {}).get("JP1")
    assert era and era["factor"] >= 1.05, f"JP1 平移系数缺失/过小: {era}"
    assert era["n_new"] >= 20
    oc = fit.get("_ou_calibration") or {}
    # 新规则样本不足400时 JP1 不应进 OU 校准(旧规则校准会拖低新中枢)
    assert ("JP1" not in oc) or era["n_new"] >= 400, "JP1 OU 校准口径错误"
    # B1 比甲(2026 中枢漂移 2.93/大球58%)必须走 365 天 OU 曲线, 不能全历史滞后
    ocb = oc.get("B1")
    assert ocb and ocb.get("n", 0) >= 100, f"B1 未进 365天 OU 校准: {ocb}"
    # CH(中超)/POL/SAU 2026 偏差(瑞士超+6.6pp/波兰甲+6.9pp/沙超稳基准)同样走窗口曲线
    # SW1 瑞士超高进球(2026大球67%) 用近1年曲线跟随
    for _lg in ("CH", "POL", "SAU", "SW1"):
        _c = oc.get(_lg)
        assert _c and _c.get("n", 0) >= 100, f"{_lg} 未进 365天 OU 校准: {_c}"

    # 抽查近期新赛季场次: λ 合计应落在新中枢附近, 不再系统性偏小
    recent = j[j["date"] >= start].head(5)
    lambdas = []
    for _, r in recent.iterrows():
        lh, la = poisson_predict(fit, r)
        if np.isfinite(lh) and np.isfinite(la):
            lambdas.append(lh + la)
    if lambdas:
        mean_l = float(np.mean(lambdas))
        assert 2.5 <= mean_l <= 3.6, f"JP1 新赛季 λ 中枢异常: {mean_l:.3f}"
    print(f"[OK] J1 跨年改制: 过渡赛季已剔除({n_trans}场), 平移系数={era['factor']}, "
          f"新规则{era['n_new']}场(场均{era['avg_new']}), OU校准未用旧规则")
    return 0


def run_data_missing_detect() -> int:
    """回归: 伪EV防护关键词必须命中"无{league}联赛数据(用联赛均值)"文案。

    2026-09-02: 德丙队 vs 德甲队(奥斯纳布吕克 vs 拜仁)算出主胜 EV+119% ★3 漏拦,
    根因是 match_report 文案 "无D1联赛数据(用联赛均值)" 不含旧关键词
    ("无联赛数据" 被联赛代码隔断, "用联赛均值兜底" 缺"兜底"二字)。
    """
    from league_router import has_data_missing

    # 三种真实数据缺失文案都应被识别
    assert has_data_missing(["主队'VfL Osnabrück'无D1联赛数据(用联赛均值)"])
    assert has_data_missing(["泊松λ用联赛均值兜底(无球队级数据)"])
    assert has_data_missing(["主队'X'本地无匹配(用联赛均值兜底)"])
    # 旧关键词不回归
    assert has_data_missing(["主队'Y'无Elo历史(用默认1500)"])
    assert has_data_missing(["客队'Z'无主场近8场数据"])
    # 正常风险标签不应误判为数据缺失
    assert has_data_missing(["平局预警26.5%禁主/客胜", "模型与市场分歧"]) is None
    print("[OK] 伪EV防护: 无{league}联赛数据(用联赛均值) 文案命中 回归全过")
    return 0


def run_guardrails_default_off() -> int:
    """回归: 双轨实验开关默认关闭, 且开启占位壳输出与旧版完全一致 (2026-09-03).
    防"实验模型顺手改了主链路导致全量漂移"(Pafos/Pi/强度加权类改动污染)。"""
    import pandas as pd
    from config import MODEL
    from model import poisson_fit, poisson_predict
    from elo import compute_elo_history, pi_history

    assert MODEL.get("strength_v2") is False, "strength_v2 默认必须关"
    assert MODEL.get("elo_pi") is False, "elo_pi 默认必须关"

    df = pd.DataFrame([
        {"date": "2024-01-01", "league": "T", "home": "A", "away": "B",
         "hg": 2, "ag": 1},
        {"date": "2024-01-08", "league": "T", "home": "B", "away": "C",
         "hg": 0, "ag": 0},
        {"date": "2024-01-15", "league": "T", "home": "C", "away": "A",
         "hg": 1, "ag": 3},
        {"date": "2024-01-22", "league": "T", "home": "A", "away": "C",
         "hg": 2, "ag": 2},
        {"date": "2024-01-29", "league": "T", "home": "B", "away": "A",
         "hg": 1, "ag": 0},
        {"date": "2024-02-05", "league": "T", "home": "C", "away": "B",
         "hg": 2, "ag": 1},
    ])
    df["date"] = pd.to_datetime(df["date"])
    fit_off = poisson_fit(df)
    old_flag = MODEL.get("strength_v2")
    MODEL["strength_v2"] = True
    try:
        fit_on = poisson_fit(df)
    finally:
        MODEL["strength_v2"] = old_flag
    row = {"league": "T", "home": "A", "away": "B",
           "date": pd.Timestamp("2024-02-06")}
    lh_off, la_off = poisson_predict(fit_off, row)
    lh_on, la_on = poisson_predict(fit_on, row)
    assert abs(lh_off - lh_on) < 1e-12 and abs(la_off - la_on) < 1e-12, \
        f"strength_v2 占位壳漂移: {lh_off}/{la_off} vs {lh_on}/{la_on}"

    e_hist = compute_elo_history(df)
    p_hist = pi_history(df)
    assert len(e_hist) == len(p_hist)
    assert float((e_hist["elo_home_pre"] - p_hist["elo_home_pre"]).abs().max()) < 1e-9, \
        "elo_pi 占位壳与 Elo 不一致"
    print("[OK] 双轨开关: 默认关闭 + 占位壳=旧输出 回归全过")
    return 0


def run_rps_metric() -> int:
    """回归: 1X2 RPS 指标正确性 (2026-09-03).
    完美预测=0; 平均基线=2/9; 方向接近的错(主->平)惩罚 < 完全反向(主->客)."""
    import numpy as np
    from model import rps_1x2

    # 完美预测
    assert rps_1x2([[1, 0, 0], [0, 1, 0], [0, 0, 1]], [0, 1, 2]) == 0.0
    # 平均基线
    base = rps_1x2([[1 / 3, 1 / 3, 1 / 3]] * 99, [0, 1, 2] * 33)
    assert abs(base - 2 / 9) < 1e-9, base
    # 方向接近(主胜->平) < 完全反向(主胜->客胜): 实际=主胜, 预测分别 平/客胜 全押
    near = rps_1x2([[0, 1, 0]], [0])   # 主胜实况, 全押平
    far = rps_1x2([[0, 0, 1]], [0])    # 主胜实况, 全押客
    assert near < far, (near, far)
    print("[OK] RPS 1X2: 完美=0 / 基线=2/9 / 方向接近惩罚<反向 回归全过")
    return 0


def run_strength_v2_routing() -> int:
    """回归: strength_v2 联赛级路由隔离 (2026-09-03).
    白名单联赛可换对手加权强度, 非白名单联赛必须与旧版逐位一致(防污染)."""
    import pandas as pd
    from config import MODEL
    from model import poisson_fit, poisson_predict

    def _mk(lg):
        return pd.DataFrame([
            {"date": "2024-01-01", "league": lg, "home": lg + "A", "away": lg + "B",
             "hg": 2, "ag": 1},
            {"date": "2024-01-08", "league": lg, "home": lg + "B", "away": lg + "C",
             "hg": 0, "ag": 0},
            {"date": "2024-01-15", "league": lg, "home": lg + "C", "away": lg + "A",
             "hg": 1, "ag": 3},
            {"date": "2024-01-22", "league": lg, "home": lg + "A", "away": lg + "C",
             "hg": 2, "ag": 2},
            {"date": "2024-01-29", "league": lg, "home": lg + "B", "away": lg + "A",
             "hg": 1, "ag": 0},
            {"date": "2024-02-05", "league": lg, "home": lg + "C", "away": lg + "B",
             "hg": 2, "ag": 1},
        ])

    df = pd.concat([_mk("T"), _mk("U")], ignore_index=True)
    df["date"] = pd.to_datetime(df["date"])
    row_t = {"league": "T", "home": "TA", "away": "TB",
             "date": pd.Timestamp("2024-02-06")}
    row_u = {"league": "U", "home": "UA", "away": "UB",
             "date": pd.Timestamp("2024-02-06")}
    old_list = MODEL.get("strength_v2_leagues", [])
    try:
        MODEL["strength_v2_leagues"] = []
        f0 = poisson_fit(df)
        MODEL["strength_v2_leagues"] = ["T"]
        f1 = poisson_fit(df)
    finally:
        MODEL["strength_v2_leagues"] = old_list
    lu0 = poisson_predict(f0, row_u)
    lu1 = poisson_predict(f1, row_u)
    assert abs(lu0[0] - lu1[0]) < 1e-12 and abs(lu0[1] - lu1[1]) < 1e-12, \
        f"非白名单联赛被污染: {lu0} vs {lu1}"
    assert "T" in f1 and "U" in f1 and "_ou_calibration" in f1
    print("[OK] strength_v2 路由: 白名单可切, 非白名单=旧输出 回归全过")
    return 0


def run_fixture_arsenal() -> int:
    """回归: Arsenal fixture 可复现(数据指纹不变则数字锁定, 变则提示漂移)."""
    from repro_arsenal import produce
    r = produce()
    fp = r["fingerprint"]
    if fp == "553529fcd36b5fdb":
        assert abs(r["old_lh"] - 2.3549) < 0.005 and abs(r["old_la"] - 0.6846) < 0.005
        assert abs(r["routed_lh"] - 2.1608) < 0.005 and abs(r["routed_la"] - 0.7757) < 0.005
        assert r["routed_lh"] < r["old_lh"]
        print("[OK] Arsenal fixture: 旧 2.3549/0.6846 | 路由 2.1608/0.7757 (指纹锁定)")
    else:
        # 数据变化(增删历史/新赛季) -> 数字允许漂移, 只做方向/有限性 sanity
        assert r["old_lh"] > 0 and r["routed_lh"] > 0
        assert r["routed_lh"] < r["old_lh"]
        print("[OK] Arsenal fixture: 数据指纹已变(%s), 数字漂移放行(方向 sanity 过)"
              % fp)
    return 0



def run_injury_delta_p1() -> int:
    """P1(2026-09-05): 伤停量化升级 - 位置×主力×攻防双向 + 封顶 + 双向等价系数"""
    from lineup_intel import injury_delta, injury_coefs, _injury_delta_recs

    # 1) 普通后卫缺阵(无历史, 0.5权重) -> 攻不变, 守-2% (旧逻辑=1.0无修正, P1已修)
    d1 = _injury_delta_recs([{"name": "S1", "position": "D", "status": "injured"}],
                            None, [])
    assert abs(d1[0] - 0.0) < 1e-6, "缺后卫不应减进攻: %s" % (d1,)
    assert abs(d1[1] - 0.02) < 1e-6, "缺普通后卫 def应0.02: %s" % (d1,)
    # 1b) 队长(核心)后卫 -> 双向加重 攻-2% 守-6%
    d1b = _injury_delta_recs([{"name": "S1", "position": "D", "status": "injured"}],
                             None, ["S1"])
    assert abs(d1b[0] - 0.02) < 1e-6 and abs(d1b[1] - 0.06) < 1e-6, "队长后卫: %s" % (d1b,)

    # 2) 无历史无队长 -> 0.5 权重, 前锋攻-2%
    d2 = _injury_delta_recs([{"name": "F1", "position": "F", "status": "injured"}],
                            None, [])
    assert abs(d2[0] - 0.02) < 1e-6, "前锋0.5权重 atk应0.02: %s" % (d2,)

    # 3) 队长中场 -> 核心加权(0.02+0.02, w=1.0) -> atk 0.04
    d3 = _injury_delta_recs([{"name": "CAP", "position": "M", "status": "injured"}],
                            None, ["CAP"])
    assert abs(d3[0] - 0.04) < 1e-6 and abs(d3[1] - 0.04) < 1e-6, "队长中场: %s" % (d3,)

    # 4) 封顶 0.25 (12 名前锋)
    recs = [{"name": "P%d" % i, "position": "F", "status": "injured"} for i in range(12)]
    d4 = _injury_delta_recs(recs, None, [])
    assert d4[0] <= 0.25 and d4[1] <= 0.25, "封顶失败: %s" % (d4,)

    # 5) 双向等价: 缺客队后卫 -> 主队系数>1, 客队=1.0
    lu = {"unavailable": {"home": [], "away": [{"name": "D1", "position": "D",
                                                "status": "injured"}]},
          "_team_ids": {"home": 1, "away": 2}, "captains": {"home": [], "away": []}}
    ch, ca = injury_coefs(lu)
    assert ch > 1.0, "客队缺后卫主队系数应>1: %.4f" % ch
    assert abs(ca - 1.0) < 1e-6, "客队缺后卫客队系数应=1.0: %.4f" % ca
    assert 0.7 <= ch <= 1.3 and 0.7 <= ca <= 1.3

    # 6) injury_delta 结构 + 萨利巴场景(缺客队后防核心 -> 主队λ上调)
    dl = injury_delta(lu)
    assert set(dl.keys()) == {"home", "away"} and "detail" in dl["away"]
    print("[OK] 伤停P1: 位置×主力×攻防双向 + 封顶 + 双向等价系数 回归全过")
    return 0

if __name__ == "__main__":
    print("== 新系统回归测试 ==")
    total = 0
    total += run_module_tests()
    total += run_ah_semantics()
    total += run_integration()
    total += run_single_match()
    total += run_team_match()
    total += run_conf_modulate()
    total += run_mc_sim()
    total += run_jp1_rules_change()
    total += run_data_missing_detect()
    total += run_guardrails_default_off()
    total += run_rps_metric()
    total += run_strength_v2_routing()
    total += run_fixture_arsenal()
    total += run_injury_delta_p1()
    if total == 0:
        print("ALL GREEN")
    else:
        print(f"{total} FAILED")
        sys.exit(1)
