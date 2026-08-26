import io
p = r"_gen_best9.py"
s = io.open(p, encoding="utf-8").read()
s = s.replace('return "**%s** EV%+.1f%%" % (x["dir"], (x.get("ev") or 0) * 100)',
              'return "**%s** EV%+.1f%%" % (x["dir"], (x.get("ev") or 0))')
io.open(p, "w", encoding="utf-8").write(s)
print("patched")
