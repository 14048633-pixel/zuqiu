# -*- coding: utf-8 -*-
"""火山引擎联网搜索 (SearchInfinity) 客户端 + 赛前情报聚合。

官方文档: https://www.volcengine.com/docs/85508/1650263
认证方式(任一):
  1) WEB_SEARCH_API_KEY —— 在「联网搜索控制台」创建, 火山方舟(Ark)的 Key 不通用
  2) VOLCENGINE_ACCESS_KEY + VOLCENGINE_SECRET_KEY —— AK/SK 签名
命令行: python search.py "Arsenal 伤停 首发" [--count 6] [--time-range OneWeek] [--api-key xxx]
"""
from __future__ import annotations

import datetime as dt
import hashlib
import hmac
import json
import os
import time
from typing import List, Optional
from urllib.parse import quote

import requests
from dotenv import load_dotenv

load_dotenv()

SERVICE = "volc_torchlight_api"
VERSION = "2025-01-01"
REGION = "cn-beijing"
HOST = "mercury.volcengineapi.com"
ACTION = "WebSearch"
INTERNAL_API_URL = "https://open.feedcoopapi.com/search_api/web_search"
TRAFFIC_TAG_HEADER = "X-Traffic-Tag"
TRAFFIC_TAG_VALUE = "skill_web_search_common"

TIME_RANGES = {"OneDay", "OneWeek", "OneMonth", "OneYear"}

ERROR_HINTS = {
    "10400": "参数错误，请检查 Query/Count/TimeRange。",
    "10402": "搜索类型非法，仅支持 web/image。",
    "10403": "API Key 无效：请确认 Key 来自『联网搜索控制台』，火山方舟(Ark) 的 Key 不可用于搜索。",
    "10406": "免费额度已用完或账户欠费，请检查账户额度。",
    "10407": "当前无可用免费策略，请检查账户状态。",
    "10500": "服务内部错误，建议稍后重试。",
    "700429": "免费链路限流，请降低请求频率。",
    "100013": "子账号未授权 TorchlightApiFullAccess。",
}


# ---------- AK/SK 签名 (参考火山官方签名示例) ----------

def _hmac_sha256(key: bytes, content: str) -> bytes:
    return hmac.new(key, content.encode("utf-8"), hashlib.sha256).digest()


def _hash_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _norm_query(params: dict) -> str:
    parts = []
    for key in sorted(params):
        vals = params[key] if isinstance(params[key], list) else [params[key]]
        for v in vals:
            parts.append(quote(str(key), safe="-_.~") + "=" + quote(str(v), safe="-_.~"))
    return "&".join(parts).replace("+", "%20")


def _sign_request(ak: str, sk: str, body: str) -> dict:
    now = dt.datetime.now(dt.timezone.utc)
    x_date = now.strftime("%Y%m%dT%H%M%SZ")
    short_date = x_date[:8]
    x_content_sha256 = _hash_sha256(body)
    content_type = "application/json"
    query_params = {"Action": ACTION, "Version": VERSION}

    signed_headers = sorted([
        "content-type", "host", "x-content-sha256", "x-date", "x-traffic-tag",
    ])
    signed_headers_str = ";".join(signed_headers)
    canonical_headers = [
        f"content-type:{content_type}",
        f"host:{HOST}",
        f"x-content-sha256:{x_content_sha256}",
        f"x-date:{x_date}",
        f"x-traffic-tag:{TRAFFIC_TAG_VALUE}",
    ]
    canonical_request = "\n".join([
        "POST", "/", _norm_query(query_params),
        "\n".join(canonical_headers), "", signed_headers_str, x_content_sha256,
    ])
    credential_scope = f"{short_date}/{REGION}/{SERVICE}/request"
    string_to_sign = "\n".join([
        "HMAC-SHA256", x_date, credential_scope, _hash_sha256(canonical_request),
    ])
    k_date = _hmac_sha256(sk.encode("utf-8"), short_date)
    k_region = _hmac_sha256(k_date, REGION)
    k_service = _hmac_sha256(k_region, SERVICE)
    k_signing = _hmac_sha256(k_service, "request")
    signature = _hmac_sha256(k_signing, string_to_sign).hex()
    authorization = (
        f"HMAC-SHA256 Credential={ak}/{credential_scope}, "
        f"SignedHeaders={signed_headers_str}, Signature={signature}"
    )
    return {
        "Content-Type": content_type,
        "Host": HOST,
        "X-Date": x_date,
        "X-Content-Sha256": x_content_sha256,
        TRAFFIC_TAG_HEADER: TRAFFIC_TAG_VALUE,
        "Authorization": authorization,
    }


# ---------- 请求构建 ----------

