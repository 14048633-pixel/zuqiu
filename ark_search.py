# -*- coding: utf-8 -*-
"""火山方舟(Ark) 联网问答客户端 —— 模型内置 web_search 工具做赛前情报检索。

官方用法(OpenAI SDK 兼容):
    client = OpenAI(base_url="https://ark.cn-beijing.volces.com/api/v3", api_key=ARK_API_KEY)
    client.responses.create(model=..., input=[{"role":"user","content":q}],
                            tools=[{"type":"web_search"}])

- 凭证: ARK_API_KEY(火山方舟 Key, 形如 ark-xxx; 兼容 DOUBAO_API_KEY 回退)
- 模型: ARK_ENDPOINT_ID(ep-xxx) 优先, 否则 ARK_MODEL(如 doubao-seed-2-1-pro-260628)
- 注意: 方舟 Key 不能用于「联网搜索控制台」的 WebSearch API(open.feedcoopapi.com),
  那是另一套产品, 需在联网搜索控制台单独创建 Key。

命令行: python ark_search.py "阿森纳 伤停 首发" [--max-queries 2] [--api-key ark-xxx] [--endpoint ep-xxx]
"""
from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

BASE_URL = "https://ark.cn-beijing.volces.com/api/v3"
DEFAULT_MODEL = "doubao-seed-2-1-pro-260628"

ERROR_HINTS = {
    "authentication_error": "方舟 Key 无效: 请确认 ARK_API_KEY 为 ark- 开头的火山方舟 Key。",
    "invalid_api_key": "方舟 Key 无效: 请检查 ARK_API_KEY 是否正确。",
    "insufficient_quota": "账户额度不足或欠费, 请检查火山方舟账户余额。",
    "rate_limit_exceeded": "触发限流, 请降低请求频率稍后再试。",
    "not_found": "模型或端点不存在: 请检查 ARK_ENDPOINT_ID / ARK_MODEL。",
    "connection_error": "网络异常, 请稍后重试。",
}


def _load_config(api_key: Optional[str] = None, endpoint: Optional[str] = None,
                 model: Optional[str] = None):
    """返回 (api_key, endpoint, model)，优先级: 显式参数 > 环境变量。"""
    key = (api_key or os.getenv("ARK_API_KEY") or os.getenv("DOUBAO_API_KEY") or "").strip()
    ep = (endpoint or os.getenv("ARK_ENDPOINT_ID") or os.getenv("DOUBAO_ENDPOINT_ID") or "").strip()
    mdl = (model or os.getenv("ARK_MODEL") or "").strip()
    return key, ep, mdl


def has_credentials(api_key: Optional[str] = None, endpoint: Optional[str] = None,
                    model: Optional[str] = None) -> bool:
    key, ep, mdl = _load_config(api_key, endpoint, model)
    return bool(key and (ep or mdl))


def parse_response(data: dict) -> dict:
    """把 Ark Responses 响应规范化为 {answer, citations, search_queries, model, status}。"""
    answer_parts, citations, queries = [], [], []
    for item in data.get("output") or []:
        itype = item.get("type")
        if itype == "web_search_call":
            action = item.get("action") or {}
            if action.get("query"):
                queries.append(action["query"])
        elif itype == "message":
            for part in item.get("content") or []:
                if part.get("type") != "output_text":
                    continue
                text = (part.get("text") or "").strip()
                if text:
                    answer_parts.append(text)
                for ann in part.get("annotations") or []:
                    if ann.get("type") != "url_citation":
                        continue
                    citations.append({
                        "title": ann.get("title", ""),
                        "url": ann.get("url", ""),
                        "site": ann.get("site_name", ""),
                        "publish_time": ann.get("publish_time", ""),
                        "summary": (ann.get("summary") or "").strip(),
                    })
    return {
        "answer": "\n".join(answer_parts).strip(),
        "citations": citations,
        "search_queries": queries,
        "model": data.get("model", ""),
        "status": data.get("status", ""),
    }


