# Cloudflare 部署

原有 Python／SQLite 版继续保留。本部署采用 Python Worker、D1 和原样打包的 `static/`，无需 Android 环境。数据库不会保存在 Worker 的临时文件系统。

## 安全与数据

- GitHub仓库默认私有。上传前检查跟踪文件、历史对象、数据库／环境文件路径和常见凭据格式；只上传源代码与文档，不上传本机个人行程、数据库、密码、令牌或签名文件。
- 本机测试的 `.dev.vars`、D1状态、虚拟环境、构建目录都已忽略；禁止把测试密码配置到生产。
- 生产密码仅在本机交互终端输入，通过标准输入把PBKDF2哈希发送为Cloudflare Secret；不写命令参数、URL或仓库。
- 原密码算法与600000次迭代不变。WASM缺少OpenSSL的 `hashlib.pbkdf2_hmac`，所以仅Cloudflare适配使用用户批准的 `cryptography==47.0.0`（Pyodide314.0.7预编译版本）；本地Python版仍然零依赖。
- Web继续使用Secure／HttpOnly／SameSite=Strict Cookie；令牌与Cookie隔离、Authorization优先、密码变更令旧会话失效。失败次数保存在D1，两个登录入口共用。
- 不启用应用统计、埋点或Worker可观测性采集。账户本身的平台配额与计费由Cloudflare管理；未获确认不开通付费计划。

## 开发环境

使用Node22以上、Python3.12以上和uv。执行：

```bash
npm ci
uv sync --locked
npm run cf:dev
```

Cloudflare官方SDK要求uv≥0.13.4；本项目已把该版本锁定在项目虚拟环境，`uv run` 的子进程使用它，不升级系统工具。Wrangler、workers-py和运行时SDK均由锁文件管理。

本机密码哈希仅放在已忽略的 `.dev.vars` 中，键名为 `PASSWORD_HASH`。本机D1迁移：

```bash
npx wrangler d1 migrations apply travel-log --local
```

## 首次部署

`wrangler.jsonc` 中的D1标识对应此账户的独立 `travel-log` 数据库；换账户时先新建D1并替换该标识。不得把已有数据库绑定到新项目后直接运行迁移。

```bash
npx wrangler whoami
npm run cf:migrate
npm run cf:deploy
python3 tools/cloudflare_admin.py
```

最后一条必须在用户本机交互终端执行，输入两次至少8位密码。只上传PBKDF2哈希，完成后旧Cookie与App令牌失效。未设置密码时服务器拒绝登录（503），不会存在默认生产密码。

首次部署不自动迁移个人行程；用户可在原站导出JSON，再在新站导入。导入仍只追加、不去重。

## 验证与更新

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v
PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests -v
node --check static/platform.js
node --check static/app.js
node --check static/dashboard.js
```

第一条验证原Python环境；第二条还验证WASM密码算法适配的标准向量及与原600000次哈希的一致性。部署前必须在真实Worker上验证登录、事务和配额，不能仅依据本机单元测试。

后续更新先跑测试和Web回归，再应用新增迁移、部署。旧D1迁移不得修改。构建脚本只复制四个运行模块，不能修改 `server.py` 或 `static/`。

## 依据

- [Cloudflare Python Workers](https://developers.cloudflare.com/workers/languages/python/)
- [Python运行时标准库限制](https://developers.cloudflare.com/workers/languages/python/stdlib/)
- [D1 Python绑定](https://developers.cloudflare.com/d1/examples/query-d1-from-python-workers/)
- [Pyodide314.0.7的cryptography构建](https://index.pyodide.org/314.0.7/cryptography/)
