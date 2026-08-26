import io, csv, json, os, sys, urllib.request, time
sys.stdout.reconfigure(encoding="utf-8")
ROOT = r"D:\足球分析"
def token():
    with io.open(os.path.join(ROOT, ".env"), encoding="utf-8") as f:
        for line in f:
            if line.startswith("BZZOIRO_API_KEY="):
                return line.split("=",1)[1].strip().strip('"').strip("'")
    return ""
tok = token()
hdr = {"User-Agent":"Mozilla/5.0","Authorization":"Token "+tok}
out, off = [], 0
while True:
    u = "https://sports.bzzoiro.com/api/v2/events/?league_id=49&status=finished&date_from=2026-08-01T00:00:00Z&limit=100&offset=%d" % off
    try:
        d = json.loads(urllib.request.urlopen(urllib.request.Request(u, headers=hdr), timeout=40).read().decode("utf-8"))
    except Exception as e:
        print("BSD 拉取失败:", e); break
    rows = d.get("results") or []
    if not rows: break
    for ev in rows:
        h, a = ev.get("home_team"), ev.get("away_team")
        hs, as_ = ev.get("home_score"), ev.get("away_score")
        dt = (ev.get("event_date") or ev.get("start_time") or "")[:10].replace("-","/")
        if h and a and hs is not None and as_ is not None and dt.startswith("2026/"):
            out.append((dt, h, a, int(hs), int(as_)))
    off += len(rows)
    if len(rows) < 100: break
    time.sleep(1.2)
print("BSD finished 场次:", len(out))
csv_rows = []
with io.open(os.path.join(ROOT, "data","raw","football_data","j1_2026_results.csv"), encoding="utf-8-sig") as f:
    for r in csv.reader(f):
        if r and len(r)>=7 and r[0]=="JP1":
            csv_rows.append((r[1], r[2], r[3], int(r[4]), int(r[5])))
print("CSV 场次:", len(csv_rows))
bsd_keys = {(d,h,a) for d,h,a,_,_ in out}
csv_keys = {(d,h,a) for d,h,a,_,_ in csv_rows}
print("BSD有/CSV无:", sorted(bsd_keys - csv_keys))
print("CSV有/BSD无:", sorted(csv_keys - bsd_keys))
# 比分不一致
mism = []
for d,h,a,hs,as_ in out:
    for d2,h2,a2,hs2,as2 in csv_rows:
        if d==d2 and h==h2 and a==a2 and (hs!=hs2 or as_!=as2):
            mism.append((d,h,a,(hs,as_),(hs2,as2)))
print("比分不一致:", mism)
