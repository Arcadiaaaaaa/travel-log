# 安卓 App 实施计划

- **执行者**：GPT。开始前先读 [`AGENTS.md`](../AGENTS.md)、[`rules.md`](rules.md)、[`architecture.md`](architecture.md)、[`api/openapi.yaml`](api/openapi.yaml)。
- **方案与审查**：Opus。
- **决策与操作**：用户。包括安装开发工具、接受许可协议、生成签名密钥、合并分支。

## 0. 目标与范围

**第一版目标**：一个在线使用的安卓 App，功能与 Web 端完全一致，包括记录、编辑、地铁换乘、看板、导入导出。另外有这些 App 特有的功能：

- 在登录页填写服务器地址；
- 支持安卓返回键；
- 适配状态栏、导航栏和深色模式；
- 导出时调用系统分享面板。

**第一版不做**：离线记录、已登录设备管理、推送、桌面小组件、上架应用商店。

**完成的标志**：签名后的 release APK 装在真机上，附录 B 的清单全部通过，Opus 终审通过。

## 1. 阶段与审查点

| 阶段 | 内容 | 主要改动 | 审查 |
|---|---|---|---|
| P0 | 仓库准备 | git、`.gitignore`、日志 | — |
| P1 | 服务器：`/api/meta`、令牌登录、CORS | `server.py`、`tests/`、`README.md` | **① Opus 审查**（涉及安全） |
| P2 | 前端平台层（Web 行为不变） | `static/` | 与 P3 一起审查 |
| P3 | Capacitor 安卓工程 | `mobile/`、`tools/` | **② Opus 审查** |
| P4 | 签名、发布脚本、文档 | `mobile/`、`docs/` | **③ Opus 终审** |

- 每个阶段一个分支：`android/p0-repo`、`android/p1-server-auth`、`android/p2-platform`、`android/p3-capacitor`、`android/p4-release`。
- 阶段完成后停下，在 [`android-log.md`](android-log.md) 写好记录，等待审查。审查通过后由用户合并到 `main`，再从 `main` 开下一个分支。
- 审查点①之前不得开始 P2，审查点②之前不得开始 P4。

## 2. 前置条件

**本机现状**（2026-10-19 复核）：Node 26.7.0、npm 11.19.0、git 2.55.0、Python 3.14.7。已安装 Temurin JDK 25.0.3（`/Library/Java/JavaVirtualMachines/temurin-25.jdk`，在沙箱里 `java_home` 可能找不到它）。**还没有 Android SDK 和 Android Studio。**

**JDK 用哪个**：构建安卓工程时，用 Android Studio 自带的 JDK（见下面第 2 步），不要用系统里的 JDK 25。Capacitor 模板里的 Gradle 和 Android Gradle 插件，通常还不支持在 JDK 25 上运行。只有官方文档明确写了支持 JDK 25，才可以改用，并要写进日志。

**需要用户自己完成的**（涉及许可协议，执行者不得代为接受）：

1. 安装最新稳定版 Android Studio，在 SDK Manager 里装好 Capacitor 模板所需的 SDK Platform、Build-Tools，以及一个最新稳定 API 的 arm64 模拟器镜像，并接受许可协议。
2. 设置环境变量：`ANDROID_HOME`（一般是 `~/Library/Android/sdk`），`JAVA_HOME` 指向 Android Studio 自带的 JDK（如 `/Applications/Android Studio.app/Contents/jbr/Contents/Home`），把 `$ANDROID_HOME/platform-tools` 加入 `PATH`。

**执行者在 P3 开始时要确认的**：

- 当前 Capacitor 最新稳定大版本要求的 Node、JDK、Android Studio 和 SDK 版本，以官方文档为准，和本机核对，写进日志。版本不符时停下报告，不要自行降级或升级系统工具。

## 3. P0 仓库准备

**任务**

1. 在项目根目录 `git init`，默认分支为 `main`。
2. 在 `.gitignore` 中追加：
   ```
   .claude/launch.json
   mobile/node_modules/
   mobile/www/
   mobile/dist/
   mobile/android/keystore.properties
   *.jks
   *.keystore
   .DS_Store
   ```