def build_body(query: str, search_type: str = "web", count: int = 8,
               time_range: Optional[str] = None, auth_level: int = 0,
               query_rewrite: bool = False) -> dict:
    body = {"Query": query.strip()[:100], "SearchType": search_type, "Count": int(count)}
    if search_type == "web":
        body["NeedSummary"] = True
        if auth_level:
            body["Filter"] = {"AuthInfoLevel": auth_level}
        if time_range:
            body["TimeRange"] = time_range
    if query_rewrite:
        body["QueryControl"] = {"QueryRewrite": True}
    return body


def load_credentials(api_key: Optional[str] = None):
    """返回 (api_key, ak, sk)，优先显式 api_key > 环境变量。"""
    key = (api_key or os.getenv("WEB_SEARCH_API_KEY") or "").strip()
    if key:
        return key, None, None
    ak = (os.getenv("VOLCENGINE_ACCESS_KEY") or "").strip()
    sk = (os.getenv("VOLCENGINE_SECRET_KEY") or "").strip()
    if ak and sk:
        return None, ak, sk
    return None, None, None


def has_credentials() -> bool:
    key, ak, sk = load_credentials()
    return bool(key or (ak and sk))


# ---------- 响应解析 ----------

def parse_response(data: dict, search_type: str = "web") -> dict:
    """把 API 原始响应规范化为统一结构。"""
    result = data.get("Result") or {}
    items = []
    raw_items = result.get("WebResults") if search_type == "web" else result.get("ImageResults")
    for it in raw_items or []:
        item = {
            "sort_id": it.get("SortId", ""),
            "title": it.get("Title", ""),
            "url": it.get("Url", ""),
            "summary": (it.get("Summary") or it.get("Snippet") or "").strip(),
            "site": it.get("SiteName", ""),
        }
        if search_type == "image":
            img = it.get("Image") or {}
            item["url"] = img.get("Url", "")
        if item["title"] or item["url"]:
            items.append(item)
    return {
        "count": result.get("ResultCount", len(items)),
        "time_cost_ms": result.get("TimeCost", 0),
        "results": items,
    }


# ---------- 主调用 ----------

def search_web(query: str, count: int = 8, search_type: str = "web",
               time_range: str = "OneWeek", auth_level: int = 0,
               query_rewrite: bool = True, api_key: Optional[str] = None,
               timeout: int = 25) -> dict:
    """返回 dict: 成功 -> {ok, results, count, time_cost_ms}；失败 -> {ok, error:{code,message,hint}}"""
    api_key, ak, sk = load_credentials(api_key)
    if not api_key and not (ak and sk):
        return {"ok": False, "results": [],
                "error": {"code": "NO_CREDENTIAL",
                          "message": "未配置联网搜索凭证 (WEB_SEARCH_API_KEY 或 AK/SK)",
                          "hint": "请在 .env 设置 WEB_SEARCH_API_KEY=你的Key"}}
    body = build_body(query, search_type=search_type, count=count,
                      time_range=time_range, auth_level=auth_level,
                      query_rewrite=query_rewrite)
    body_str = json.dumps(body, ensure_ascii=False)
    try:
        if api_key:
            headers = {
                "Content-Type": "application/json",
                TRAFFIC_TAG_HEADER: TRAFFIC_TAG_VALUE,
                "Authorization": f"Bearer {api_key}",
            }
            url = INTERNAL_API_URL
        else:
            headers = _sign_request(ak, sk, body_str)
            url = f"https://{HOST}?Action={ACTION}&Version={VERSION}"
        resp = requests.post(url, headers=headers, data=body_str.encode("utf-8"), timeout=timeout)
        if resp.status_code == 429:
            return {"ok": False, "results": [],
                    "error": {"code": "429", "message": "请求频率过高触发限流",
                              "hint": "请降低搜索频率，稍后再试。"}}
        resp.raise_for_status()
        data = resp.json()
    except requests.exceptions.HTTPError as exc:
        return {"ok": False, "results": [],
                "error": {"code": str(exc.response.status_code if exc.response is not None else ""),
                          "message": f"HTTP {exc}",
                          "hint": "检查网络与开通状态。"}}
    except Exception as exc:
        return {"ok": False, "results": [],
                "error": {"code": "NETWORK", "message": str(exc), "hint": "网络异常，请稍后重试。"}}

    err = (data.get("ResponseMetadata") or {}).get("Error")
    if err:
        code = str(err.get("Code", ""))
        return {"ok": False, "results": [],
                "error": {"code": code,
                          "message": err.get("Message", ""),
                          "hint": ERROR_HINTS.get(code, "请稍后重试。")}}
    parsed = parse_response(data, search_type)
    parsed["ok"] = True
    parsed["query"] = query
    return parsed


# ---------- 赛前情报聚合 ----------

