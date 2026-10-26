# Cloudflare Implementation Plan

> For agentic workers: use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 完成已授权的私有 GitHub 上传和 Workers＋D1 部署。
**Architecture:** 保留 Python 服务，复用业务校验；新增 Python Worker 请求适配、异步D1存储和原样静态资源。
**Tech Stack:** Python标准库、Cloudflare workers-py、Wrangler、D1；精确锁版本。
**Spec:** docs/superpowers/specs/2026-10-26-cloudflare.md

## Global Constraints
- 不改变 docs/rules.md 和 OpenAPI、现有安全参数、现有测试断言、static/。
- 数据库不写临时文件系统；D1迁移只追加，不改 server.MIGRATIONS。
- 密码／令牌不写Git／日志；本地密码由用户输入，远端仅存哈希与会话指纹。
- 无收费升级、无安卓工作、无统计SDK；GitHub默认私有。

## Review Focus
- 并发登录和Worker多实例不能绕过同IP限流。
- 导入中途SQL失败必须整批回滚，区段必须关联正确的行程。
- 密码变更后旧Cookie和令牌全部失效。
- 超大请求、未知方法、错误响应也保持CORS／CSP。
- 部署及Secret配置不能把测试密码或本地个人行程带到生产。

## Tasks
- [x] 1. 审查全部Git历史、创建私有仓库、通过严格SSH主机校验上传并核对远端。
- [x] 2. 先编写D1真SQL和API测试并观察失败；实现核心存储与请求适配；测试转绿。
- [x] 3. 精确锁定官方工具、配置静态资源与Python入口；实际运行Worker验证，不依赖仅模拟成功。
- [x] 4. 新增安全密码初始化工具、追加架构与部署说明；保持原Python测试49项通过。
- [x] 5. Web附录A回归；再次敏感审查；提交并推送适配分支。
- [x] 6. 完成Cloudflare授权，创建独立D1、应用迁移、部署；检查线上路由、身份拒绝、资源和配额，记录URL与用户需要完成的密码初始化。
