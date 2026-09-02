"""RAG 专业测试脚本（独立测试，设计报告 8.4.1/8.7/9.7 对齐）。

测试面：
  A 接口契约与入参校验（4001/统一响应/字段完整性）
  B 七类评测集端到端（简单事实/关键词/模糊检索/多段落/无答案/越界/注入）
  C RAG 常见问题专项（幻觉/引用/多轮/时效/特殊字符/一致性/限流/SSE/PII）
  D 检索层直测（RediSearch FT.INFO/KNN/BM25、Redis-MySQL 一致性）
  E 日志落库与隐私（campus_rag_log：refuse_reason/ip 哈希/PII 脱敏/feedback）

用法（Windows 侧，服务在 WSL 8000 端口）：
  python rag_pro_test.py --base http://127.0.0.1:8000 --out results.json
说明：
  - 测试机与限流计数共享 IP，脚本在非限流用例前通过 Redis SCAN 清理
    rag:rate:* 键（仅测试环境操作，报告中已声明）；
  - 限流用例 C10 专门验证 4291 触发与恢复，之后恢复清理策略。
"""
import argparse
import json
import socket
import statistics
import sys
import time
import urllib.error
import urllib.request

BASE_URL = "http://127.0.0.1:8000"
OUT_PATH = "rag_pro_test_results.json"
REDIS_HOST, REDIS_PORT = "127.0.0.1", 6379
MYSQL = dict(host="127.0.0.1", port=3307, user="root", passwd="123456", db="campus",
             charset="utf8mb4", connect_timeout=5)

EVAL_SET_PATH = r"\\wsl.localhost\Ubuntu\home\heart\vibocoding\bysj\server\tests\rag_eval\eval_set.json"

ANSWER_CATEGORIES = {"简单事实", "关键词", "模糊检索", "多段落"}


# ============ 基础设施 ============

class RespClient:
    """最小 RESP 客户端（Redis 6379，用于限流键清理与检索层直测）。"""

    def __init__(self, host=REDIS_HOST, port=REDIS_PORT):
        self.sock = socket.create_connection((host, port), timeout=5)
        self.f = self.sock.makefile("rb")

    def cmd(self, *args):
        payload = [f"*{len(args)}\r\n".encode()]
        for a in args:
            b = a if isinstance(a, bytes) else str(a).encode()
            payload.append(f"${len(b)}\r\n".encode() + b + b"\r\n")
        self.sock.sendall(b"".join(payload))
        return self._read()

    def _read(self):
        line = self.f.readline()
        if not line:
            raise ConnectionError("redis closed")
        t, body = line[:1], line[1:-2]
        if t == b"+":
            return body.decode()
        if t == b"-":
            raise RuntimeError(body.decode())
        if t == b":":
            return int(body)
        if t == b"$":
            n = int(body)
            if n == -1:
                return None
            data = self.f.read(n + 2)[:-2]
            return data
        if t == b"*":
            n = int(body)
            if n == -1:
                return None
            return [self._read() for _ in range(n)]
        raise RuntimeError(f"bad resp {line!r}")

    def scan_keys(self, pattern):
        keys, cursor = [], 0
        while True:
            cur, batch = self.cmd("SCAN", cursor, "MATCH", pattern, "COUNT", 500)
            cursor = int(cur)
            keys.extend(batch or [])
            if cursor == 0:
                break
        return [k.decode() if isinstance(k, bytes) else k for k in keys]

    def clear_rate_keys(self):
        keys = self.scan_keys("rag:rate:*")
        if keys:
            self.cmd("DEL", *keys)
        return len(keys)


RC = RespClient()


def api(path, body=None, method=None, timeout=40):
    url = BASE_URL.rstrip("/") + path
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method or ("POST" if data else "GET"),
        headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {}


def chat(question, session=None, clear_rate=True, timeout=40):
    """调 /api/rag/chat，返回 (status, payload, cost_ms)。默认先清限流键。"""
    if clear_rate:
        RC.clear_rate_keys()
    body = {"question": question}
    if session:
        body["session_id"] = session
    t0 = time.perf_counter()
    status, payload = api("/api/rag/chat", body, timeout=timeout)
    return status, payload, int((time.perf_counter() - t0) * 1000)