3. 运行 `python3 -m unittest discover -s tests`，确认全部通过（目前 14 个）。
4. 把现有代码原样提交为基线：`chore: 初始提交`。
5. 在 `docs/android-log.md` 填写 P0 记录。

**验收**：`git status` 干净；测试全部通过；`git ls-files` 中没有数据库、`.claude/launch.json` 和 `__pycache__`。

## 4. P1 服务器：`/api/meta`、令牌登录、CORS

只改 `server.py`、`tests/test_server.py`、`README.md`，以及把 `docs/api/openapi.yaml` 中已实现项的 `x-status: planned` 删掉。**接口行为必须与 openapi.yaml、architecture.md 第 3 节完全一致。**

### P1.0 修复 `/favicon.ico` 404（P0 审查时发现的老问题）

- **现象**：页面声明的图标是 `/icons/icon-192.png`，但 Chromium 系浏览器再次打开页面时，仍会请求 `/favicon.ico`，服务器返回 404，Console 里出现报错。这个问题从第一版就有，与 P0 的改动无关。
- **修法**：在 `serve_static()` 里把 `/favicon.ico` 映射到 `icons/icon-192.png`，返回 200，`Content-Type: image/png`。可以直接采用 P0 准备的补丁（`/tmp/travel-p0-evidence/favicon-proposal.patch`）。不要新增 `.ico` 文件，也不要把 `.ico` 加进 `CONTENT_TYPES`。
- **测试**：新增 `test_favicon`，检查状态码、`Content-Type`，以及返回内容与 `icon-192.png` 完全相同。
- 单独提交：`fix: 为 /favicon.ico 返回应用图标`。

### P1.1 版本常量与 `GET /api/meta`

- 新增常量 `SERVER_VERSION = "1.0.0"`、`API_VERSION = 1`。
- `GET /api/meta` 不需要登录，返回 `{"app": "travel-log", "api_version": 1, "server_version": "1.0.0"}`，不返回任何其他信息。

### P1.2 会话表迁移（`migrate_v3`）

- 在 `MIGRATIONS` 末尾追加 `migrate_v3`，不要修改已有迁移。
- 给 `sessions` 表加 4 列：`kind TEXT NOT NULL DEFAULT 'cookie'`、`device_name TEXT NOT NULL DEFAULT ''`、`created_at INTEGER NOT NULL DEFAULT 0`、`last_used_at INTEGER NOT NULL DEFAULT 0`。
- 迁移前已有的会话按 Cookie 会话处理，继续有效。

### P1.3 令牌接口

- **`POST /api/tokens`**：
  - 流程与 `/api/login` 相同：先查限流，再读 JSON，再校验密码，失败时计数。
  - 校验 `device_name`：可以省略；必须是文本，否则返回 400「设备名称必须是文本」；去掉首尾空白后最多 50 字，否则返回 400「设备名称最多 50 个字」。
  - 成功后创建 `kind='token'` 的会话，有效期 90 天，返回 201 和 `{"token": …, "token_type": "Bearer", "expires_in": 7776000}`，**不设置 Cookie**。
- **`DELETE /api/tokens/current`**：必须带有效的 Bearer 令牌，删除这个令牌后返回 `{"ok": true}`；只带 Cookie 时返回 401。
- **令牌生成与存储**：沿用 `secrets.token_urlsafe(32)`；数据库只存 SHA-256。

### P1.4 判断登录状态

把 `current_token()` 改成一个返回（种类，令牌）或 `None` 的函数，规则如下：

1. 请求带了 `Authorization` 头时：
   - 头的格式必须是 `Bearer <令牌>`，令牌只含 `A-Z a-z 0-9 - _`；
   - 令牌必须在库里存在、`kind='token'`、并且没过期；
   - 不满足就当作未登录，**不再看 Cookie**。
