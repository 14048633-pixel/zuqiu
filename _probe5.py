import io,sys,os
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
for p in ["prediction_v2/src/api_router.py","src/odds/api_router.py","prediction_v2/api_router.py"]:
    if os.path.exists(p):
        s=io.open(p,encoding="utf-8").read()
        print("FILE:",p)
        i=s.find("class OddsApiRouter")
        print(s[i:i+2500])
        break
else:
    print("not found; search...")
    import glob
    for f in glob.glob(r"D:\足球分析\**\api_router.py", recursive=True):
        print(f)