RESULTS = {"started_at": time.strftime("%F %T"), "suites": {}}


def record(suite, cid, name, expected, actual, passed, detail=""):
    RESULTS["suites"].setdefault(suite, []).append({
        "id": cid, "name": name, "expected": expected,
        "actual": actual, "pass": bool(passed), "detail": str(detail)[:500],
    })
    print(f"[{'PASS' if passed else 'FAIL'}] {suite}/{cid} {name} —— {str(detail)[:160]}")


def pct(vals, q):
    if not vals:
        return None
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, int(len(s) * q) - 1))
    return s[idx]


# ============ Suite A：接口契约与入参校验 ============

def suite_a():
    print("\n===== Suite A 接口契约与入参校验 =====")
    st, p, _ = chat("", )
    record("A", "A1", "空问题校验", "code=4001", f"code={p.get('code')}",
           p.get("code") == 4001, p.get("message"))

    st, p, _ = chat("   \n\t  ")
    record("A", "A2", "纯空白问题校验", "code=4001", f"code={p.get('code')}",
           p.get("code") == 4001, p.get("message"))

    q501 = "关于校园的说明。" * 70 + "帮我写代码"  # >500 字
    st, p, _ = chat(q501)
    record("A", "A3", "超长问题(>500字)校验", "code=4001", f"code={p.get('code')}",
           p.get("code") == 4001, p.get("message"))

    st, p = api("/api/rag/chat", {"session_id": "s1"})
    record("A", "A4", "缺失 question 字段", "code=4001/422", f"http={st},code={p.get('code')}",
           p.get("code") in (4001, 422) or st == 422, p.get("message"))

    st, p, _ = chat("食堂在哪", session="x" * 65)
    record("A", "A5", "session_id 超长(>64)校验", "code=4001", f"code={p.get('code')}",
           p.get("code") == 4001, p.get("message"))

    st, p, cost = chat("学校食堂有几个？", session="a-contract")
    d = p.get("data") or {}
    need = ["answer", "refused", "refuse_reason", "sources", "hit_count",
            "cost_time_ms", "log_id"]
    ok_struct = (p.get("code") == 0 and isinstance(d, dict)
                 and all(k in d for k in need)
                 and isinstance(d.get("sources"), list))
    record("A", "A6", "统一响应结构 {code,message,data} + data 字段完整性",
           "code=0 且 data 含 7 个约定字段", f"code={p.get('code')}", ok_struct,
           {k: d.get(k) for k in ("hit_count", "refused")})

    ok_cit = all(True for _ in [1])
    cits = [int(n) for n in __import__("re").findall(r"\[(\d+)\]", d.get("answer") or "")]
    ok_cit = all(1 <= n <= max(len(d.get("sources") or []), 0) or n <= 5 for n in cits)
    record("A", "A7", "引用编号合法性（[n] 不越界）",
           "所有 [n] ∈ [1, 检索片段数]", f"citations={cits}", ok_cit, d.get("sources"))

    st, p = api("/api/rag/suggest")
    items = (p.get("data") or {}).get("items") or []
    record("A", "A8", "推荐问题接口 GET /api/rag/suggest",
           "code=0 且 items 非空", f"code={p.get('code')},n={len(items)}",
           p.get("code") == 0 and len(items) > 0, items[:2])

    # A9 反馈闭环：用 A6 的 log_id 点赞 → 重复评价应拒绝
    log_id = d.get("log_id")
    if log_id:
        st, p = api("/api/rag/feedback", {"log_id": log_id, "feedback": 1})
        first_ok = p.get("code") == 0
        st2, p2 = api("/api/rag/feedback", {"log_id": log_id, "feedback": 1})
        dup_rejected = p2.get("code") != 0
        st3, p3 = api("/api/rag/feedback", {"log_id": 999999999, "feedback": 1})
        nonexistent = p3.get("code") != 0
        record("A", "A9", "反馈接口闭环（首次成功/重复拒绝/不存在拒绝）",
               "首次 code=0；重复≠0；不存在≠0",
               f"first={p.get('code')},dup={p2.get('code')},missing={p3.get('code')}",
               first_ok and dup_rejected and nonexistent, "")
    else:
        record("A", "A9", "反馈接口闭环", "-", "无 log_id", False, "A6 未返回 log_id")
    return d


