# -*- coding: utf-8 -*-
import io, datetime
p = r"D:\足球分析\SESSION_STATE.md"
s = io.open(p, encoding="utf-8").read()
stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
block = """# 会话状态

> 最近更新：__STAMP__（08-22 凌晨 27 场重新拉取赔率对比）

## 08-22 凌晨 27 场 赔率对比（本次完成, 2026-08-21 晚）
- 任务: 08-22 00:00~07:00 开赛 27 场, 用最新盘口与旧快照(scan_window_20260821_ah5, snap=08-20 17:xxZ)对比
- 新赔率: the-odds-api 23 场(key5, 每联赛1次bulk) + API-Football 4 场兜底(保甲/罗甲/葡乙/哥甲, 剩余额度8)
- 输出: `analysis_records/research/odds_compare_0822_27.md`(完整27场) + `odds_live_0822_matched_final.json`(新盘原始) + `odds_compare_0822_rows.json`(对比明细)
- 对比方法: 1X2取最低抽水庄; 大小球/让球按庄配对过滤异常价(orr<=1.18/1.30, 极值价排除)后取跨庄中位价; 让球线=带符号主让线
  * the-odds-api spreads: 主outcome.line为带符号主让线, 客outcome.line为镜像
  * API-Football AH: "Home X"与"Away X"(同号标签)是同一盘, X即主让线(勿用异号配对!)
  * AFB Goals Over/Under 一个bet条目含多线, 必须按线分组再配对(勿按side覆盖)
- 关键变化(相对旧快照):
  * 大小球主盘上移: 沙超Al-Riyadh/Al-Qadsiah 2.5->3.5, 德国杯3场只挂3.5线(2.5线无), 哥甲/葡乙等AFB场2.5仍在
  * 1X2大幅移动: Al-Qadsiah客胜+66、Al-Riyadh主胜+41、Boulogne主胜+28、Cracovia主胜+16、Waldhof平局-10
  * 让球线微移: Sirius -0.5->-0.75、Erzurumspor +1.2->+1.25、Cracovia -0.5->-0.25、Dunkerque 0->-0.25
  * 方向价值翻转/大增: Al-Riyadh大球(旧-13.5->新3.5线+28)、Al-Qadsiah大球(-7.7->+13.7)、Marseille大2.5(-1.8->+0.8转正)
- 遗留: 3场德国杯新盘口无让球数据; 旧模型概率为封顶值时"新EV"偏大仅作方向参考
- 下次: 开赛前30分钟用 prematch_pull 补临场盘, 再决定是否重跑 scan_upcoming

""".replace("__STAMP__", stamp)
head, sep, rest = s.partition("# 会话状态")
if sep:
    body = rest
    lines = body.splitlines(keepends=True)
    out = []
    inserted = False
    for ln in lines:
        if not inserted and ln.startswith("## "):
            out.append(block)
            inserted = True
        out.append(ln)
    if not inserted:
        out.append(block)
    s = "# 会话状态" + "".join(out)
else:
    s = block + s
io.open(p, "w", encoding="utf-8").write(s)
print("state updated")
