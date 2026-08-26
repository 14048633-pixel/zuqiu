# -*- coding: utf-8 -*-
import sys, io, json, hashlib, collections, os
from datetime import datetime, timezone, timedelta
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
ROOT = r"D:\足球分析"
fp = ROOT + r"\data\raw\football_data\bsd_team_stats_20260818.json"
raw = io.open(fp, "rb").read()
d = json.loads(raw.decode("utf-8"))
c = collections.Counter(v.get("league") for v in d["stats"].values())

related = [
    "scan48h_20260818_2259.json", "scan48h_20260818_2300.json", "scan48h_teams_20260818_2300.txt",
    "key46_20260818_2307.json", "key46_20260818_2308.md",
    "key46_model_ev_20260818_2316.json", "key46_ev_v2_20260818_2317.json",
    "key46_ev_v3_20260818_2319.json", "key46_ev_final_20260818_2319.json",
    "key46_ev_final2_20260818_2319.json",
]
arc = {
    "id": "bsd_team_stats_20260818",
    "desc": "46场重点联赛(欧冠/欧联/欧协联/中超/西甲) 92支球队BSD历史赛果攻防stats",
    "archived_at": datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M"),
    "data_file": "data/raw/football_data/bsd_team_stats_20260818.json",
    "bytes": len(raw), "md5": hashlib.md5(raw).hexdigest(), "sha1": hashlib.sha1(raw).hexdigest(),
    "fetched_ts": d["ts"], "n_teams": d["n_teams"], "n_events": d["n_events"],
    "league_dist": dict(c),
    "source": "BSD /api/v2/events/?team_id={id}&status=finished&limit=60 (92队, 0错误)",
    "agg_rule": "近40场(最多), 时间衰减权重: 近5场1.0/6-10场0.7/11-20场0.4/>20场0.2; 主客场分列",
    "fields": ["home_gf","home_ga","away_gf","away_ga","n_home","n_away","n_scored","src_season","src_w","src_tag","league","team_id"],
    "known_issues": [
        "未做对手强度归一: 弱队主场失球失真(如Levski home_ga0.32), 强队客场防守被低估(Monaco away_ga2.09), 我们λ仅作交叉验证",
        "BSD prediction的expected_goals与其自身match_result方向矛盾(如Inter Turku), 不可直接当λ",
    ],
    "conclusion": "46场最终EV_bet(BSD概率x市场价-1)全部为负(-1.3%~-12.9%), 0正EV; BSD共识赔率早盘定价有效",
    "related": related,
    "location": ROOT,
}
io.open(ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.json", "w", encoding="utf-8").write(
    json.dumps(arc, ensure_ascii=False, indent=1))

L = ["# 归档：92队BSD历史攻防数据（2026-08-18）", ""]
L.append("> 归档时间 %s" % arc["archived_at"])
L.append("")
L.append("## 数据文件")
L.append("- `%s`（%d 字节）" % (arc["data_file"], arc["bytes"]))
L.append("- MD5 `%s` ｜ SHA1 `%s`" % (arc["md5"], arc["sha1"]))
L.append("- 拉取时间 %s UTC ｜ %d 队 ｜ %d 场赛果 ｜ 0 错误" % (d["ts"], d["n_teams"], d["n_events"]))
L.append("")
L.append("## 覆盖")
L.append("| 联赛 | 队伍数 |")
L.append("|---|---|")
for k, v in c.most_common():
    L.append("| %s | %d |" % (k, v))
L.append("")
L.append("## 来源与口径")
L.append("- 来源：BSD `GET /api/v2/events/?team_id={id}&status=finished&limit=60`")
L.append("- 聚合：每队近 40 场（最多），时间衰减权重 近5场1.0 / 6-10场0.7 / 11-20场0.4 / >20场0.2，主客场分列")
L.append("- 字段：`home_gf/home_ga/away_gf/away_ga/n_home/n_away/n_scored/src_tag/league/team_id`")
L.append("")
L.append("## 已知质量问题（后续必须修复）")
L.append("1. **未做对手强度归一**：弱队主场失球失真（Levski home_ga 0.32 → AEK λ 被压到 0.30）、强队客场防守被低估（Monaco away_ga 2.09 → Górnik λ 虚高）。我们 λ 仅作交叉验证，偏差>0.5 标独立观点")
L.append("2. **BSD expected_goals 与 BSD 自身预测方向矛盾**（如 Inter Turku eg 主1.71/客1.22 却预测客胜63%），不能直接当 λ")
L.append("")
L.append("## 结论（46 场 EV）")
L.append("- 最终 `EV_bet = BSD预测概率 × 市场价 - 1` 全部为负（-1.3% ~ -12.9%），**0 场正 EV**")
L.append("- BSD 共识赔率（多机构平均）早盘定价有效，欧联/欧协联为提前 2 天早盘，无价值腿")
L.append("- 临场 30 分钟重拉后才可能出现盘口偏移")
L.append("")
L.append("## 关联产物")
for f in related:
    L.append("- `analysis_records/%s`" % f)
L.append("")
L.append("## 用途")
L.append("- 46 场重点联赛 λ/EV 独立计算（本次）")
L.append("- 后续并入主数据池前需先做对手强度归一 + 与 load_team_stats 现有池融合验证")
io.open(ROOT + r"\analysis_records\bsd_team_stats_20260818_archive.md", "w", encoding="utf-8").write("\n".join(L))
print("saved archive.json + archive.md")
print("md5:", arc["md5"])
