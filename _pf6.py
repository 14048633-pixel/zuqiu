import io
p=r"form_phase0\_refetch5.py"
s=io.open(p,encoding="utf-8").read()
old='''    router = OddsApiRouter(project_root=ROOT)
    key = router.get_active_key()
    print("active key:", router.active_source(), "| keys:", len(router.keys))'''
new='''    env = {}
    for line in io.open(os.path.join(ROOT, ".env"), encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line: continue
        k, v = line.split("=", 1); env[k.strip()] = v.split("#")[0].strip()
    key = env.get("ODDS_API_KEY_4") or env.get("ODDS_API_KEY_1")
    print("using key ODDS_API_KEY_4 (剩余500)")'''
assert old in s
s=s.replace(old,new,1)
s=s.replace('''        if remaining is not None and int(remaining) < 3:
            key = router.rotate()
            print("  rotate ->", router.active_source())''', '''        if remaining is not None and int(remaining) < 3:
            print("  key quota low, stop"); break''')
io.open(p,"w",encoding="utf-8").write(s)
print("patched")
