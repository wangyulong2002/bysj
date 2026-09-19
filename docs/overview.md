# RAG 专项测试 — 任务概览

## 完成内容
对 bysj（智慧校园系统）的 RAG 智能问答模块执行了一套专业测试，并输出测试报告。

- **测试面**：先梳理 RAG 常见 14 类问题（幻觉、误拒、引用伪造、提示词注入、越界漂移、多轮失效、检索一致性、PII 隐私、限流、边界输入、降级、性能、知识覆盖），逐项映射为 88 条测试用例，分 5 个 Suite 端到端执行。
- **产出物**：
  - `bysj/docs/RAG专项测试报告.md` —— 主报告
  - `bysj/scripts/rag_pro_test.py` —— 可复跑测试脚本（A 契约 / B 七类评测 / C 专项 / D 检索层直测 / E 日志隐私）
  - `bysj/scripts/rag_pro_test_results.json` —— 原始逐题结果

## 关键结果
- 总体 84/88 通过（95.5%）；安全类全部达标：越界拒答 8/8、注入拦截 8/8、PII/IP 落库全脱敏、限流 4291 触发与恢复正常。
- 3 项真实缺陷：
  1. L1 阈值误拒（"宿舍热水"内容存在但 best_sim<0.45，BM25 仅索引 title 无法兜底）
  2. 弱相关档"语义拒答但 refused=false"（LLM 输出"暂无相关信息"而非 [[NO_ANSWER]] 哨兵）
  3. 多轮指代追问必拒（检索侧未做问题改写，历史仅参与生成）
- 性能：端到端 P95 9.5s（超 4s 目标，与设计注记一致）；L0 拒答 8~481ms 达标，L1 拒答超 0.3s 口径。
- 发现模型选型三方不一致（设计 ark-code-latest / 代码默认 deepseek-chat / 运行时 doubao-seed-2.0-lite），已提示回归纪律。

## 续轮补充（同日）
- **单元测试 49/49 全部通过**（server/venv Windows venv 补装 pytest/openai/httpx/langchain-core/numpy/tzdata 后执行）。
- **离线检索评测达标**：Recall@5=0.970、Recall@10=0.970、MRR=0.939、误拒率 0/33；无答案 L1 硬拦截率仅 6/8（2 条 sim=0.464/0.491 穿透直达 LLM），阈值标定因 embedding 429 限流未跑完。
- **高危发现 + 事故**：RAG 单测缺环境隔离，test_full_rebuild 直连真实共享 Redis，执行时清空了线上向量索引（chat 全部降级拒答）；通过写入 rag:rebuild_requested 标记触发 WSL worker 全量重建，约 20 秒恢复 num_docs=26。已列为报告 P0 改进项。
- 报告第 7 章改进建议：P0 测试隔离 → P1 L3 拒答后处理/BM25 正文索引 → P2 多轮改写/阈值标定 → P3 延迟口径/模型一致性/知识库扩容。
