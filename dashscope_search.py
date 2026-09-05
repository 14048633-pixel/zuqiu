# -*- coding: utf-8 -*-
"""阿里云百炼(DashScope) 联网问答客户端 — qwen-plus 内置 web_search 工具。

用法(OpenAI Responses API 兼容):
    POST https://dashscope.aliyuncs.com/compatible-mode/v1/responses
    {"model": "qwen-plus", "input": [...], "tools": [{"type":"web_search"}]}

- 凭证: DASHSCOPE_API_KEY(sk-开头)
- 模型: DASHSCOPE_MODEL(默认 qwen-plus)
- 与 ark_search.py 输出格式一致, 可无缝替换
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
import requests

load_dotenv(Path(__file__).parent.parent / ".env")

# 兼容多工作空间端点: 用 .env 的 DASHSCOPE_BASE_URL 覆盖(默认官方域名)。
# 2026-09-03 切换 ws-7xaegkat3bk6pbm5.cn-beijing.maas.aliyuncs.com 专用端点。
BASE_URL = os.getenv(
    "DASHSCOPE_BASE_URL",
    "https://dashscope.aliyuncs.com/compatible-mode/v1",
).strip().rstrip("/")
DEFAULT_MODEL = "qwen-plus"

ERROR_HINTS = {
    "invalid_api_key": "百炼 Key 无效: 请确认 DASHSCOPE_API_KEY 为 sk- 开头。",
    "insufficient_quota": "账户额度不足或欠费, 请检查阿里云百炼账户余额。",
    "rate_limit_exceeded": "触发限流, 请降低请求频率稍后再试。",
    "model_not_found": "模型不存在: 请检查 DASHSCOPE_MODEL。",
    "connection_error": "网络异常, 请稍后重试。",
}

# 会话内熔断: 一旦命中 欠费/额度不足/Key无效, 整批短路不再发请求(2026-09-02 百炼欠费教训)
_QUOTA_BLOCKED = False


def _load_config(api_key: Optional[str] = None, model: Optional[str] = None):
    key = (api_key or os.getenv("DASHSCOPE_API_KEY") or "").strip()
    mdl = (model or os.getenv("DASHSCOPE_MODEL") or DEFAULT_MODEL).strip()
    return key, mdl


def has_credentials(api_key: Optional[str] = None, model: Optional[str] = None) -> bool:
    key, mdl = _load_config(api_key, model)
    return bool(key and mdl)


def parse_response(data: dict) -> dict:
    """把百炼 Responses 响应规范化为 {answer, citations, search_queries, model, status}。"""
    answer_parts, citations, queries = [], [], []
    for item in data.get("output") or []:
        itype = item.get("type")
        if itype == "web_search_call":
            action = item.get("action") or {}
            if action.get("query"):
                queries.append(action["query"])
            for src in action.get("sources") or []:
                citations.append({
                    "title": src.get("title", ""),
                    "url": src.get("url", ""),
                    "site": src.get("site_name", ""),
                    "publish_time": src.get("publish_time", ""),
                    "summary": (src.get("summary") or "").strip(),
                })
        elif itype == "message":
            for part in item.get("content") or []:
                if part.get("type") != "output_text":
                    continue
                text = (part.get("text") or "").strip()
                if text:
                    answer_parts.append(text)
    return {
        "answer": "\n".join(answer_parts).strip(),
        "citations": citations,
        "search_queries": queries,
        "model": data.get("model", ""),
        "status": data.get("status", ""),
    }


def ask_web(query: str, api_key: Optional[str] = None, model: Optional[str] = None,
            max_output_tokens: int = 2048, timeout: int = 40, max_retries: int = 1) -> dict:
    """单次联网问答。成功 -> {ok, answer, citations, search_queries, model, status, query}。"""
    global _QUOTA_BLOCKED
    if _QUOTA_BLOCKED:
        return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                "error": {"code": "QUOTA_BLOCKED",
                          "message": "百炼账户欠费/额度不足, 本会话已熔断, 不再发请求",
                          "hint": "充值后重启进程恢复"},
                "query": query}
    key, mdl = _load_config(api_key, model)
    if not key:
        return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                "error": {"code": "NO_CREDENTIAL",
                          "message": "未配置百炼凭证 (DASHSCOPE_API_KEY)",
                          "hint": "请在 .env 设置 DASHSCOPE_API_KEY=sk-xxx"}}
    url = f"{BASE_URL}/responses"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": mdl,
        "input": [{"role": "user", "content": query.strip()[:500]}],
        "tools": [{"type": "web_search"}],
        "max_output_tokens": max_output_tokens,
    }
    last_err = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
            if resp.status_code == 200:
                data = resp.json()
                parsed = parse_response(data)
                return {"ok": True, "query": query, **parsed}
            msg = resp.text[:500]
            try:
                err_body = resp.json().get("error", {})
                code = err_body.get("code", str(resp.status_code))
                msg = err_body.get("message", msg)
            except Exception:
                code = str(resp.status_code)
            _blob = (msg + " " + code).lower()
            if any(k in _blob for k in ("quota", "insufficient", "arrearage",
                                        "欠费", "余额", "out of credit")):
                _QUOTA_BLOCKED = True
            hint = ERROR_HINTS.get(str(code).lower())
            last_err = {"code": code, "message": msg, "hint": hint}
        except requests.exceptions.Timeout:
            last_err = {"code": "APITimeoutError", "message": "Request timed out.",
                        "hint": "请检查网络与账户状态。"}
        except requests.exceptions.ConnectionError:
            last_err = {"code": "connection_error", "message": "Connection error.",
                        "hint": ERROR_HINTS["connection_error"]}
        except Exception as e:
            last_err = {"code": "UnknownError", "message": str(e)[:200]}
        if attempt < max_retries:
            time.sleep(2 * (attempt + 1))
    return {"ok": False, "answer": "", "citations": [], "search_queries": [],
            "error": last_err, "query": query}


if __name__ == "__main__":
    import sys
    q = sys.argv[1] if len(sys.argv) > 1 else "曼联 最新伤停"
    r = ask_web(q, timeout=30, max_retries=1)
    print("ok:", r.get("ok"))
    print("model:", r.get("model"))
    print("queries:", r.get("search_queries"))
    print("citations:", len(r.get("citations", [])))
    print("answer:", r.get("answer", "")[:300])
    if not r.get("ok"):
        print("error:", r.get("error"))


def _parse_json_array(text):
    """从模型回复中容错提取 JSON 数组(可能带 markdown 代码块)。"""
    import json as _json
    import re as _re
    if not text:
        return []
    m = _re.search(r"\[.*\]", text, _re.S)
    if not m:
        return []
    try:
        data = _json.loads(m.group(0))
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    except Exception:
        pass
    return []


def extract_injury_json(home, away, league_cn, max_output_tokens=2000,
                        timeout=30, api_key=None, model=None,
                        max_attempts=2, retry_sleep=2.0, cache_dir=None) -> dict:
    """百炼联网: 一次问答提取结构化伤停 JSON (与 ark_search.extract_injury_json 同接口)。

    返回 {"ok": bool, "records": [{side, player, position, status, reason}], "raw": ...}
    """
    if cache_dir:
        import json as _json, hashlib as _hashlib
        cache_key = _hashlib.md5(f"{home}|{away}|{league_cn}".encode()).hexdigest()[:12]
        cache_file = Path(cache_dir) / f"injury_ds_{cache_key}.json"
        if cache_file.exists():
            try:
                cached = _json.loads(cache_file.read_text(encoding="utf-8"))
                if cached.get("ok"):
                    cached["_from_cache"] = True
                    return cached
                _cache_age = time.time() - cache_file.stat().st_mtime
                if _cache_age < 300 and cached.get("error", {}).get("code") != "NO_CREDENTIAL":
                    cached["_from_cache"] = True
                    return cached
            except Exception:
                pass

    q = ("请联网搜索并分别查询主队 %s 和客队 %s (%s) 两支球队各自的伤病/停赛名单。"
         "两队都要单独检查并报告; 某队查不到信息时, 该队的记录留空, 但不要省略对它的检查。"
         "用JSON返回: [{\"team\":\"home\",\"player\":\"英文名\",\"position\":\"F\",\"status\":\"out\",\"reason\":\"腿筋\"},"
         "{\"team\":\"away\",...}] 只输出JSON, 不要注释"
         % (home, away, league_cn))

    last_error = None
    for attempt in range(1, max_attempts + 1):
        out = ask_web(q, api_key=api_key, model=model,
                      max_output_tokens=max_output_tokens, timeout=timeout)
        if out.get("ok"):
            ans = (out.get("answer") or "").strip()
            if ans:
                recs = _parse_json_array(ans)
                for rec in recs:
                    if "team" in rec and "side" not in rec:
                        rec["side"] = rec["team"]
                result = {"ok": True, "records": recs, "raw": ans[:500],
                          "attempts": attempt, "backend": "dashscope"}
                if cache_dir:
                    try:
                        Path(cache_dir).mkdir(parents=True, exist_ok=True)
                        cache_file.write_text(_json.dumps(result, ensure_ascii=False),
                                              encoding="utf-8")
                    except Exception:
                        pass
                return result
            last_error = {"code": "EMPTY_ANSWER",
                          "message": "百炼 返回空回复(status=%s)" % out.get("status")}
        else:
            last_error = out.get("error", {})
        if attempt < max_attempts:
            time.sleep(retry_sleep)

    result = {"ok": False, "records": [], "error": last_error,
              "attempts": max_attempts, "backend": "dashscope"}
    if cache_dir and last_error.get("code") != "NO_CREDENTIAL":
        try:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            cache_file.write_text(_json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return result


SIGNAL_TYPES = (
    "rotation",            # 轮换/战意: 杯赛双线/已出线/保留主力
    "motivation",          # 动机: 争冠/保级/争欧战/无欲无求
    "defensive_motivation",  # 死守/摆大巴倾向(保级客场/客场保平)
    "return_from_injury",  # 核心复出(抵消伤停扣减)
    "coach_absent",        # 主教练停赛/缺席/临阵换帅
    "fatigue_travel",      # 周中赛/双赛/跨洲长途
    "weather_pitch",       # 雨战/极端天气/场地差
    "unknown",
)


def extract_signal_json(home, away, league_cn, max_output_tokens=2500,
                        timeout=60, api_key=None, model=None,
                        max_attempts=2, retry_sleep=2.0, cache_dir=None) -> dict:
    """百炼联网: 一次问答提取"精细化情报信号"结构化 JSON (字段级 schema)。

    设计原则(2026-09-02):
      - 只做情报提取, 不做胜平负/大小球预测(黑盒无校准);
      - 白名单信号类型 SIGNAL_TYPES, level 只许 low/medium/high;
      - 每条必须给 note + evidence, 查不到写 unknown, 禁止编造;
      - 供风控层转规则(轮换→降星 / 死守→小球+ / 复出→抵消伤停)。

    返回 {"ok": True, "signals": [{type, side, level, player?, note, evidence}], ...}
    """
    # 2026-09-02 策略: 百炼仅用于伤停校对; 信号提取费 token, 默认禁用。
    # 需启用时设环境变量 ENABLE_SIGNAL_EXTRACT=1 (仅供后续按需评估)。
    if str(os.getenv("ENABLE_SIGNAL_EXTRACT", "")).strip() not in ("1", "true", "yes"):
        return {"ok": False, "signals": [], "error": {
            "code": "SIGNAL_EXTRACT_DISABLED",
            "message": "百炼信号提取已停用(费token), 仅伤停校对 extract_injury_json 启用"},
            "backend": "dashscope"}
    if cache_dir:
        import json as _json, hashlib as _hashlib
        cache_key = _hashlib.md5(f"sig|{home}|{away}|{league_cn}".encode()).hexdigest()[:12]
        cache_file = Path(cache_dir) / f"signal_ds_{cache_key}.json"
        if cache_file.exists():
            try:
                cached = _json.loads(cache_file.read_text(encoding="utf-8"))
                if cached.get("ok"):
                    cached["_from_cache"] = True
                    return cached
            except Exception:
                pass

    allowed = ",".join(SIGNAL_TYPES)
    q = (
        "请联网搜索 %s vs %s（%s）的赛前情报, 只提取以下类别的信号, 不要预测比分: "
        "%s。"
        "每条规则: 只输出JSON数组, 字段 [{\"type\":\"...\",\"side\":\"home或away\","
        "\"level\":\"low/medium/high\",\"player\":\"核心球员英文名(可空)\","
        "\"note\":\"一句话中文说明\",\"evidence\":\"依据原文摘要\"}]; "
        "level只许low/medium/high; 查不到的类型写 {\"type\":\"unknown\","
        "\"side\":\"home\",\"level\":\"unknown\",\"note\":\"未查到\","
        "\"evidence\":\"\"}; 禁止编造, 禁止输出JSON以外的文字"
        % (home, away, league_cn, allowed)
    )

    last_error = None
    for attempt in range(1, max_attempts + 1):
        out = ask_web(q, api_key=api_key, model=model,
                      max_output_tokens=max_output_tokens, timeout=timeout)
        if out.get("ok"):
            ans = (out.get("answer") or "").strip()
            if ans:
                recs = _parse_json_array(ans)
                signals = []
                for rec in recs:
                    if not isinstance(rec, dict):
                        continue
                    typ = str(rec.get("type") or "unknown")
                    if typ not in SIGNAL_TYPES:
                        typ = "unknown"
                    lvl = str(rec.get("level") or "unknown")
                    if lvl not in ("low", "medium", "high", "unknown"):
                        lvl = "unknown"
                    signals.append({
                        "type": typ,
                        "side": str(rec.get("side") or "unknown"),
                        "level": lvl,
                        "player": rec.get("player"),
                        "note": str(rec.get("note") or "")[:200],
                        "evidence": str(rec.get("evidence") or "")[:200],
                    })
                result = {"ok": True, "signals": signals,
                          "citations": len(out.get("citations") or []),
                          "raw": ans[:800], "attempts": attempt,
                          "backend": "dashscope"}
                if cache_dir:
                    try:
                        Path(cache_dir).mkdir(parents=True, exist_ok=True)
                        cache_file.write_text(_json.dumps(result, ensure_ascii=False),
                                              encoding="utf-8")
                    except Exception:
                        pass
                return result
            last_error = {"code": "EMPTY_ANSWER",
                          "message": "百炼 返回空回复(status=%s)" % out.get("status")}
        else:
            last_error = out.get("error", {})
        if attempt < max_attempts:
            time.sleep(retry_sleep)

    return {"ok": False, "signals": [], "error": last_error,
            "attempts": max_attempts, "backend": "dashscope"}
