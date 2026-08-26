import io
p=r"SESSION_STATE.md"
s=io.open(p,encoding="utf-8").read()

s=s.replace("> 最近更新：2026-08-17 23:10（回填 CH 污染修复 + 48h 观察比赛按新方案重分析完成）",
            "> 最近更新：2026-08-17 23:40（48h 观察比赛最终方向：临场盘 16/16 全部匹配 + LSTM v2 风控合成完成）")

old="""- **48h 新方案分析产物**: form_phase0/analyze_48h_v2.py(.csv/.txt/.report.md); 42场中 24场状态分齐全、9场有BSD/扫描方向, 其余待临场盘口"""
new="""- **48h 新方案分析产物**: form_phase0/analyze_48h_v2.py(.csv/.txt/.report.md); 42场中 24场状态分齐全、9场有BSD/扫描方向
- **48h 最终方向(本次完成)**: analysis_records/live_odds_48h_20260817.json = 16/16 全部匹配; 48h_final_direction_20260817.md/.json = 临场方向+form风控合成表(高3/中7/低6)
- **队名匹配修复(本次)**: ①NFKD 不分解字符(ø/å/æ)直接 ascii-ignore 丢字 → live_odds.py 新增 transliterate() 音译表 + fetch_live_48h.py 本地 _TRANSLIT; ②别名: Sønderjyske Fodbold→sønderjyske、Gimnasia y Esgrima Mendoza→Gimnasia Mendoza; ③_GENERIC 加 fodbold/fotball/idrettslag。丹超 Brøndby、阿甲 Gimnasia 两场补拉成功"""
assert old in s
s=s.replace(old,new,1)

s=s.replace("- the-odds-api 主key剩~175", "- the-odds-api 主key剩~34（本次48h补拉耗2次）")

s=s.replace("""## 待办
- ✅ 回填 2025/26 含射门/xG 完成(7,569场) + v2 重训(训练池44,953场) + 账本覆盖104/108(96.3%)""",
"""## 待办
- ✅ 回填 2025/26 含射门/xG 完成(7,438场) + v2 重训(训练池44,919场) + 账本覆盖104/108(96.3%) + 48h 最终方向表完成
- 临场盘仅剩~34次: 之后拉盘需轮换备用key(the-odds-api 11 key 已配容灾)""")

io.open(p,"w",encoding="utf-8").write(s)
print("session updated")