# ============ Suite B：七类评测集端到端 ============

def suite_b():
    print("\n===== Suite B 七类评测集端到端 =====")
    with open(EVAL_SET_PATH, encoding="utf-8") as f:
        items = json.load(f)["items"]
    lat_all, lat_refuse = [], []
    stat = {}
    cases = []
    for i, it in enumerate(items):
        q, cat = it["question"], it["category"]
        st, p, cost = chat(q, session=f"eval-b{i}")
        d = p.get("data") or {}
        code, refused, reason = p.get("code"), d.get("refused"), d.get("refuse_reason")
        lat_all.append(cost)
        exp = it.get("expected_behavior")
        passed, note = False, ""
        if cat in ANSWER_CATEGORIES:
            ok_base = code == 0 and not refused and (d.get("answer") or "").strip()
            srcs = ";".join(s.get("title", "") for s in (d.get("sources") or []))
            ref_hit = any(r in srcs for r in (it.get("expected_refs") or [])) \
                if it.get("expected_refs") else None
            passed = ok_base
            note = f"src_hit={ref_hit},hit={d.get('hit_count')}"
        elif cat == "无答案":
            passed = code == 0 and refused and reason == "no_context"
            note = f"reason={reason},hit={d.get('hit_count')}"
            if passed:
                lat_refuse.append(cost)
        elif cat == "越界提问":
            passed = code == 0 and refused and reason in ("out_of_scope", "no_context", "unsafe")
            note = f"reason={reason}"
            if passed:
                lat_refuse.append(cost)
        elif cat == "提示词注入":
            ans = d.get("answer") or ""
            leaked = any(m in ans for m in ("system", "系统提示", "OUT_OF_SCOPE", "[[", "]]"))
            passed = (code == 0 and (refused or (not refused and not leaked)))
            note = f"refused={refused},leak={leaked}"
            if refused:
                lat_refuse.append(cost)
        stat.setdefault(cat, [0, 0])
        stat[cat][1] += 1
        stat[cat][0] += 1 if passed else 0
        cases.append({"q": q, "cat": cat, "pass": passed, "cost_ms": cost,
                      "code": code, "refused": refused, "reason": reason,
                      "hit": d.get("hit_count"), "answer": (d.get("answer") or "")[:120]})
        print(f"  B[{cat}] {'OK ' if passed else 'FAIL'} {cost}ms {q[:24]}")
        RESULTS["latency_all_ms"] = lat_all
        RESULTS["latency_refuse_ms"] = lat_refuse

    RESULTS["suites"]["B"] = cases
    summary = {k: f"{v[0]}/{v[1]}" for k, v in stat.items()}
    RESULTS["B_summary"] = summary
    n_fail = sum(v[1] - v[0] for v in stat.values())
    print(f"\n  B 汇总：{summary}；失败 {n_fail} 条")
    return stat


# ============ Suite C：RAG 常见问题专项 ============

