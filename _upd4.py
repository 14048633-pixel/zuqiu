import io
p=r"SESSION_STATE.md"
s=io.open(p,encoding="utf-8").read()
old="> 最近更新：2026-08-18 00:10（48h 三信号合成方案完成 + 5 场模型旧快照单独重拉重算）"
new="> 最近更新：2026-08-18 00:40（48h 23 场模型全覆盖：5 场+16 场重拉重算完成，方案高3/中8/低12）"
assert old in s
s=s.replace(old,new,1)
old2="- 5 场模型旧快照重拉(本次): refetch5_results_20260817.json; 结果: Casa Pia(小2.5 EV+26%★3解除否决,⚠大小球反向)/Almería(解除,让球主-1.2 EV+9.9%)/Internacional(解除但无达标腿); Samsunspor(仍否决=模型vs市场分歧20pp)、Palestino(仍否决=隔日快照)"
new2="""- 模型全覆盖(本次): refetch5(5场)+refetch16(16场) -> 48h 方案 23/23 全有模型, 高3/中8/低12
  - 高: Casa Pia(客胜76%)、Häcken(主胜68%)、Deportivo(小2.5 58%)
  - 硬否决7场: 分歧20pp=Samsunspor/Sassuolo/Palermo/Brøndby/Cardiff; 隔日快照=Palestino/Gimnasia/Necaxa; 过期13h=Pachuca
  - 大小球反向信号(结算重点核对): Casa Pia、Brøndby(模型小EV+62.7%)、Deportivo(模型大EV+25.9%)、Lanús、Est.Río Cuarto"""
assert old2 in s
s=s.replace(old2,new2,1)
io.open(p,"w",encoding="utf-8").write(s)
print("session updated")
