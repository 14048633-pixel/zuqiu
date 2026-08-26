"""火山方舟豆包 联网搜索(web_search) CLI
==============================================
用法:
  python search_web.py "Sevilla vs Rayo Vallecano team news August 2026"
  python search_web.py "塞维利亚 巴列卡诺 伤停 首发" --model ep-xxx --max-tokens 1200

前提:
  1) 项目根 .env 已配置 DOUBAO_API_KEY / DOUBAO_ENDPOINT_ID
  2) 火山引擎控制台已开通「联网内容插件」:
     https://console.volcengine.com/common-buy/CC_content_plugin
     未开通时报 404 ToolNotOpen, 代码会给出明确提示。

说明:
  仅用于研究与本地离线分析, 不参与赌博; 输出带引用来源,
  供情报流人工核对, 不直接进回测训练特征。
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.web_search import doubao_web_search


def main():
    ap = argparse.ArgumentParser(description="豆包联网搜索(Responses API web_search)")
    ap.add_argument("query", help="搜索问题, 建议含英文队名+injury/lineup等关键词")
    ap.add_argument("--model", default=None, help="推理接入点ID(默认 DOUBAO_ENDPOINT_ID)")
    ap.add_argument("--max-tokens", type=int, default=1200)
    ap.add_argument("--timeout", type=int, default=120)
    args = ap.parse_args()

    r = doubao_web_search(args.query, model=args.model,
                          max_output_tokens=args.max_tokens, timeout=args.timeout)
    if not r["ok"]:
        print(f"❌ 搜索失败: {r.get('error')}")
        print(r.get("text", ""))
        sys.exit(2 if r.get("error") in ("env_missing", "tool_not_open") else 1)
    print("✔ 回答:")
    print(r["text"])
    if r.get("searches"):
        print(f"\n✔ 搜索次数: {len(r['searches'])} 次")
        for q in r["searches"]:
            print(f"  - {q[:120]}")
    if r.get("sources"):
        print("\n✔ 来源:")
        for s in r["sources"]:
            print(f"  - {s.get('title', '')}  {s.get('url', '')}")
    if r.get("usage"):
        print(f"\n✔ 用量: {r['usage']}")


if __name__ == "__main__":
    main()