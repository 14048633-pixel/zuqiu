# -*- coding: utf-8 -*-
import json, io, sys, time, urllib.request, datetime
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
TOK = ""
for l in io.open(r"D:\足球分析\.env", encoding="utf-8"):
    if l.startswith("BZZOIRO_API_KEY="):
        TOK = l.split("=", 1)[1].strip().strip('"').strip("'")
        break
def fetch_status():
    url = "https://sports.bzzoiro.com/api/v2/events/?league_id=19&date_from=2026-08-22&date_to=2026-08-24&limit=100"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0", "Authorization": "Token " + TOK})
    d = json.loads(urllib.request.urlopen(req, timeout=40).read().decode("utf-8"))
    for r in d.get("results") or []:
        ht = r.get("home_team") or {}
        at = r.get("away_team") or {}
        hn = ht.get("name") if isinstance(ht, dict) else ht
        an = at.get("name") if isinstance(at, dict) else at
        if "Guadalajara" in str(hn) and "Tijuana" in str(an):
            return r
    return None
deadline = time.time() + 55 * 60
while time.time() < deadline:
    now = datetime.datetime.now().strftime("%H:%M:%S")
    try:
        r = fetch_status()
        if r is None:
            print("[%s] 未找到该场, 继续轮询" % now); time.sleep(180); continue
        st = r.get("status")
        print("[%s] status=%s score=%s" % (now, st, r.get("score") or (r.get("home_score"), r.get("away_score"))))
        if st == "finished":
            print("RESULT_DONE")
            sys.exit(0)
        time.sleep(180)
    except Exception as e:
        print("[%s] ERR %r, 3min后重试" % (now, e)); time.sleep(180)
print("POLL_TIMEOUT")