2. 没带 `Authorization` 头时：按 Cookie `tl_session` 查 `kind='cookie'` 的会话，与现在的行为一样。
3. **滑动续期**：令牌每次通过验证后，若剩余有效期不足 89 天，就把 `expires_at` 更新为现在加 90 天，同时更新 `last_used_at`。Cookie 会话保持 30 天固定有效期，不续期。
4. `/api/session` 按上面的规则返回 `authenticated`。
5. `/api/logout` 的行为不变。

### P1.5 CORS

- **配置**：环境变量 `TRAVEL_CORS_ORIGINS` 是逗号分隔的列表，默认 `https://localhost,capacitor://localhost`；设为空字符串时关闭 CORS。`TravelServer` 增加 `cors_origins` 参数，方便测试。
- **只作用于 `/api/*`**。请求头 `Origin` 与白名单逐字完全相等时，响应加上 `Access-Control-Allow-Origin: <该来源>` 和 `Vary: Origin`。所有状态码的响应都要加，包括 401、404、429、500。
- **新增 `do_OPTIONS`**（预检请求）：
  - 来源在白名单内：返回 204，不带响应体，带上 `Access-Control-Allow-Methods: GET, POST, PUT, DELETE`、`Access-Control-Allow-Headers: Authorization, Content-Type`、`Access-Control-Max-Age: 600`，以及上面的两个头。
  - 来源不在白名单内或没有 `Origin`：返回 403 和 `{"error": "来源不被允许"}`，不带任何 CORS 头。
  - 非 `/api/` 路径：返回 405。
- **永远不要**返回 `Access-Control-Allow-Origin: *`，也不要返回 `Access-Control-Allow-Credentials`。

### P1.6 文档

- README 的环境变量表加上 `TRAVEL_CORS_ORIGINS`。
- 在 openapi.yaml 中删掉已实现项的 `x-status: planned`。除此之外不得修改契约。

### P1.7 测试

新增以下测试，每条一个断言主题。可以给测试辅助函数 `request()` 增加自定义请求头参数。

1. `/api/meta` 不登录也能访问，返回的字段恰好是这三个。
2. 用令牌登录：返回 201，`token_type` 是 `Bearer`，没有 `Set-Cookie`；拿令牌访问 `/api/trips` 成功。
3. `device_name` 是非文本、或超过 50 字时返回 400。
4. 令牌接口密码错误返回 401；在 `/api/tokens` 失败 5 次后，`/api/login` 也返回 429，即两者共用限流。
5. Cookie 会话的值放进 `Authorization: Bearer` 返回 401；令牌放进 Cookie 返回 401。
6. 带了无效的 `Authorization` 头、同时带有效 Cookie，返回 401。
7. `DELETE /api/tokens/current` 之后，这个令牌失效；只带 Cookie 调用这个接口返回 401。
8. `set_password` 之后，令牌和 Cookie 会话全部失效。
9. 滑动续期：把库里的 `expires_at` 改成 10 天后，请求一次后变成约 90 天后；改成已经过去的时间，请求返回 401。
10. 迁移：先用 v2 的表结构建库，插入一条 Cookie 会话；用新代码打开后，这条会话仍然有效，`kind` 为 `cookie`。
11. CORS：
    - 白名单来源的预检返回 204，带上述各个头；
    - 非白名单来源的预检返回 403，不带 `Access-Control-Allow-Origin`；
    - 白名单来源的 GET 带 `Access-Control-Allow-Origin` 和 `Vary`；
    - 白名单来源的 401 响应也带 `Access-Control-Allow-Origin`；
    - 不带 `Origin` 的请求没有 CORS 头；
    - `cors_origins` 为空时完全没有 CORS 头；
    - 所有响应都没有 `Access-Control-Allow-Credentials`。

### P1 验收

- `python3 -m unittest discover -s tests -v` 全部通过，原有 14 个测试一个都不改。
- 日志里记录下面这些命令的输出。用临时数据库和临时密码；令牌只保留前 6 位，其余打码。
  ```bash
  curl -sI http://127.0.0.1:8765/favicon.ico
  curl -s http://127.0.0.1:8765/api/meta
  curl -s -X POST -H 'Content-Type: application/json' -d '{"password":"<临时密码>","device_name":"curl"}' http://127.0.0.1:8765/api/tokens
  curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/trips
  curl -si -X OPTIONS -H 'Origin: https://localhost' -H 'Access-Control-Request-Method: POST' http://127.0.0.1:8765/api/trips
  curl -si -X OPTIONS -H 'Origin: https://evil.example' -H 'Access-Control-Request-Method: POST' http://127.0.0.1:8765/api/trips
  ```
