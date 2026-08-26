import io
p=r"form_phase0\build_detail_48h.py"
s=io.open(p,encoding="utf-8").read()

s=s.replace('''    L.append("- **综合**: 首选 **%s**(%.0f%%, 优势%.1fpp) | 置信 **%s** | 参考仓位 %s | form支持 %s(差%s)" % (
        r["pick"], r["pick_prob"], r["pick_gap"], r["conf"], r["stake"], r["form"], r["form_diff"] if r["form_diff"] else "无"))''',
'''    L.append("- **综合**: 首选 **%s**(%.0f%%, 优势%.1fpp) | 置信 **%s** | 参考仓位 %s | form支持 %s(差%s)" % (
        r["pick"], r["pick_prob"], r["pick_gap"], r["conf"], r["stake"], r["form"], r["form_diff"] if r["form_diff"] else "无"))''')

s=s.replace('''    L.append("- **模型**: %s | 模型列: %s" % ("（5场新盘重算）" if r.get("refetched") else "（原扫描）", r["model_ref"]))''',
'''    mcell = "%s EV%s" % (r["model_leg"], r["model_ev"]) if r["model_ev"]!="无" else "无模型"
    if r.get("refetched"): mcell += " [新盘重算]"
    if r.get("ou_reverse"): mcell += " ⚠大小球反向"
    if r["resonance"].startswith("硬否决"): mcell += " ⚠硬否决(%s)" % r["resonance"][len("硬否决("):-1]
    L.append("- **模型**: %s | %s" % (("5场新盘重算" if r.get("refetched") else "原扫描"), mcell))''')

io.open(p,"w",encoding="utf-8").write(s)
print("ok")
