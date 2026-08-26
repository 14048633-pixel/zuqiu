"""火山方舟豆包 Responses API 联网搜索(web_search)模块。

调用方式(2026-08-13 已实测验证, 见 search_web.py):
  POST https://ark.cn-beijing.volces.com/api/v3/responses
  body: {
    "model": "<推理接入点ID>",
    "input": [{"role": "user", "content": "..."}],
    "tools": [{"type": "web_search"}]
  }

实测结论(重要, 避免再踩坑):
  1. chat/completions 的 tools=[{"type":"web_search","web_search":{"enable":true}}]
     在现有豆包/GLM 接入点上返回 400: missing `tools.function`,
     该通道只接受 function calling, 不支持 web_search 工具。
  2. /api/v3/responses + tools=[{"type":"web_search"}] 是正确格式;
     子参数 tools=[{"type":"web_search","web_search":{...}}] 会 400
     (json: unknown field "web_search")。
  3. 若账号未开通「联网内容插件」, 返回 404 ToolNotOpen:
       Your account has not activated web search. You may activate it at
       https://console.volcengine.com/common-buy/CC_content_plugin
     需先在火山引擎控制台开通(免费插件), 再重试。

用途(研究/本地分析):
  补充队伍情报数据源缺口: 伤停/停赛/预计首发/临场新闻/赛程变更,
  输出带引用来源的文本, 供情报流人工核对, 不直接进回测训练特征。

用法:
  from src.web_search import doubao_web_search
  r = doubao_web_search("Sevilla vs Rayo Vallecano team news August 2026")
  print(r["text"])       # 模型综合回答
  print(r["sources"])    # 引用来源列表 [{title,url,content}]
"""
import json
import os
import sys
from typing import Dict, List, Optional

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:  # 无 dotenv 时退化为环境变量
    pass

ARK_API_URL = "https://ark.cn-beijing.volces.com/api/v3"
ACTIVATION_URL = "https://console.volcengine.com/common-buy/CC_content_plugin"


def _load_dotenv_from_project_root():
    """按模块位置向上找 .env(项目根=足球竞猜模型训练/.env)。"""
    here = os.path.dirname(os.path.abspath(__file__))
    for base in (here, os.path.dirname(here), os.path.dirname(os.path.dirname(here))):
        p = os.path.join(base, ".env")
        if os.path.isfile(p):
            try:
                load_dotenv(p, override=False)
            except Exception:
                pass
            return p
    return None


_load_dotenv_from_project_root()


def doubao_web_search(
    query: str,
    model: Optional[str] = None,
    max_output_tokens: int = 1200,
    timeout: int = 120,
) -> Dict:
    """调用豆包 Responses API 联网搜索。

    参数:
      query: 搜索问题(建议英文队名+关键信息, 如 injury/lineup)
      model: 推理接入点 ID(默认 DOUBAO_ENDPOINT_ID)
      max_output_tokens: 输出上限
      timeout: 秒

    返回:
      {
        "ok": bool,
        "text": str,             # 模型综合回答
        "sources": List[Dict],   # 引用来源 [{title,url,content}]
        "usage": Dict,           # token 用量
        "error": Optional[str],  # ok=False 时的错误码
        "raw": Dict,             # 完整响应(诊断用)
      }
    """
    api_key = os.getenv("DOUBAO_API_KEY", "")
    endpoint = model or os.getenv("DOUBAO_ENDPOINT_ID", "")
    if not api_key or not endpoint:
        return {
            "ok": False,
            "error": "env_missing",
            "text": "",
            "sources": [],
            "usage": {},
            "raw": {},
        }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }
    payload = {
        "model": endpoint,
        "input": [{"role": "user", "content": query}],
        "tools": [{"type": "web_search"}],
        "max_output_tokens": max_output_tokens,
    }

    try:
        resp = requests.post(
            f"{ARK_API_URL}/responses", json=payload, headers=headers, timeout=timeout
        )
    except Exception as e:  # 网络/超时
        return {"ok": False, "error": f"request_exc:{type(e).__name__}",
                "text": str(e), "sources": [], "usage": {}, "raw": {}}

    try:
        data = resp.json()
    except Exception:
        return {"ok": False, "error": "bad_json", "text": resp.text[:500],
                "sources": [], "usage": {}, "raw": {}}

    if resp.status_code != 200:
        err = data.get("error", {}) if isinstance(data, dict) else {}
        code = err.get("code", "") if isinstance(err, dict) else ""
        msg = err.get("message", "") if isinstance(err, dict) else str(data)
        if code == "ToolNotOpen" or "not activated web search" in str(msg):
            return {
                "ok": False,
                "error": "tool_not_open",
                "text": "账号未开通「联网内容插件」。请在火山引擎控制台开通后重试:\n" + ACTIVATION_URL,
                "sources": [],
                "usage": {},
                "raw": data,
            }
        return {
            "ok": False,
            "error": f"http_{resp.status_code}:{code}",
            "text": str(msg)[:500],
            "sources": [],
            "usage": {},
            "raw": data,
        }

    text, sources, searches = _parse_responses_output(data)
    return {
        "ok": True,
        "text": text,
        "sources": sources,
        "searches": searches,
        "usage": data.get("usage", {}),
        "error": None,
        "raw": data,
    }