- 附录 A 的 Web 回归清单全部通过。

**→ 审查点①**：按附录 C 准备材料，交给 Opus 审查。

## 5. P2 前端平台层（Web 行为不变）

只改 `static/`。这一阶段结束时，**Web 端的外观和行为与之前完全一样**；App 模式的代码在 P3 才能真正运行。

### P2.1 新增 `static/platform.js`

- 按 architecture.md 5.2 实现 `Platform`，Web 和 App 两种实现放在同一个文件里，以 `window.TravelNative` 是否存在来区分。
- App 模式的登录、退出、切换服务器流程严格按 architecture.md 第 4 节实现。存储键名为 `serverOrigin`、`authToken`。错误提示文字与该节一致。
- 在 `index.html` 里，于 `app.js` 之前加上：
  ```html
  <!-- native-bridge -->
  <script src="/platform.js"></script>
  ```
  其中 `<!-- native-bridge -->` 是标记，P3 的构建脚本会把它替换成 `native.js`。Web 端保留这行注释，不影响使用。

### P2.2 修改 `app.js`

- **`api()`**：
  - 请求地址为 `Platform.apiBase() + path`，合并 `Platform.authHeaders()`；
  - `credentials`：Web 用 `same-origin`，App 用 `omit`；
  - 用 `AbortController` 设 15 秒超时，超时抛出「连接超时，请检查网络」；
  - 收到 401 时（登录接口本身除外），先 `await Platform.onUnauthorized()`，再显示登录页。
- **登录页**：
  - 增加服务器地址输入框，只在 App 中显示：`type="url"`、`inputmode="url"`、`autocomplete="url"`，占位文字「https://你的服务器地址」；有保存的地址时预先填好。
  - 提交时调用 `Platform.signIn(server, password)`。
- **`boot()`**：
  - 先 `await Platform.init()`。
  - App 中没有令牌：直接显示登录页。
  - App 中网络出错：显示主界面，顶部出现一条提示「无法连接到服务器」和「重试」按钮，不清除令牌。
  - Web 端的行为保持不变。
- **菜单**：
  - App 中增加两行说明文字（不可点）：「服务器：<主机名>」「版本：<App 版本>」。
  - App 中增加「切换服务器」：先确认「退出登录并清除服务器地址？」，再调用 `Platform.forgetServer()`。
  - 「退出登录」改为调用 `Platform.signOut()`。
- **导出**：取到数据后调用 `Platform.saveFile(文件名, JSON 文本, "application/json")`。把现有的分享或下载逻辑原样移到 Web 实现里。
- **返回键**：用 `Platform.onBackButton()` 注册处理函数，依次检查：
  1. 有打开的对话框 → 关闭最上层的，返回 true；
  2. 图表提示框可见 → 隐藏，返回 true；
  3. 当前在看板页 → 切回记录页，返回 true；
  4. 以上都不是 → 返回 false，由原生侧退出 App。
- **容错**（architecture.md D7）：
  - 遇到不认识的 `transport`：卡片徽标显示原始值，套用 `.t-unknown`（灰色，用 `--muted`）；
  - 点开这种行程不打开编辑框，而是提示「这条记录需要新版 App 才能编辑」；
  - 看板各页签只统计认识的交通方式。
  - 编辑时如果行程的坐席不在本 App 的选项里，把它作为额外的一个选项显示并保持选中，保存时原样提交。

### P2.3 样式

新增 `.t-unknown`、登录页服务器地址栏、连接失败提示条的样式，沿用现有的设计变量。

### P2 验收

