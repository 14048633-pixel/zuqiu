import json,io,sys
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
d=json.load(io.open("strategy_data/league_calib.json",encoding="utf-8"))
cc=d.get("cup_coeffs",{})
print("cup_coeffs keys:", list(cc.keys()))
for k in ["意杯","欧冠","欧冠资格","国内杯"]:
    if k in cc:
        print(k, cc[k])
# 检查 league 配置里是否有意杯/欧冠资格
print("leagues keys sample:", list(d.get("leagues",{}).keys())[:20])
