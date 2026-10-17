# AGENTS.md — 执行代理工作约定

本项目的分工：Opus 制定方案并审查，其他模型（目前是 GPT）负责执行。执行代理开始任何工作前，按顺序读完下面这些文档：

1. [`docs/rules.md`](docs/rules.md)：字段、校验、交互和统计口径，是**唯一的事实来源**。
2. [`docs/architecture.md`](docs/architecture.md)：多端架构和已经定下的决策。
3. [`docs/api/openapi.yaml`](docs/api/openapi.yaml)：接口契约。
4. 当前任务所属的计划，比如 [`docs/android-plan.md`](docs/android-plan.md)。

## 项目速览

| 位置 | 内容 |
|---|---|
| `server.py` | 后端：只用 Python 3.9+ 标准库，数据存在 SQLite，零第三方依赖 |
| `static/` | 前端：原生 HTML/CSS/JS，没有框架和构建步骤。同一份代码也是 App 的界面 |
| `tests/test_server.py` | 后端接口测试（unittest） |
| `tools/` | 开发工具脚本，只用标准库 |
| `deploy/` | 服务器部署示例 |
| `mobile/` | Capacitor 工程，在安卓计划 P3 中创建 |

## 常用命令

```bash
python3 -m unittest discover -s tests -v
python3 server.py set-password --db /tmp/dev.db
python3 server.py serve --db /tmp/dev.db
node --check static/app.js
node --check static/dashboard.js
```

本机沙箱可能禁止监听端口，测试报 `PermissionError: [Errno 1] Operation not permitted` 时，需要在允许监听本地端口的环境中运行。

## 硬性约束（违反任何一条即为不合格）

1. **不擅自改规则和契约**：不得改变 `docs/rules.md` 中的规则、`docs/api/openapi.yaml` 中的契约、`docs/architecture.md` 中的决策。确实需要改时，停下来写明原因，等待确认。唯一例外是：删除已实现项上的 `x-status: planned`。
2. **依赖限制**：
   - 后端只能用 Python 标准库。
   - Web 前端不引入任何第三方库、CDN、外部字体或构建步骤。
   - App 只能使用计划白名单中的依赖。所有依赖写精确版本号，提交 lock 文件，用 `npm ci` 安装。
3. **不加任何统计、埋点、崩溃上报、广告或远程配置**。App 只和用户配置的服务器通信，不从网络加载代码。
4. **秘密**：密码、令牌、keystore 及其密码永远不提交、不写进日志、不放进 URL。执行代理不生成、不读取、不打印用户的签名密钥。在日志里展示令牌时，只保留前 6 位。
5. **Web 端不受影响**：除非计划明确要求，Web 端的行为必须保持不变。每个阶段都要跑 `docs/android-plan.md` 附录 A 的回归清单。
6. **数据库迁移**：数据库结构只能通过在 `MIGRATIONS` 末尾追加迁移函数来修改，已有的迁移永远不改；每个迁移都要有测试。
7. **不弱化安全设置**：包括 CSP、Cookie 属性、登录限流、PBKDF2 参数、CORS 白名单规则，以及发布版的明文流量、调试和备份设置。
8. **不改现有测试**：不得删除或放宽现有测试的断言，只能新增测试。如果现有测试必须改，停下来说明原因。

## 代码风格

- **和周围的代码保持一致**：注释用中文，写得简洁；用户能看到的文字一律用简体中文，语气与现有提示一致。
- **JavaScript**：
  - 使用 `"use strict"`，缩进 2 个空格，字符串用双引号。
  - 用 `h()` 创建 DOM 元素；禁止把用户数据拼进 `innerHTML`。
  - 不要设置 `style` 属性字符串，因为 CSP 不允许；需要时用 `el.style.xxx = ...`。
- **Python**：缩进 4 个空格，沿用现有结构：用 `ApiError` 报错，用 `validate_*` 和 `parse_*` 做校验，数据库操作写成 `Database` 的方法。
- **CSS**：颜色一律用 `:root` 中的变量，深色模式在 `@media (prefers-color-scheme: dark)` 中重新定义。不要单独改动交通方式的配色（见 rules.md 第 1 节）。
- **不要顺手重构**与当前任务无关的代码，不要顺手改格式。

## 工作流程

1. 按计划的阶段顺序执行，一个阶段一个分支，分支名用计划里规定的名字。
2. 只改计划中列出的文件和目录。
3. 完成后逐条核对该阶段的「验收」，在 [`docs/android-log.md`](docs/android-log.md) 末尾按模板追加记录，然后提交并停下，等待审查。没有收到继续的指示前，不开始下一阶段。
4. 提交信息用中文，格式为 `类型: 说明`，例如 `feat: 新增令牌登录`、`test: 覆盖 CORS 预检`、`docs: 补充发布说明`。

### 遇到下列情况立即停下

先说明情况，等待确认后再继续，不要自行决定：

- 需要计划白名单之外的依赖；
- 需要修改规则、契约或架构决策；
- 官方文档与计划冲突，并且影响安全或数据；
- 任务描述有歧义，不同理解会导致不同的实现；
- 需要用户本人操作，比如接受许可协议、生成或提供密钥、在真机上安装。

## 完成的定义（每个阶段）

- 该阶段「验收」中的每一条都满足，并在日志里逐条给出证据：命令输出摘要、截图文件名或测试名称。
- `python3 -m unittest discover -s tests` 全部通过。
- Web 回归清单全部通过。
- 所有与计划不一致的地方都写进了日志的「偏差」部分。