- `node --check static/platform.js`、`node --check static/app.js`、`node --check static/dashboard.js` 都通过。
- 附录 A 的 Web 回归清单全部通过（第 11 条包括 Network 面板中应用发出的请求只有同源请求）。
- 在日志里列出 `app.js` 中所有改动过的函数，并说明 Web 端的行为为什么不变。

## 6. P3 Capacitor 安卓工程

### P3.1 工程结构

```
mobile/
  package.json            # private；version 是 App 版本号的唯一来源，从 "1.0.0" 开始
  package-lock.json       # 必须提交
  capacitor.config.json   # 或 .ts，二选一
  src/native.js           # 原生桥，按 architecture.md 5.1 实现
  scripts/build-www.mjs   # 构建 www/（见 P3.3）
  assets/                 # 图标源文件（见 P3.5）
  android/                # npx cap add android 生成，提交到仓库
  www/                    # 构建产物，不提交
  dist/                   # 发布的 APK，不提交
```

- **依赖**：只允许 `@capacitor/core`、`@capacitor/cli`、`@capacitor/android`、`@capacitor/preferences`、`@capacitor/filesystem`、`@capacitor/share`、`@capacitor/app`、`@capacitor/status-bar`；开发依赖为 `esbuild`、`@capacitor/assets`。只有当键盘相关的验收项过不了时，才可以加 `@capacitor/keyboard`，并在日志中说明原因。
- 版本：所有 `@capacitor/*` 包用同一个大版本的最新稳定版，写**精确版本号**，不加 `^` 或 `~`。
- `npm` 脚本（名字固定）：

  | 脚本 | 作用 |
  |---|---|
  | `build:web` | 构建发布版 `www/` |
  | `build:web:debug` | 构建调试版 `www/` |
  | `sync` | `cap sync android` |
  | `android:open` | 用 Android Studio 打开工程 |
  | `build:android:debug` | 构建调试版 APK |
  | `release:android` | 构建发布版 APK，P4 实现 |

### P3.2 Capacitor 配置

- `appId`：用 architecture.md 第 7 节的值（默认 `com.travellog.app`，用户另有决定时以用户为准）；`appName`：「旅行记录」；`webDir`：`www`。
- **显式写出** `server.androidScheme: "https"`，不依赖默认值。启动 App 后在日志里记录 `location.origin` 的实际值，必须是 `https://localhost`。
- 要求系统 WebView 版本 ≥ 111（`color-mix()` 需要）。按当前 Capacitor 文档配置最低 WebView 版本，并在模拟器上验证版本不够时会出现提示。
- **调试版与发布版的区别**必须写得明明白白，而且发布版默认就是安全的：
  - 调试版：允许 `http://` 服务器，允许 WebView 远程调试，允许访问开发服务器 `10.0.2.2` 的明文流量。
  - 发布版：以上全部关闭。
  - 具体怎么实现（多份配置、构建参数等）由执行者决定，但要在日志中说明，并给出检查方法。
- 发布配置中不得出现 `server.url`。

### P3.3 构建脚本 `scripts/build-www.mjs`

只用 Node 内置模块和 esbuild。按以下顺序执行：

1. 清空 `www/`，把 `../static/` 整个复制过去。
2. 用 esbuild 把 `src/native.js` 打包成 `www/native.js`：
   - 格式 IIFE，目标 `chrome111`；
   - 发布版压缩代码；
   - 注入 `__DEBUG__`（调试版为 `true`）和 `__APP_VERSION__`（取 `package.json` 的 `version`）。
3. 把 `www/index.html` 中的 `<!-- native-bridge -->` 替换为 `<script src="/native.js"></script>`。标记必须恰好出现 1 次，否则报错退出。
4. 在 `<meta charset="utf-8">` 之后注入 CSP：
   ```html
   <meta http-equiv="Content-Security-Policy" content="default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self' https:; base-uri 'none'; form-action 'self'; object-src 'none'">
   ```
   调试版的 `connect-src` 再加上 `http:`。如果 Capacitor 的原生桥被这条 CSP 拦住，只能做最小限度的放宽，并在日志中说明放宽了哪一项、为什么。

### P3.4 原生桥 `src/native.js`

