import json, io
fp = r"D:\足球分析\analysis_records\apifb_fixture_map_emperor_20260826.json"
d = json.load(io.open(fp, encoding="utf-8"))
d["matches"].append({
    "home": "Kashima Antlers", "away": "Atletico Suzuka Club", "fixture_id": 1630761,
    "date": "2026-08-26T09:00:00+00:00", "league": "Emperor Cup",
    "target_home": "Kashima Antlers", "target_away": "Atletico Suzuka Club", "target_league": "天皇杯",
    "target_ko": "2026-08-26T09:00:00+00:00", "odds_event_id": None, "match_score": 0.95,
})
d["n"] = len(d["matches"])
json.dump(d, io.open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("matches:", d["n"])
