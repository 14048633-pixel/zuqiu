import io
p=r"SESSION_STATE.md"
s=io.open(p,encoding="utf-8").read()
old="> 最近更新：2026-08-17 23:40（48h 观察比赛最终方向：临场盘 16/16 全部匹配 + LSTM v2 风控合成完成）"
new="> 最近更新：2026-08-18 00:10（48h 三信号合成方案完成 + 5 场模型旧快照单独重拉重算）"
assert old in s
s=s.replace(old,new,1)

old2="""- 临场盘仅剩~34次: 之后拉盘需轮换备用key(the-odds-api 11 key 已配容灾)"""
new2="""- 48h 三信号方案: analysis_records/48h_plan_20260817.md/.json（赔率×模型EV×LSTM v2 form, 23场有盘, 高7/中4/低12, 测试期只观察不下单）
- 5 场模型旧快照重拉(本次): refetch5_results_20260817.json; 结果: Casa Pia(小2.5 EV+26%★3解除否决,⚠大小球反向)/Almería(解除,让球主-1.2 EV+9.9%)/Internacional(解除但无达标腿); Samsunspor(仍否决=模型vs市场分歧20pp)、Palestino(仍否决=隔日快照)
- the-odds-api key 状态(本次探测): KEY_1剩1、KEY_2失效(401)、KEY_3剩~424、**KEY_4~9满配额500**(拉盘优先)、KEY_10剩1、KEY_11耗尽; 主链路 router 会自动轮询
- snapshots.csv 已追加5联赛新快照(112,630行), 后续主扫描会读到新盘"""
assert old2 in s
s=s.replace(old2,new2,1)

io.open(p,"w",encoding="utf-8").write(s)
print("session updated")