def _parse_responses_output(data: Dict):
    """宽容解析 Responses API output 数组(实测结构 2026-08-13)。

    实测 output 结构:
      - {"type": "reasoning",
         "summary": [{"type": "summary_text", "text": "..."}]}
      - {"type": "web_search_call",
         "action": {"query": "...", "type": "search"}, "status", "id"}
      - {"type": "message", "role": "assistant",
         "content": [{"type": "output_text", "text": "...",
                      "annotations": [{"type": "url_citation",
                                       "title", "url", "site_name",
                                       "publish_time", "summary"}]}]}
    引用来源(url_citation)在 output_text.annotations 里;
    模型会自动多轮搜索, 每轮一个 web_search_call。
    返回: (text, sources, searches)
    """
    text_parts: List[str] = []
    sources: List[Dict] = []
    searches: List[str] = []
    seen_urls = set()
    output = data.get("output", []) if isinstance(data, dict) else []
    if not isinstance(output, list):
        return "", [], []

    for item in output:
        if not isinstance(item, dict):
            continue
        itype = item.get("type", "")
        if itype == "message":
            content = item.get("content", [])
            if isinstance(content, list):
                for c in content:
                    if not isinstance(c, dict):
                        continue
                    ctype = c.get("type", "")
                    if ctype in ("output_text", "text"):
                        text_parts.append(c.get("text", ""))
                        for ann in (c.get("annotations") or []):
                            if isinstance(ann, dict) and ann.get("type") == "url_citation" \
                                    and (ann.get("url") or ann.get("title")):
                                key = ann.get("url") or ann.get("title", "")
                                if key in seen_urls:
                                    continue
                                seen_urls.add(key)
                                sources.append({
                                    "title": ann.get("title", ""),
                                    "url": ann.get("url", ""),
                                    "site_name": ann.get("site_name", ""),
                                    "publish_time": ann.get("publish_time", ""),
                                    "summary": (ann.get("summary") or "")[:500],
                                })
                    else:
                        sources.append({"kind": ctype, **{k: v for k, v in c.items()
                                                          if k != "type"}})
        elif itype == "web_search_call":
            action = item.get("action") or {}
            if isinstance(action, dict) and action.get("query"):
                searches.append(action.get("query", ""))
        elif itype in ("web_search_result", "function_call"):
            sources.append({"kind": itype,
                            **{k: v for k, v in item.items() if k != "type"}})
        else:
            sources.append({"kind": itype, **{k: v for k, v in item.items()
                                              if k != "type"}})

    return "\n".join(p for p in text_parts if p), sources, searches


def main_cli(argv=None) -> int:
    """命令行入口: python -m src.web_search "查询词" [--model ep-xxx] [--max-tokens 1200]"""
    args = argv if argv is not None else sys.argv[1:]
    if not args or args[0] in ("-h", "--help"):
        print(__doc__)
        print("用法: python -m src.web_search \"查询词\" [--model ep-xxx] [--max-tokens 1200]")
        return 0
    query = args[0]
    model = None
    max_tokens = 1200
    i = 1
    while i < len(args):
        if args[i] == "--model" and i + 1 < len(args):
            model = args[i + 1]
            i += 2
        elif args[i] == "--max-tokens" and i + 1 < len(args):
            max_tokens = int(args[i + 1])
            i += 2
        else:
            i += 1

    r = doubao_web_search(query, model=model, max_output_tokens=max_tokens)
    if not r["ok"]:
        print(f"搜索失败: {r.get('error')}")
        print(r.get("text", ""))
        return 1 if r.get("error") not in ("env_missing", "tool_not_open") else 2
    print("回答:")
    print(r["text"])
    if r.get("searches"):
        print(f"\n搜索次数: {len(r['searches'])} 次")
        for q in r["searches"]:
            print(f"  - {q[:120]}")
    if r.get("sources"):
        print("\n来源:")
        for s in r["sources"]:
            print(f"  - {s.get('title','')}  {s.get('url','')}")
    if r.get("usage"):
        print(f"\n用量: {json.dumps(r['usage'], ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main_cli())