- 严格按 architecture.md 5.1 实现 `window.TravelNative`，不增不减。
- **`shareFile`**：用 Filesystem 把文件写到缓存目录，再用 Share 分享。
- **`onBackButton`**：监听 App 插件的 `backButton` 事件；处理函数返回 false 时退出 App，或者使用当前 Capacitor 版本提供的最小化方式。
- **状态栏**：跟随 `prefers-color-scheme`（同时监听变化），图标颜色要和背景形成对比。背景颜色：浅色 `#f2f2f7`，深色 `#000000`。

### P3.5 图标与启动画面

- 扩展 `tools/make_icons.py`（仍然只用标准库），生成 `mobile/assets/` 下 `@capacitor/assets` 需要的源文件：
  - 完整图标；
  - 自适应图标的前景：透明背景，列车图形落在安全区内；
  - 自适应图标的背景：现有的蓝色渐变；
  - 启动画面：浅色背景 `#f2f2f7`、深色背景 `#000000`，中间放图标，不写文字。
- 用 `npx @capacitor/assets generate --android` 生成安卓资源（具体参数以文档为准），把生成的资源提交到仓库。
- 现有 Web 图标的外观不变。

### P3.6 清单文件与网络安全

- 设置 `android:allowBackup="false"`，并配置数据提取规则（Android 12 及以上），云备份和设备迁移都排除全部数据。
- **发布版**：禁止明文流量，网络安全配置中设 `cleartextTrafficPermitted="false"`。
- **调试版**：在 `src/debug` 中覆盖网络安全配置，只允许 `10.0.2.2` 和 `localhost` 使用明文。
- **权限**：合并后的清单只应有 `INTERNET`。在日志里列出合并后清单中的全部权限；插件带进来的多余权限（如外部存储权限）要用 `tools:node="remove"` 去掉，并说明理由。
- 除了桌面图标的启动入口，不能有其他 intent filter。

### P3.7 演示数据（开发工具）

新增 `tools/seed_demo.py`，只用标准库，并通过 `server.Database` 和 `server.validate_trip` 写入数据：

- 往指定的数据库里写约 100 条覆盖各种情况的行程：五种交通方式、各种坐席、带里程和不带里程、两到三个地铁系统、多段换乘、跨天、跨年。
- 用法：`python3 tools/seed_demo.py --db /tmp/demo.db`。数据库不是空的时候拒绝执行，除非加上 `--force`。

### P3.8 运行与联调

- 开发服务器：
  ```bash
  python3 server.py set-password --db /tmp/demo.db
  python3 server.py serve --db /tmp/demo.db
  ```
  模拟器通过 `http://10.0.2.2:8765` 访问电脑上的 `127.0.0.1:8765`，服务器不需要改监听地址。
- 调试版 App 里的服务器地址填 `http://10.0.2.2:8765`。
- 截图保存到 `docs/screenshots/android/`（PNG，尽量小）。至少包括：
  - 登录页；
  - 记录列表，浅色和深色各一张；
  - 两段换乘的地铁编辑面板；
  - 看板的四个页签各一张；
  - 深色模式的看板一张。

### P3 验收

- 附录 B 中除第 14 条以外全部通过：在最新稳定 API 的模拟器上逐条测试，每条在日志中给出结论和证据（截图文件名，或命令输出）。
- 附录 A 的 Web 回归清单再跑一遍，确认通过（构建脚本不能改动 `static/` 本身）。
- 用 `npm ls --depth=0` 列出的依赖与 P3.1 的白名单一致。

**→ 审查点②**：P2 和 P3 一起交给 Opus 审查。

## 7. P4 签名、发布与文档

### P4.1 签名

- `android/app/build.gradle` 的 release 签名配置从 `mobile/android/keystore.properties`（不提交）读取 `storeFile`、`storePassword`、`keyAlias`、`keyPassword`。
- 这个文件不存在时，release 构建要**失败**并给出清楚的提示；不得退回去用调试签名。
- keystore 由用户按 `docs/android-release.md` 自己生成。**执行者不生成、不读取、不打印任何密钥或密码。**

