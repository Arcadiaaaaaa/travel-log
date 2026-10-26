# Cloudflare 部署适配

用户于 2026-10-26 授权新增 Workers＋D1 部署适配、架构说明及 Cloudflare 官方运行时／工具依赖例外。安卓继续暂停。

目标：先审查 Git 历史并上传私有 GitHub，再把现有 Web 和全部 API 部署到 Cloudflare，保留本地 Python 服务与既有业务、安全契约。

方案：采用 Python Worker 的请求入口和异步 D1 数据层，直接复用 server.py 的校验、格式化及 PBKDF2 600000 次参数；static/ 原样作为 Worker 静态资源。原 ThreadingHTTPServer 与 SQLite 文件版不改动。仅发布静态页面无法运行 API；临时文件系统不能保存业务数据库，因此选择 D1。

持久化：新 D1 使用独立追加式 SQL 迁移，初始业务结构与现有三个迁移后的结构一致；增加仅部署端使用的批次关联字段，以 JSON 批量 SQL 和 D1 batch 保证多段换乘、导入、修改的原子性。限流记录持久保存在 D1，Web／App 两入口共用。不要修改 server.py 已有迁移。

认证：密码哈希使用 Worker Secret，原密码只在用户本地的 getpass 交互中出现；会话保存 SHA-256、kind、有效期及密码版本指纹，变更 Secret 后旧会话即失效。Cookie 固定30天、HttpOnly、SameSite=Strict、HTTPS Secure；令牌90天滑动续期、每天至多一次。Authorization 优先且不回退 Cookie。CORS 及安全头完全遵守契约。未初始化密码时拒绝登录，不能部署公共测试密码。

范围：新增 cloudflare_core.py、cloudflare_crypto.py、cloudflare_worker.py、cloudflare/migrations/、wrangler.jsonc、pyproject.toml／uv.lock、package.json／package-lock.json、tools/cloudflare_admin.py、tools/build_cloudflare.py、pylock.toml、新测试与部署文档。只补充架构的 Cloudflare 选项与 README 链接，不改变原规则、OpenAPI、现有测试或 static/。

验收：原49项测试不改且通过；新增 D1 真 SQL 测试覆盖事务回滚、CRUD、导入、认证优先级、隔离、限流、滑动过期、密码变更、CORS错误响应及安全头；Python Worker 本地实际运行并检查全部路由；Web附录A回归；部署后检查元信息、静态资源、未授权拒绝和真实域名，登录密码由用户初始化。核实配额是否承载600000次PBKDF2，不能降低安全参数或擅自开通付费。每次推送前重新扫描，业务数据不上传GitHub。

构建选择由执行者按官方SDK确定，工具版本精确锁定；不添加框架、统计、埋点或远程代码。GitHub上传已在原历史通过审查后完成，后续适配使用独立 codex/cloudflare-deploy 分支，不合并未经审查的安卓分支。

2026-10-26追加用户授权：允许Cloudflare适配依赖cryptography，保持60万次PBKDF2。Pyodide314.0.7的预编译支持版本为47.0.0，运行包与本机包均锁定；不能把本机通过视为云端配额通过。
