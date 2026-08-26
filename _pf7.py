import io
p=r"form_phase0\build_detail_48h.py"
s=io.open(p,encoding="utf-8").read()
s=s.replace('r["form_support"], r["form_diff"] if r["form_diff"] else "无"', 'r["form"], r["form_diff"] if r["form_diff"] else "无"')
s=s.replace('r["form_support"] if r["form_support"] else "中性"', 'r["form"] if r["form"] else "中性"')
io.open(p,"w",encoding="utf-8").write(s)
print("ok")
