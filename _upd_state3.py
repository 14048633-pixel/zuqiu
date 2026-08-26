# -*- coding: utf-8 -*-
import io
ROOT = r"D:\足球分析"
fp = ROOT + r"\SESSION_STATE.md"
txt = io.open(fp, encoding="utf-8").read()
marker = "## 当前进度："
section = """## 对手强度归一 v3：国内联赛补齐（✅ 本次完成, 2026-08-18 深夜）

### 数据与覆盖
- 来源：HF soccer-dataset 本地（67.4万场, 2008-2027, 含2025/26完整赛季）
- 32队国内补齐：奥超4/克甲3/塞超2/以超3/捷甲3/匈甲1/阿塞2/塞浦2/斯洛伐克/斯洛文尼亚/波黑/格鲁吉亚/哈/亚美尼亚/立/拉/爱/北爱/直布罗陀/科索沃
- 队名修正3个：Austria Wien→627、Iberia 1999→Saburtalo(1448)、Drita→1896
- 92队统一输出：`data/raw/football_data/bsd_team_stats_norm_v3_20260818.json`
  - covered=55（final=v2）/ domestic_merged=31（HF国内+BSD欧战融合）/ no_domestic=6
- 融合公式：`final=(w_euro×euro_v2+w_dom×dom_est)/(w_euro+w_dom)`，w=min(n,20)；dom_est=(dom场均/国内联赛场均)×dom_coef，收缩K=6；国内日期衰减+<5场近期判陈旧

### 验证
- 红星主攻1.00→1.13、迪纳摩1.10→1.19（国内优势体现）；马卡比主防1.23→1.07（软化）；沙姆洛克客防1.21→0.96
- 全池无NaN/缺失，分布0.72~1.47 无离群
- 残留偏高（人工复核）：KF Egnatia 1.474、Víkingur 1.304（无国内数据）
- 新联赛coef（DOM_COEF, 可配置）：奥/克0.92、塞/以/捷/匈0.88、阿塞/塞浦/斯洛伐克0.85、斯洛文尼亚0.82、波黑/格鲁吉亚0.78、哈/亚0.75、拉/立/爱0.72、北爱0.68、科索沃0.65、直0.55

### 遗留
- 6队无国内数据：阿尔巴尼亚(地拉那/Egnatia)、安道尔(埃斯卡尔德斯)、法罗(克拉克斯维克)、冰岛(维京人)、里加(陈旧2016-19)
- fbref/Sofascore/Transfermarkt 均被反爬(403/405)，补齐需 api-football key 或人工复核
- 报告：`analysis_records/opp_strength_norm_v3_20260818.md`；归档已更新

"""
if marker in txt:
    txt = txt.replace(marker, section + marker, 1)
old_line = None
for line in txt.splitlines():
    if line.startswith("> 最近更新"):
        old_line = line
        break
if old_line:
    txt = txt.replace(old_line, "> 最近更新：2026-08-18 深夜（对手强度归一 v3 完成：HF 补齐 32 队国内联赛，92 队统一输出，6 队无国内数据待复核）", 1)
io.open(fp, "w", encoding="utf-8").write(txt)
print("SESSION_STATE.md updated")
