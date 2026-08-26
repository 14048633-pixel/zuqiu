# -*- coding: utf-8 -*-
import json, io, sys
sys.stdout.reconfigure(encoding='utf-8')
p = 'strategy_data/j1_odds_zones.json'
d = json.load(io.open(p, encoding='utf-8'))

# 1) metadata: 明确样本窗口与规则归属
d['metadata'] = {
  "sample_n": 1100,
  "data_window": {"start": "2023-08-01", "end": "2026-06-30"},
  "generation": "rolling_window",
  "rule_basis": "旧规则样本(2023-2025自然年18队 + 2026过渡赛季分区制)。2026-27跨年新规(20队/外援5人/取消U23强制/VAR点球收紧)下, 旧区间真值(odds_zones/asian_hdp/draw_odds/deep_hdp等)前10-15轮校准期禁用, 仅 baseline(3.35实测20场)为当前有效基准",
  "note": "近3赛季+2026过渡赛季, sample_n为估算; 2026-08-21 冻结旧区间, 待J1新规满10-15轮后重算"
}

# 2) odds_zones 各 zone 冻结标注
R = {
 'zone1_1.30_1.50': '主队深热区间旧样本(主胜68.2%), 新规下主场优势消失(实测主40/客40), 禁用',
 'zone2_1.51_1.80': '主队优势区间旧样本(主胜56.7%), 新规客队能力上涨, 禁用',
 'zone3_1.81_2.20': '均衡区间旧样本(主44.1/平25.8/客30.1), 新规客强主弱, 禁用',
 'zone4_2.21_2.70': '客队小幅优势区间旧样本(客43.9), 方向与基线一致, 待重算',
 'zone5_2.71_plus': '客队强势区间旧样本(客59.0), 方向与基线一致, 待重算',
}
for k, v in d.get('odds_zones', {}).items():
    if isinstance(v, dict):
        v['rule_basis_2026'] = R.get(k, '旧规则样本, 新规校准期禁用/待重算')

# 3) asian_hdp / draw_odds / deep_hdp / ou_link 冻结标注
d['asian_hdp']['rule_basis_2026'] = '旧规则亚盘真值(近3赛季+过渡), 新规校准期禁用; 深盘穿盘低的核心规律保留为方向参考'
d['draw_odds']['rule_basis_2026'] = '旧规则平局赔率区间, 新规校准期仅参考'
d['deep_hdp']['rule_basis_2026'] = '旧规则深盘真值, 新规下客队变强深盘更难过盘, 方向保留'
d['ou_link']['rule_basis_2026'] = '旧规则盘口-大小球联动, 新规进球中枢上修(实测3.35/大2.5=70%), 待重算'
for k in ('goal_timing', 'top_scores', 'first_half'):
    if k in d and isinstance(d[k], dict):
        d[k]['rule_basis_2026'] = '旧规则样本, 新规校准期仅参考'

# 4) baseline 标注为唯一有效
d['baseline']['effective_2026'] = True
d['baseline']['rule_basis_2026'] = '2026-27跨年正式赛季开季20场实测(8/7-8/15), 当前唯一有效基准; 前10轮校准期, 每轮更新'

# 5) version_comparison.C 官方旧基准弃用标注
d['version_comparison']['C_2026跨年正式赛季']['note'] = '官方预设基准(2.40), 已被 D 开季20场实测(3.35)取代, 弃用'

d['updated'] = '2026-08-21'
json.dump(d, io.open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('已更新 j1_odds_zones.json')
print('baseline effective:', d['baseline'].get('effective_2026'))
print('odds_zones zone1:', json.dumps(d['odds_zones']['zone1_1.30_1.50'], ensure_ascii=False))