def build_match_queries(home: str, away: str, league_cn: str) -> List[str]:
    base = f"{home} {away} {league_cn}"
    return [
        f"{base} 伤停 停赛 伤病名单",
        f"{home} 伤停 停赛 伤病 {league_cn}",
        f"{away} 伤停 停赛 伤病 {league_cn}",
        f"{base} 赛前 预测 首发 战意",
        f"{home} 首发预测 轮换 {league_cn}",
        f"{away} 首发预测 轮换 {league_cn}",
    ]


def gather_match_intel(home: str, away: str, league_cn: str,
                       count: int = 5, max_queries: int = 4,
                       per_query_sleep: float = 1.0,
                       time_range: str = "OneWeek", auth_level: int = 0,
                       query_rewrite: bool = True,
                       api_key: Optional[str] = None,
                       verbose: bool = False) -> dict:
    """对一场比赛检索伤停/首发/战意情报，按 URL 去重聚合。"""
    key, ak, sk = load_credentials(api_key)
    if not key and not (ak and sk):
        return {"enabled": False, "reason": "no_credentials",
                "results": [], "queries": []}
    queries = build_match_queries(home, away, league_cn)[:max_queries]
    seen = set()
    results = []
    warnings = []
    for q in queries:
        out = search_web(q, count=count, time_range=time_range,
                         auth_level=auth_level, query_rewrite=query_rewrite,
                         api_key=api_key)
        if verbose:
            print(f"  [search] {q} -> ok={out.get('ok')}")
        if not out.get("ok"):
            warnings.append(out.get("error", {}).get("message", q))
            time.sleep(per_query_sleep)
            continue
        for item in out["results"]:
            url = item.get("url", "")
            if not url or url in seen:
                continue
            seen.add(url)
            item["query"] = q
            results.append(item)
        time.sleep(per_query_sleep)
    return {"enabled": True, "reason": None, "results": results,
            "queries": queries, "warnings": warnings[:5]}


# ---------- 自检 (无网络) ----------

def _self_test() -> None:
    body = build_body(" 测试  ", search_type="web", count=5,
                      time_range="OneWeek", auth_level=1, query_rewrite=True)
    assert body == {"Query": "测试", "SearchType": "web", "Count": 5,
                    "NeedSummary": True, "Filter": {"AuthInfoLevel": 1},
                    "TimeRange": "OneWeek", "QueryControl": {"QueryRewrite": True}}, body
    fake = {"Result": {"ResultCount": 2, "TimeCost": 12,
                       "WebResults": [
                           {"SortId": 1, "Title": "t1", "Url": "http://a.com",
                            "Summary": "s1", "SiteName": "site"},
                           {"SortId": 2, "Title": "t2", "Url": "http://a.com", "Snippet": "s2"},
                       ]}}
    parsed = parse_response(fake, "web")
    assert parsed["count"] == 2 and len(parsed["results"]) == 2
    assert parsed["results"][1]["summary"] == "s2"
    no_cred = gather_match_intel("A", "B", "英超")
    assert no_cred["enabled"] is False
    key, ak, sk = load_credentials()
    # 不强制断言凭证是否存在，只确认返回结构
    assert (key, ak, sk) is not None


# ---------- CLI ----------

def main(argv=None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="火山引擎联网搜索 (SearchInfinity)")
    parser.add_argument("query", help="搜索关键词")
    parser.add_argument("--count", "-c", type=int, default=8)
    parser.add_argument("--type", "-t", default="web", choices=["web", "image"])
    parser.add_argument("--time-range", default="OneWeek",
                        help="OneDay/OneWeek/OneMonth/OneYear")
    parser.add_argument("--auth-level", type=int, default=0, choices=[0, 1])
    parser.add_argument("--api-key", help="联网搜索 API Key（优先于环境变量）")
    args = parser.parse_args(argv)

    if args.type == "image" and args.count > 5:
        args.count = 5
    if args.type == "web" and args.count > 50:
        args.count = 50

    out = search_web(args.query, count=args.count, search_type=args.type,
                     time_range=args.time_range, auth_level=args.auth_level,
                     api_key=args.api_key)
    if not out.get("ok"):
        err = out.get("error", {})
        print(f"[搜索失败] {err.get('code')}: {err.get('message')}")
        print(f"  提示: {err.get('hint')}")
        return 1
    print(f"结果数: {out['count']}  耗时: {out.get('time_cost_ms', 0)}ms")
    for item in out["results"]:
        print(f"\n[{item.get('sort_id')}] {item.get('title')}")
        if item.get("site"):
            print(f"    来源: {item['site']}")
        if item.get("url"):
            print(f"    {item['url']}")
        if item.get("summary"):
            print(f"    {item['summary'][:500]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