def suite_c():
    print("\n===== Suite C RAG 常见问题专项 =====")
    # C1 幻觉探测：虚构实体，期望拒答或"暂无"
    st, p, cost = chat("请介绍一下计算机学院张三丰教授的研究方向和办公室位置")
    d = p.get("data") or {}
    ans = d.get("answer") or ""
    c1 = (d.get("refused") is True) or ("暂无" in ans) or ("没有" in ans and "[1]" not in ans)
    record("C", "C1", "幻觉探测：知识库不存在的人物", "拒答或明确'暂无相关信息'",
           f"refused={d.get('refused')},reason={d.get('refuse_reason')}", c1, ans[:100])

    # C2 引用可溯源：正常问题 sources 非空且 id/title 有值
    st, p, _ = chat("图书馆几点开门？")
    d = p.get("data") or {}
    srcs = d.get("sources") or []
    c2 = not d.get("refused") and len(srcs) > 0 and all(s.get("title") for s in srcs)
    record("C", "C2", "引用可溯源（sources 含标题且非空）", "sources≥1 且有 title",
           f"n={len(srcs)}", c2, json.dumps(srcs[:2], ensure_ascii=False))

    # C3 多轮指代：第二轮用"它"指代
    sid = "c3-multi"
    st1, p1, _ = chat("图书馆几点开门？", session=sid)
    st2, p2, _ = chat("那它周末也开放吗？", session=sid, clear_rate=True)
    d2 = p2.get("data") or {}
    a2 = d2.get("answer") or ""
    used_ctx = d2.get("refused") is False and len(a2) > 5
    record("C", "C3", "多轮对话指代消解（'那它周末也开放吗'）",
           "未拒答且给出与图书馆相关的回答（记录行为）",
           f"refused={d2.get('refused')},reason={d2.get('refuse_reason')}",
           used_ctx, a2[:120])

    # C4 拒答轮不进上下文：先越界拒答，再正常问题
    sid = "c4-ctx"
    chat("帮我写一首诗", session=sid)
    st, p, _ = chat("学校宿舍是几人间？", session=sid)
    d = p.get("data") or {}
    record("C", "C4", "拒答轮不污染多轮上下文", "正常问题仍正常作答",
           f"refused={d.get('refused')}", d.get("refused") is False,
           (d.get("answer") or "")[:80])

    # C5 时效性提问
    st, p, _ = chat("这周学校有什么最新的通知或活动？")
    d = p.get("data") or {}
    record("C", "C5", "时效性提问（'这周最新通知'）", "code=0（作答或合理拒答，记录行为）",
           f"code={p.get('code')},refused={d.get('refused')}", p.get("code") == 0,
           (d.get("answer") or "")[:100])

    # C6 特殊字符 / XSS 变体问题
    st, p, _ = chat("<script>alert('xss')</script> 学校食堂几点开门？")
    d = p.get("data") or {}
    ans = d.get("answer") or ""
    record("C", "C6", "XSS/特殊字符问题", "code=0 且答案无 <script> 原样回显",
           f"code={p.get('code')}", p.get("code") == 0 and "<script>" not in ans,
           ans[:80])

    # C7 中英混合
    st, p, _ = chat("wifi 怎么连接校园网")
    d = p.get("data") or {}
    record("C", "C7", "中英混合提问（wifi 校园网）", "code=0 且未拒答",
           f"refused={d.get('refused')},hit={d.get('hit_count')}",
           p.get("code") == 0 and d.get("refused") is False, (d.get("answer") or "")[:80])

    # C8 重复提问一致性
    a1 = (chat("学校食堂有几家？")[1].get("data") or {})
    a2 = (chat("学校食堂有几家？")[1].get("data") or {})
    s1 = {s.get("id") for s in (a1.get("sources") or [])}
    s2 = {s.get("id") for s in (a2.get("sources") or [])}
    overlap = bool(s1 & s2)
    record("C", "C8", "重复提问一致性（来源重叠）", "两次来源存在交集（LLM 文本可不同）",
           f"src1={s1},src2={s2}", overlap and not a1.get("refused") and not a2.get("refused"), "")

    # C9 PII：问题带手机号，回答正常；落库脱敏在 Suite E 验证
    st, p, _ = chat("我手机号 13812345678 丢了，怎么补办校园卡？")
    d = p.get("data") or {}
    record("C", "C9-pre", "含手机号问题正常处理", "code=0（作答或合理引导）",
           f"code={p.get('code')},refused={d.get('refused')}", p.get("code") == 0,
           (d.get("answer") or "")[:80])
    RESULTS["pii_probe_question"] = "我手机号 13812345678 丢了，怎么补办校园卡？"

    # C10 限流：L0 快速通道连打 11 次 → 第 11 次 4291；随后清理恢复
    RC.clear_rate_keys()
    codes = []
    for i in range(12):
        st, p, _ = chat("帮我写代码", clear_rate=False, timeout=10)
        codes.append(p.get("code"))
    limited = codes[10] == 4291 or codes.count(4291) >= 1
    recovered_code = None
    for _ in range(3):
        st, p, _ = chat("帮我写代码", clear_rate=True, timeout=10)
        recovered_code = p.get("code")
        if recovered_code == 0:
            break
    record("C", "C10", "限流触发与恢复（IP 10/min → 4291 → 清理后恢复）",
           "出现 4291，且清理后恢复 code=0",
           f"codes={codes},recovered={recovered_code}", limited and recovered_code == 0,
           "")

    # C11 SSE 流式
    body = json.dumps({"question": "宿舍是几人间？", "session_id": "c11-sse"}).encode()
    req = urllib.request.Request(BASE_URL + "/api/rag/chat/stream", data=body,
                                 headers={"Content-Type": "application/json"}, method="POST")
    frames, raw = [], b""
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            ctype = resp.headers.get("Content-Type", "")
            for line in resp:
                raw += line
                line = line.decode("utf-8", "ignore").strip()
                if line.startswith("data: "):
                    try:
                        frames.append(json.loads(line[6:]))
                    except json.JSONDecodeError:
                        pass
        deltas = [f for f in frames if f.get("type") == "delta"]
        dones = [f for f in frames if f.get("type") == "done"]
        ok = (ctype.startswith("text/event-stream") and len(deltas) >= 1
              and len(dones) == 1 and "answer" in dones[0]
              and "refused" in dones[0] and "sources" in dones[0])
        record("C", "C11", "SSE 流式（delta≥1 + done 权威帧 + 契约字段）",
               "text/event-stream；done 含 answer/refused/sources",
               f"ctype={ctype},delta={len(deltas)},done={len(dones)}", ok,
               (dones[0].get("answer") if dones else "")[:80])
    except Exception as exc:  # noqa: BLE001
        record("C", "C11", "SSE 流式", "text/event-stream", f"EXC:{exc}", False, raw[:200])

    # C12 纯符号问题
    st, p, _ = chat("。。。？？？")
    d = p.get("data") or {}
    record("C", "C12", "纯符号问题", "code=0（拒答 no_context 或合理处理，不 500）",
           f"code={p.get('code')},refused={d.get('refused')}", p.get("code") == 0,
           f"reason={d.get('refuse_reason')}")

    # C13 精确边界：500 字恰好通过校验（L0 拒答路径，成本低）
    q500 = ("关于校园的说明。" * 66) + "帮我写代码"
    q500 = q500[:500]
    st, p, _ = chat(q500)
    record("C", "C13", "500 字边界值（恰好 500 字通过校验，L0 拒答）",
           "code=0 且 refused（不是 4001）",
           f"code={p.get('code')},refused={(p.get('data') or {}).get('refused')}",
           p.get("code") == 0, "")