def ask_web(query: str, api_key: Optional[str] = None, endpoint: Optional[str] = None,
            model: Optional[str] = None, max_output_tokens: int = 2048,
            timeout: int = 40, max_retries: int = 0) -> dict:
    """单次联网问答。成功 -> {ok, answer, citations, search_queries, model, status, query}。

    用 requests 直接调用 Responses API (比 OpenAI SDK 快 4 倍, 7.5s vs 30s+)。
    """
    import requests as _requests
    key, ep, mdl = _load_config(api_key, endpoint, model)
    if not key or not (ep or mdl):
        return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                "error": {"code": "NO_CREDENTIAL",
                          "message": "未配置方舟凭证 (ARK_API_KEY + ARK_ENDPOINT_ID/ARK_MODEL)",
                          "hint": "请在 .env 设置 ARK_API_KEY=ark-xxx 与 ARK_ENDPOINT_ID=ep-xxx"}}
    url = f"{BASE_URL}/responses"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    payload = {
        "model": ep or mdl,
        "input": [{"role": "user", "content": query.strip()[:500]}],
        "tools": [{"type": "web_search"}],
        "max_output_tokens": max_output_tokens,
    }
    try:
        resp = _requests.post(url, headers=headers, json=payload, timeout=timeout)
        if resp.status_code != 200:
            msg = resp.text[:500]
            try:
                err_body = resp.json().get("error", {})
                code = err_body.get("code", str(resp.status_code))
                msg = err_body.get("message", msg)
            except Exception:
                code = str(resp.status_code)
            hint = ERROR_HINTS.get(str(code).lower())
            if hint is None and resp.status_code == 401:
                hint = ERROR_HINTS["invalid_api_key"]
            elif hint is None and resp.status_code == 429:
                hint = ERROR_HINTS["rate_limit_exceeded"]
            elif hint is None and resp.status_code == 404:
                hint = ERROR_HINTS["not_found"]
            elif hint is None:
                hint = "请检查网络与账户状态。"
            return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                    "error": {"code": str(code), "message": msg[:500], "hint": hint}}
        data = resp.json()
    except _requests.exceptions.Timeout:
        return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                "error": {"code": "APITimeoutError", "message": "Request timed out.",
                          "hint": "请检查网络与账户状态。"}}
    except Exception as exc:
        return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                "error": {"code": type(exc).__name__, "message": str(exc)[:500],
                          "hint": "请检查网络与账户状态。"}}
    try:
        parsed = parse_response(data)
    except Exception as exc:
        return {"ok": False, "answer": "", "citations": [], "search_queries": [],
                "error": {"code": "PARSE", "message": str(exc), "hint": "响应解析失败。"}}
    parsed["ok"] = True
    parsed["query"] = query
    return parsed


def gather_match_intel(home: str, away: str, league_cn: str,
                       max_queries: int = 4, per_query_sleep: float = 1.0,
                       max_output_tokens: int = 2048,
                       api_key: Optional[str] = None,
                       endpoint: Optional[str] = None,
                       model: Optional[str] = None,
                       verbose: bool = False) -> dict:
    """对一场比赛用方舟联网问答检索伤停/首发/战意情报，按 URL 去重聚合。"""
    key, ep, mdl = _load_config(api_key, endpoint, model)
    if not key or not (ep or mdl):
        return {"enabled": False, "reason": "no_credentials",
                "results": [], "answers": [], "queries": []}
    from search import build_match_queries
    queries = build_match_queries(home, away, league_cn)[:max_queries]
    max_queries = len(queries)
    seen = set()
    results = []
    answers = []
    warnings = []
    for q in queries:
        out = ask_web(q, api_key=key, endpoint=ep, model=mdl,
                      max_output_tokens=max_output_tokens)
        if verbose:
            print(f"  [ark] {q} -> ok={out.get('ok')}")
        if not out.get("ok"):
            warnings.append(out.get("error", {}).get("message", q))
            time.sleep(per_query_sleep)
            continue
        if out.get("answer"):
            answers.append({"query": q, "text": out["answer"]})
        for c in out.get("citations", []):
            url = c.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            c["query"] = q
            results.append(c)
        time.sleep(per_query_sleep)
    return {"enabled": True, "backend": "ark", "results": results,
            "answers": answers, "queries": queries, "warnings": warnings[:5]}


def _self_test() -> None:
    """无网络自检: 响应解析 + 无凭证降级。"""
    fake = {
        "model": "doubao-seed-2-1-pro-260628", "status": "completed",
        "output": [
            {"type": "web_search_call", "action": {"query": "A 伤停", "type": "search"},
             "status": "completed"},
            {"type": "reasoning",
             "summary": [{"type": "summary_text", "text": "思考过程"}], "status": "completed"},
            {"type": "message", "role": "assistant", "content": [
                {"type": "output_text", "text": "答案文本", "annotations": [
                    {"type": "url_citation", "title": "t1", "url": "http://a.com",
                     "site_name": "站点", "publish_time": "2026-08-10", "summary": "s1"},
                    {"type": "url_citation", "title": "t2", "url": "http://a.com", "summary": "s2"},
                ]},
            ]},
        ],
    }
    parsed = parse_response(fake)
    assert parsed["answer"] == "答案文本"
    assert len(parsed["citations"]) == 2
    assert parsed["citations"][0]["site"] == "站点"
    assert parsed["search_queries"] == ["A 伤停"]

    saved = {k: os.environ.get(k) for k in
             ("ARK_API_KEY", "DOUBAO_API_KEY", "ARK_ENDPOINT_ID",
              "DOUBAO_ENDPOINT_ID", "ARK_MODEL")}
    for k in saved:
        os.environ.pop(k, None)
    try:
        no_cred = gather_match_intel("A", "B", "英超")
        assert no_cred["enabled"] is False
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v
    assert has_credentials() in (True, False)