### P4.2 版本号

- 版本号的唯一来源是 `mobile/package.json` 的 `version`（格式 `x.y.z`）。
- Gradle 中 `versionName` 等于这个版本号，`versionCode` = x × 10000 + y × 100 + z。
- 菜单中显示的 App 版本也来自这里（通过 `__APP_VERSION__`）。

### P4.3 发布脚本 `npm run release:android`

依次执行：

1. `build:web`（发布版）；
2. `cap sync android`；
3. `./gradlew assembleRelease`；
4. 把 APK 复制为 `mobile/dist/travel-log-<版本>.apk`，并生成同名的 `.sha256` 文件；
5. 打印签名证书的 SHA-256 指纹（用 `apksigner verify --print-certs`）。

### P4.4 文档 `docs/android-release.md`

内容包括：

- **一次性准备**：用户自己运行 `keytool` 生成 keystore，以及填写 `keystore.properties` 的方法。提醒用户：keystore 和密码必须备份到仓库以外的安全位置，丢失后无法再覆盖安装更新。
- **每次发布**：改版本号 → `npm run release:android` → 核对证书指纹 → 安装。
- **校验安装包**：`apksigner verify --print-certs` 的用法，并留一处位置记录首次发布时的证书指纹。
- **安装与升级**：`adb install -r`，或把 APK 传到手机上安装（需要在系统里允许安装未知来源的应用）。
- **出问题时**：手机丢失或怀疑令牌泄露，在服务器上执行 `python3 server.py set-password` 让所有设备下线。

另外在 README 中加一节「安卓 App」，链接到这份文档。

### P4 验收

- 附录 B 第 14 条通过；在真机上安装发布版 APK，附录 B 第 1 到 12 条抽查通过。
- `apkanalyzer manifest debuggable` 或同类工具确认发布版不可调试。
- 合并后清单中的权限只有 `INTERNET`，或者每一项多出来的权限都有理由。

**→ 审查点③**：Opus 终审。

---

## 附录 A　Web 回归清单

在电脑浏览器中，以手机宽度（约 375px）访问本地服务器。这些检查每个阶段都要跑。

1. **登录**：密码错误时提示「密码错误」；正确密码可以进入。
2. **新增高铁行程**：填坐席和里程，卡片上显示「车次 · 型号 · 坐席」和里程。
3. **车次推断**：在车次号里输入 `D301`，交通方式自动切到动车组。
4. **地铁两段换乘**：新增地铁系统、线路、车型；改动第 1 段的下车站，第 2 段的上车站跟着变；卡片上显示「换乘 1 次」。
5. **编辑和删除**都正常。
6. **筛选**：按交通方式筛选；选中地铁后按城市筛选。
7. **看板**：
   - 四个页签都能打开；
   - 切换年份；
   - 出行趋势的月、年视图都能显示，「全部 + 月视图」可以横向滑动；
   - 点击柱子会出现提示框；
   - 地铁页签里有站点排行、换乘站排行，线路按城市分组。
8. **导入导出**：导出 JSON 后再导入，提示的条数正确，列表数量翻倍。
9. **退出后重新登录**正常。
10. **深色模式**下外观正常。
11. **开发者工具**：Console 没有报错；Network 面板里，应用发出的请求只有同源请求。
    - 浏览器扩展产生的条目（如 `chrome-extension://` 资源和扩展自己的报错）不算。最好用没有安装扩展的浏览器配置来跑这一条。
    - 判断依据以服务器日志为准：日志里不能有 4xx/5xx，有意测试错误情况（如故意输错密码）产生的除外。

## 附录 B　安卓验收清单

1. **首次启动**显示登录页，有服务器地址栏。
2. **地址校验**：
   - 空地址或乱填 →「服务器地址无效」；
   - 发布版填 `http://` 地址 →「只支持 https:// 地址」；
   - 填一个能访问但不是旅行记录的网站 →「这不是旅行记录服务器」，并在该网站一侧确认密码没有被发送过去；
   - 服务器关闭 →「无法连接到服务器」；
   - 密码错误 →「密码错误」。