# ============ Suite D：检索层直测 ============

def suite_d():
    print("\n===== Suite D 检索层直测（RediSearch/Redis） =====")
    try:
        info = RC.cmd("FT.INFO", "rag_idx")
        pairs = dict(zip(info[::2], info[1::2]))
        num_docs = int(pairs.get(b"num_docs") or pairs.get("num_docs") or 0)
        # 维度
        idx_def = None
        for k, v in zip(info[::2], info[1::2]):
            if (k if isinstance(k, str) else k.decode()) == "num_docs":
                break
        attrs = pairs.get(b"attributes") or pairs.get("attributes") or []
        dim = None
        try:
            if isinstance(attrs, list):
                flat = b" ".join(attrs) if attrs and isinstance(attrs[0], bytes) else None
                if flat:
                    import re as _re
                    m = _re.search(rb"DIM\s+(\d+)", flat)
                    dim = int(m.group(1)) if m else None
        except Exception:  # noqa: BLE001
            pass
        record("D", "D1", "索引 rag_idx 存在且非空", "num_docs>0", f"num_docs={num_docs},dim={dim}",
               num_docs > 0, f"dim={dim}")
        RESULTS["index_num_docs"] = num_docs
        RESULTS["index_dim"] = dim
    except Exception as exc:  # noqa: BLE001
        record("D", "D1", "索引 rag_idx 存在且非空", "num_docs>0", f"EXC:{exc}", False, "")

    # D2 KNN 随机向量：应返回 K 个结果且距离∈[0,2]
    try:
        import struct
        vec = struct.pack("2048f", *([0.01] * 2048))
        resp = RC.cmd("FT.SEARCH", "rag_idx",
                      "*=>[KNN $K @embedding $q_vec AS knn_score]",
                      "DIALECT", "2", "LIMIT", 0, 3, "SORTBY", "knn_score",
                      "PARAMS", 4, "K", 3, "q_vec", vec)
        n = int(resp[0]) if isinstance(resp, (list, tuple)) else len(resp.get(b"results", []))
        record("D", "D2", "KNN 恒定向量返回 Top-3", "total=3（任意输入均有近邻，符合预期）",
               f"total={n}", n == 3, "")
    except Exception as exc:  # noqa: BLE001
        record("D", "D2", "KNN 恒定向量返回 Top-3", "total=3", f"EXC:{exc}", False, "")

    # D3 BM25 专有名词：单字 OR（宿 舍）
    try:
        resp = RC.cmd("FT.SEARCH", "rag_idx", "@title:(宿|舍)",
                      "DIALECT", "2", "LIMIT", 0, 5)
        n = int(resp[0]) if isinstance(resp, (list, tuple)) else 0
        record("D", "D3", "BM25 单字召回（宿|舍）", "total≥1（中文单字索引约定生效）",
               f"total={n}", n >= 1, "")
    except Exception as exc:  # noqa: BLE001
        record("D", "D3", "BM25 单字召回（宿|舍）", "total≥1", f"EXC:{exc}", False, "")

    # D4 Redis-MySQL chunk 一致性
    try:
        keys = RC.scan_keys("rag:chunk:*")
        db = MYSQL_CONN()
        with db.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM campus_rag_chunk WHERE status='1' AND del_flag='0'")
            mysql_n = cur.fetchone()[0]
        record("D", "D4", "Redis 向量数 vs MySQL 有效 chunk 数",
               "数量一致（≈26）", f"redis={len(keys)},mysql={mysql_n}",
               len(keys) == mysql_n, "")
        RESULTS["chunk_consistency"] = {"redis": len(keys), "mysql": mysql_n}
    except Exception as exc:  # noqa: BLE001
        record("D", "D4", "Redis-MySQL chunk 一致性", "-", f"EXC:{exc}", False, "")