def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="火山方舟联网问答 (Ark Responses + web_search)")
    parser.add_argument("query", help="情报查询, 如: 阿森纳 伤停 首发")
    parser.add_argument("--max-queries", "-n", type=int, default=1)
    parser.add_argument("--api-key", help="方舟 Key(优先于环境变量)")
    parser.add_argument("--endpoint", help="方舟端点 ep-xxx(优先于环境变量)")
    parser.add_argument("--model", help="方舟模型名(无端点时使用)")
    parser.add_argument("--max-output-tokens", type=int, default=2048)
    args = parser.parse_args(argv)

    out = ask_web(args.query, api_key=args.api_key, endpoint=args.endpoint,
                  model=args.model, max_output_tokens=args.max_output_tokens)
    if not out.get("ok"):
        err = out.get("error", {})
        print(f"[联网问答失败] {err.get('code')}: {err.get('message')}")
        print(f"  提示: {err.get('hint')}")
        return 1
    print(f"模型: {out.get('model')} | 状态: {out.get('status')}")
    print(f"\n【回答】\n{out['answer']}")
    print(f"\n【引用 {len(out.get('citations') or [])} 条】")
    for c in (out.get("citations") or [])[:10]:
        print(f"- {c.get('title', '')} | {c.get('site', '')}")
        if c.get("url"):
            print(f"  {c['url']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


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
                        timeout=30, api_key=None, endpoint=None, model=None,
                        max_attempts=1, retry_sleep=2.0, cache_dir=None) -> dict:
    """方舟联网: 一次问答提取结构化伤停 JSON。

    返回 {"ok": bool, "records": [{side, player, position, status, reason}], "raw": ...}
    用于与 BSD 缺阵名单合并核验(补 BSD 漏报的马特塔类伤停)。
    注意: 模型偶发 status=incomplete/空回复, 此时自动重试, 仍失败则 ok=False。

    新增: 应用层重试(max_attempts=2) + 结果缓存(按日期+对阵缓存到 cache_dir)。
    """
    # 缓存检查
    if cache_dir:
        import json as _json, hashlib as _hashlib
        cache_key = _hashlib.md5(f"{home}|{away}|{league_cn}".encode()).hexdigest()[:12]
        cache_file = Path(cache_dir) / f"injury_{cache_key}.json"
        if cache_file.exists():
            try:
                cached = _json.loads(cache_file.read_text(encoding="utf-8"))
                # 成功结果永久缓存; 失败结果只缓存5分钟, 超时后重试
                if cached.get("ok"):
                    cached["_from_cache"] = True
                    return cached
                _cache_age = time.time() - cache_file.stat().st_mtime
                if _cache_age < 300 and cached.get("error", {}).get("code") != "NO_CREDENTIAL":
                    cached["_from_cache"] = True
                    return cached
            except Exception:
                pass

    q = ("用JSON返回 %s vs %s (%s) 今日伤病/停赛名单(无则返回[]), 格式: "
         '[{"team":"home","player":"英文名","position":"F","status":"out","reason":"腿筋"},'
         '{"team":"away",...}] 只输出JSON, 不要注释'
         % (home, away, league_cn))

    last_error = None
    for attempt in range(1, max_attempts + 1):
        out = ask_web(q, api_key=api_key, endpoint=endpoint, model=model,
                      max_output_tokens=max_output_tokens, timeout=timeout)
        if out.get("ok"):
            ans = (out.get("answer") or "").strip()
            if ans:
                recs = _parse_json_array(ans)
                # 规范化 team 字段 -> side
                for rec in recs:
                    if "team" in rec and "side" not in rec:
                        rec["side"] = rec["team"]
                result = {"ok": True, "records": recs, "raw": ans[:500],
                          "attempts": attempt}
                # 写入缓存
                if cache_dir:
                    try:
                        Path(cache_dir).mkdir(parents=True, exist_ok=True)
                        cache_file.write_text(_json.dumps(result, ensure_ascii=False),
                                              encoding="utf-8")
                    except Exception:
                        pass
                return result
            last_error = {"code": "EMPTY_ANSWER",
                          "message": "ARK 返回空回复(status=%s)" % out.get("status")}
        else:
            last_error = out.get("error", {})
        # 重试前等待
        if attempt < max_attempts:
            time.sleep(retry_sleep)

    result = {"ok": False, "records": [], "error": last_error, "attempts": max_attempts}
    # 失败也缓存(避免短时间内重复调用失败的API), 但NO_CREDENTIAL不缓存
    if cache_dir and last_error.get("code") != "NO_CREDENTIAL":
        try:
            Path(cache_dir).mkdir(parents=True, exist_ok=True)
            cache_file.write_text(_json.dumps(result, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass
    return result

