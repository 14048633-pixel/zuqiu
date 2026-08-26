"""SharpAPI 简历解析 CLI (sharpapi.com/api/v1/hr/parse_resume)
============================================================
用法:
  python sharpapi_resume.py --file 简历.pdf [--language English] [--key xxx]

流程:
  1) POST multipart 提交简历 -> 返回 status_url/job_id
  2) 轮询 job 状态直到 completed/failed
  3) 输出解析结果 JSON(结构化简历)

密钥: 优先 --key 参数, 其次环境变量 SHARPAPI_API_KEY, 其次项目 .env。
纯标准库, 无第三方依赖。
"""
import argparse
import json
import os
import sys
import time
import uuid
import urllib.request
import urllib.error

API_BASE = "https://sharpapi.com/api/v1/hr"
SUBMIT_URL = API_BASE + "/parse_resume"
STATUS_URL = API_BASE + "/parse_resume/job/status"

CONTENT_TYPES = {
    ".pdf": "application/pdf",
    ".doc": "application/msword",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".rtf": "application/rtf",
}

DONE_STATUS = {"completed", "succeeded", "success", "done", "finished", "failed", "error", "cancelled"}


def load_key(cli_key):
    if cli_key:
        return cli_key.strip()
    v = os.environ.get("SHARPAPI_API_KEY", "").strip()
    if v:
        return v
    try:
        from dotenv import load_dotenv
        root = os.path.dirname(os.path.abspath(__file__))
        p = os.path.join(root, ".env")
        if os.path.exists(p):
            load_dotenv(p, override=False)
    except Exception:
        pass
    return os.environ.get("SHARPAPI_API_KEY", "").strip() or None


def _auth_headers(key):
    return {
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
    }


def build_multipart(file_path, language, boundary):
    ext = os.path.splitext(file_path)[1].lower()
    ctype = CONTENT_TYPES.get(ext, "application/octet-stream")
    with open(file_path, "rb") as f:
        data = f.read()
    parts = []
    parts.append(("--" + boundary).encode())
    parts.append(("Content-Disposition: form-data; name=\"file\"; filename=\"%s\"" % os.path.basename(file_path)).encode())
    parts.append(("Content-Type: " + ctype).encode())
    parts.append(b"")
    parts.append(data)
    parts.append(("--" + boundary).encode())
    parts.append(b'Content-Disposition: form-data; name="language"')
    parts.append(b"")
    parts.append(language.encode("utf-8"))
    parts.append(("--" + boundary + "--").encode())
    parts.append(b"")
    return b"\r\n".join(parts)


def http_json(req, timeout=60):
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
        try:
            return resp.status, json.loads(raw)
        except json.JSONDecodeError:
            return resp.status, {"raw": raw}


def submit_resume(key, file_path, language, timeout=120):
    boundary = "----SharpApiBoundary" + uuid.uuid4().hex
    body = build_multipart(file_path, language, boundary)
    req = urllib.request.Request(SUBMIT_URL, data=body, method="POST", headers={
        **_auth_headers(key),
        "Content-Type": "multipart/form-data; boundary=" + boundary,
    })
    return http_json(req, timeout=timeout)


def poll_status(key, status_url, poll_interval=3.0, max_wait=300):
    """轮询 job 状态, 返回最终 JSON。"""
    t0 = time.time()
    while True:
        req = urllib.request.Request(status_url, headers=_auth_headers(key))
        try:
            code, data = http_json(req)
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"状态查询失败 HTTP {e.code}: {e.read(300)}")
        status = str(data.get("status") or data.get("state") or data.get("job_status") or "").lower()
        print(f"  ⌛ job 状态: {status or code}  (已等待 {int(time.time()-t0)}s)")
        if status in DONE_STATUS or (status == "" and code != 200):
            return data
        if time.time() - t0 > max_wait:
            raise TimeoutError(f"轮询超时 {max_wait}s, 最后状态: {data}")
        time.sleep(poll_interval)


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="SharpAPI 简历解析(提交+轮询+输出)")
    ap.add_argument("--file", required=True, help="简历文件路径 (pdf/doc/docx/txt)")
    ap.add_argument("--language", default="English", help="简历语言, 默认 English")
    ap.add_argument("--key", default=None, help="SharpAPI Bearer key (默认读 SHARPAPI_API_KEY)")
    ap.add_argument("--poll", type=float, default=3.0, help="轮询间隔秒数, 默认3")
    ap.add_argument("--timeout", type=float, default=300.0, help="最大等待秒数, 默认300")
    args = ap.parse_args()

    key = load_key(args.key)
    if not key:
        print("❌ 未找到 SharpAPI key: 用 --key 传入, 或设置环境变量 SHARPAPI_API_KEY / 写入 .env")
        sys.exit(2)
    if not os.path.exists(args.file):
        print(f"❌ 简历文件不存在: {args.file}")
        sys.exit(2)

    print(f"✔ 提交简历: {os.path.basename(args.file)} (语言={args.language})")
    try:
        code, resp = submit_resume(key, args.file, args.language)
    except urllib.error.HTTPError as e:
        print(f"❌ 提交失败 HTTP {e.code}: {e.read(400)}")
        sys.exit(1)
    print(f"✔ 提交响应 HTTP {code}: {json.dumps(resp, ensure_ascii=False)[:500]}")

    status_url = resp.get("status_url") or resp.get("statusUrl") or resp.get("url")
    job_id = resp.get("job_id") or resp.get("jobId") or resp.get("id")
    if not status_url and job_id:
        status_url = f"{STATUS_URL}/{job_id}"
    if not status_url:
        print("⚠️ 响应中没有 status_url/job_id, 原样输出响应:")
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return

    try:
        final = poll_status(key, status_url, poll_interval=args.poll, max_wait=args.timeout)
    except Exception as e:
        print(f"❌ {e}")
        sys.exit(1)

    print("\n====== 解析结果 ======")
    print(json.dumps(final, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()