3. **登录成功**后，强制结束 App 再打开，直接进入主界面。
4. **主要功能**：在 App 中把附录 A 的第 2 到 8 条全部做一遍。
5. **导出和导入**：
   - 导出时弹出系统分享面板，可以保存到「文件」或发给别的应用；
   - 导入时能在系统文件选择器里选中刚才导出的文件，并导入成功。
6. **返回键**：
   - 编辑面板打开时按返回 → 面板关闭；
   - 在看板页按返回 → 回到记录页；
   - 在记录页按返回 → 离开 App。
7. **系统栏不遮挡内容**：手势导航和三键导航各测一次。状态栏、导航栏都不遮挡内容；底部标签栏、加号按钮、底部面板都在导航栏之上。
8. **键盘**：键盘弹出后，正在输入的输入框仍然可见，底部面板里靠下的「备注」也一样。
9. **深浅色切换**：切换系统深色、浅色模式后，界面和状态栏图标都正确，没有被系统自动反色。
10. **断网**：开飞行模式后打开 App，显示「无法连接到服务器」和重试按钮；恢复网络后重试成功，没有被登出。
11. **服务器改密码**：在服务器上执行 `set-password` 后，App 下一次请求会回到登录页，服务器地址仍然保留。
12. **菜单**：显示服务器地址和 App 版本；「切换服务器」后回到空白的登录页。
13. **WebView 版本**：在 WebView 版本低于要求的模拟器上（可选），出现版本过低的提示，而不是界面错乱。
14. **发布版检查**：
    - `chrome://inspect` 里看不到 App 的 WebView；
    - 无法使用 `http://` 服务器；
    - APK 签名校验通过，证书指纹与文档中记录的一致。

## 附录 C　交给 Opus 审查的材料

每个审查点都需要准备：

1. `git log --oneline main..<分支>` 和 `git diff --stat main..<分支>` 的输出。
2. 完整的 diff：`git diff main..<分支>`。安卓工程中模板生成的文件可以只列文件名。
3. `python3 -m unittest discover -s tests -v` 的完整输出。
4. `docs/android-log.md` 中本阶段的记录。
5. P3 和 P4 还需要：
   - `npm ls --depth=0` 的输出；
   - 合并后的 AndroidManifest（在 `android/app/build/intermediates/` 下）；
   - 截图目录的文件列表。

在 Claude Code 中审查时，也可以直接让 Opus 读取仓库和这个分支。

## 附录 D　已知的坑

- **WebView 不支持网页分享 API，也不能下载 blob 链接**：所以导出必须走 `Platform.saveFile`，再由原生桥分享。
- **跨源请求失败只表现为 `TypeError: Failed to fetch`**：要用调试版加 `chrome://inspect` 查看实际原因，通常是来源不在 CORS 白名单里，或者响应缺了 CORS 头。
- **混合内容**：App 页面的来源是 `https://localhost`，请求 `http://` 服务器会被当作混合内容拦截。调试版需要专门放开，发布版不要放开。
- **文件选择器**：`<input type="file" accept="application/json">` 在部分安卓文件选择器里会把 `.json` 文件过滤掉。如果选不到文件，再把 `accept` 放宽，并在日志中记录。
- **边到边显示**：Android 15 及以上强制边到边，旧版 WebView 的 `env(safe-area-inset-*)` 可能是 0。按当前 Capacitor 版本的官方方案处理，并用附录 B 第 7 条验证。
- **键盘遮挡**：边到边模式下，`adjustResize` 的表现会变，必须实测附录 B 第 8 条。
- **深色模式**：要确认 WebView 没有开启「算法变暗」，`prefers-color-scheme` 跟随系统。
- **WebView 版本**：`color-mix()` 需要 Chromium 111，`:has()` 需要 105，`dvh` 需要 108。
- **`datetime-local` 的值**：有的系统会带秒，现有代码已经截取前 16 个字符，不要删掉这段处理。
- **`confirm()` 对话框**：在 Capacitor 的 WebView 中可以正常弹出，暂时不需要换成原生对话框。
