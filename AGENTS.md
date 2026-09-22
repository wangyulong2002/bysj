# 项目规则（AGENTS.md）

本文件随 bysj 项目仓库分发，每次会话自动加载，是所有编码行为的最优先约束。**优先级高于一般对话指令，仅低于用户显式覆盖。**

## 项目背景

本项目为 **bysj/ —— 智慧校园信息管理系统**。技术栈：FastAPI + uni-app + Django 5.2 LTS（Django REST Framework 管理端）。设计权威基线为《智慧校园信息管理系统 设计报告》（`docs/智慧校园信息管理系统-设计报告.md`，**v2.9**；v2.9 = 按《企业级代码审核报告》完成 P0+P1 整改并回写，见报告第 16 章）。

## 编码铁律（强制）

1. **编码前必读设计报告**：开始任何代码改动（建表/接口/页面/配置/部署/修复）前，必须先调用 `design-report` skill，并按该 skill 流程读取设计报告对应章节。未读取设计约束前，不得开始写实现代码。
2. **遵循设计约定**：统一响应 `{code,message,data}`、错误码体系、`campus_`/`sys_` 表前缀、端口约定（FastAPI 8000 / Django 8001 / MySQL 3307 / Redis 6379）、数据权限与防 IDOR 规则。任何与设计报告的偏差必须向用户说明并获得同意。
   - **HTTP 状态码双层映射（v2.9/P0-1，强制）**：业务 `code` 必须保留在响应体内，**同时 HTTP status 按语义返回**（唯一权威表 `server/app/core/errors.py:HTTP_STATUS_MAP`）。**禁止**把异常一律返回 HTTP 200。
   - **DDL 单一真相（v2.9/P0-4，强制）**：结构变更只能「改 Django Model → `makemigrations` → `migrate`」；`sql/init_all.sql` 已废弃（DEPRECATED，禁止执行/手改），字典数据走 `sql/seed_dict.sql`（纯 DML），结构查阅走 `sql/schema_export.sql`（自动导出产物）。提交前跑 `make ddl-check`。
   - **破坏性脚本护栏（v2.9/P0-3）**：`init_db.sh` 仅允许 `APP_ENV=dev`，执行前强制备份 + 二次确认。**不得**绕过护栏。
   - **密码与时间源（v2.9/P0-2/P1-13）**：密码哈希一律用 Django 官方 `make_password/check_password`（禁止自实现）；时间一律用 `server/app/core/time.py:now()`（Asia/Shanghai），不要在业务代码里裸用 `datetime.now()`。
   - **测试环境（v2.9/P0-5）**：后端测试必须跑在独立库 `campus_test`（`MYSQL_DB_TEST`），测试用例需**数据自足**（不依赖种子数据）；新增用例不得直连业务库。
3. **子任务清单驱动**：开发任务对应《子任务执行清单》中的子任务（T0-1 ~ T9-4），实施前先定位该子任务的"关联设计"章节与"验收要点"。
4. **开发后对照验收**：实现完成后，对照设计报告第 13 章验收标准与对应功能章节逐条自查。
5. **前端技能门禁（强制）**：所有前端代码开发（uni-app 页面/组件、管理端页面、Django 模板页面、请求封装、样式/动效、页面交互），在实现前**必须**加载并遵循 `ui-skill` 与 `soft-ui` 两个 skill；未加载前不得开始写任何前端代码。视觉风格遵循这两个 skill，页面结构以设计报告 7.1/7.2 为准。

## 技能流水线（按序执行）

```
design-report（读取设计约束）
    → brainstorming（新功能/新模块：方案设计获批后才写代码）
    → 【前端开发时】ui-skill + soft-ui（前端技能门禁，铁律 5）
    → dev-quality-loop（实施：TDD 测试先行 + 代码审查）
    → systematic-debugging（遇到 bug/异常时）
```

## 开发环境速记

- 服务统一在 WSL 内运行；
- MySQL/Redis 为 Docker 容器（端口 3307/6379）；Python 虚拟环境 `server/venv_wsl/`。
- 详细环境见 `docs/环境版本清单.md`。

## 常用命令（v2.9 新增）

| 命令 | 用途 |
|---|---|
| `make ddl-check` | DDL 漂移门禁（模型 vs 迁移），提交前必跑 |
| `make ddl-export` | 导出 `sql/schema_export.sql`（只读产物） |
| `make rag-worker` | 启动 RAG Worker 独立进程（Web 进程默认不再跑调度） |
| `make lock-deps` | 生成依赖锁文件（需 pip-tools） |
| `make init-db` | 数据库初始化（仅 dev；自动备份 + 二次确认） |
| `pytest` | 后端测试（自动使用 `campus_test` 独立库） |