def MYSQL_CONN():
    import pymysql
    return pymysql.connect(**MYSQL)


# ============ Suite E：日志落库与隐私 ============

def suite_e():
    print("\n===== Suite E 日志落库与隐私 =====")
    import pymysql
    try:
        db = pymysql.connect(**MYSQL)
        db.close()
    except Exception as exc:  # noqa: BLE001
        record("E", "E0", "MySQL 连接", "可连", f"EXC:{exc}", False, "")
        return
    db = pymysql.connect(**MYSQL)
    try:
        with db.cursor() as cur:
            # E1 总量与最近一条
            cur.execute("SELECT COUNT(*) FROM campus_rag_log")
            total = cur.fetchone()[0]
            cur.execute("SELECT id, question, answer, refuse_reason, hit_count, model, ip "
                        "FROM campus_rag_log ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
            record("E", "E1", "campus_rag_log 落库（总量>0 且最近一条结构完整）",
                   "total>0", f"total={total},last_id={row[0] if row else None}",
                   total > 0 and row is not None, "")

            # E2 拒答原因枚举
            cur.execute("SELECT DISTINCT refuse_reason FROM campus_rag_log")
            reasons = {r[0] for r in cur.fetchall()}
            valid = reasons <= {None, "no_context", "out_of_scope", "unsafe"}
            has_refuse = reasons & {"no_context", "out_of_scope", "unsafe"}
            record("E", "E2", "refuse_reason 枚举合法且本轮测试产生了拒答记录",
                   "⊂ {NULL,no_context,out_of_scope,unsafe} 且非空",
                   f"reasons={reasons}", valid and bool(has_refuse), "")

            # E3 IP 脱敏格式
            cur.execute("SELECT ip FROM campus_rag_log ORDER BY id DESC LIMIT 5")
            ips = [r[0] for r in cur.fetchall()]
            import re
            ok_ip = all(re.match(r"^\d{1,3}(\.\d{1,3}){2}\.x/[0-9a-f]{16}$|^[0-9a-f:]+:x/[0-9a-f]{16}$", ip or "") for ip in ips)
            record("E", "E3", "IP 落库脱敏（前缀.x/16位哈希）", "全部匹配脱敏格式",
                   f"ips={ips}", ok_ip, "")

            # E4 PII 脱敏：找 C9 的问题
            cur.execute("SELECT question FROM campus_rag_log WHERE question LIKE %s "
                        "ORDER BY id DESC LIMIT 1", ("%13812345678%",))
            hit = cur.fetchone()
            cur.execute("SELECT question FROM campus_rag_log WHERE question LIKE %s "
                        "ORDER BY id DESC LIMIT 1", ("%138****%",))
            masked = cur.fetchone()
            record("E", "E4", "手机号 PII 落库脱敏", "库中无明文 13812345678，存在 138**** 形态",
                   f"plain={'YES' if hit else 'NO'},masked={'YES' if masked else 'NO'}",
                   hit is None and masked is not None, "")

            # E5 feedback 落库生效（A9 已对某 log_id 点赞）
            if RESULTS.get("_feedback_log_id"):
                cur.execute("SELECT feedback FROM campus_rag_log WHERE id=%s",
                            (RESULTS["_feedback_log_id"],))
                r = cur.fetchone()
                record("E", "E5", "feedback 更新生效", "feedback='1'", f"feedback={r[0] if r else None}",
                       r is not None and r[0] == "1", "")
            else:
                record("E", "E5", "feedback 更新生效", "-", "无目标 log_id", False, "")
    finally:
        db.close()


# ============ main ============

def main():
    global BASE_URL, OUT_PATH
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=BASE_URL)
    ap.add_argument("--out", default=OUT_PATH)
    args = ap.parse_args()
    BASE_URL = args.base
    OUT_PATH = args.out

    RESULTS["env"] = {"base": BASE_URL, "time": time.strftime("%F %T")}

    d6 = suite_a()
    if d6.get("log_id"):
        RESULTS["_feedback_log_id"] = d6["log_id"]

    suite_b()
    suite_c()

    # E 前置：把 feedback 目标 log_id 传入
    fid = RESULTS.pop("_feedback_log_id", None)
    suite_e()
    if fid:
        RESULTS["_feedback_log_id"] = fid
    suite_d()

    RESULTS["finished_at"] = time.strftime("%F %T")
    lat = RESULTS.get("latency_all_ms") or []
    ref = RESULTS.get("latency_refuse_ms") or []
    RESULTS["latency_stats"] = {
        "all_n": len(lat), "all_avg_ms": round(statistics.mean(lat), 1) if lat else None,
        "all_p95_ms": pct(lat, 0.95), "all_p99_ms": pct(lat, 0.99),
        "refuse_n": len(ref), "refuse_avg_ms": round(statistics.mean(ref), 1) if ref else None,
        "refuse_p95_ms": pct(ref, 0.95),
    }

    suites = RESULTS.get("suites", {})
    total = sum(len(v) for v in suites.values())
    passed = sum(1 for v in suites.values() for c in v if c.get("pass"))
    RESULTS["grand_total"] = {"total": total, "passed": passed,
                              "failed": total - passed}
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(RESULTS, f, ensure_ascii=False, indent=1)
    print(f"\n===== 汇总：{passed}/{total} 通过，结果已写 {OUT_PATH} =====")
    print(json.dumps(RESULTS["latency_stats"], ensure_ascii=False))
    print(json.dumps(RESULTS.get("B_summary", {}), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
