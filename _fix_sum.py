import io
p=r"analysis_records/48h_full_odds_20260817.md"
s=io.open(p,encoding="utf-8").read()
s=s.replace("- 盘口覆盖: 临场16场 + 12场盘(意杯4场 + 欧冠3场 + 葡超/阿甲5场) = 20场有完整盘口; 其余22场无盘(缺源)。",
            "- 盘口覆盖: 去重后 **23 场有完整盘口**（临场16场 + 12场盘补7场: 意杯4 + 欧冠3）; 其余19场无盘(缺源)。")
io.open(p,"w",encoding="utf-8").write(s)
print("fixed")
