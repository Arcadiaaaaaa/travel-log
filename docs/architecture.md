# 多端架构与决策

旅行记录要支持三个客户端：Web（现有的 PWA）、Android App、iOS App。三端都只和用户自己的服务器通信，数据只存在用户的服务器上。

本文记录已经做出的架构决策。执行者按这些决策实现，不要另起炉灶；认为某个决策有问题时，停下来说明理由，等待确认。

- 业务规则见 [`rules.md`](rules.md)，接口契约见 [`api/openapi.yaml`](api/openapi.yaml)。
- 安卓的分阶段任务见 [`android-plan.md`](android-plan.md)。

## 1. 总体结构

```
                 ┌────────────── 用户的服务器（HTTPS 反向代理） ──────────────┐
                 │   server.py（Python 标准库） ── SQLite（data/travel.db）     │
                 │     ├─ /         静态页面（Web 端用）                       │
                 │     └─ /api/*    JSON 接口                                  │
                 └──────────▲─────────────────────────────▲─────────────────┘
          同源请求 + Cookie 会话 │                             │ 跨源请求 + Bearer 令牌
                              │                             │ （CORS 白名单）
               ┌──────────────┴─────────┐   ┌───────────────┴──────────────────────┐
               │ Web / PWA（浏览器）       │   │ Android / iOS App（Capacitor）           │
               │ static/ 由服务器提供      │   │ static/ 打包进 App + native.js（原生桥） │
               │ 不加载任何第三方 JS       │   │ 页面来源 https://localhost（Android）     │
               └────────────────────────┘   │          capacitor://localhost（iOS）     │
                                            └────────────────────────────────────────┘
```

**三端共用同一份界面代码 `static/`。** App 只多一个很薄的原生桥 `native.js`，界面逻辑通过 `static/platform.js` 区分运行环境。以后新增功能只写一次。

## 2. 决策记录

### D1　App 用 Capacitor 打包同一份 `static/` 界面，界面文件打包在 App 内

- **理由**：三端界面只维护一份；看板图表、表单联动等复杂逻辑不用写三遍；以后做 iOS 只需 `cap add ios`。
- **放弃的方案**：
  - 原生界面（Kotlin Compose + SwiftUI）：界面要写三套，每加一个字段改三处。对个人工具来说维护成本不划算。
  - 让 App 远程加载服务器上的页面（Capacitor `server.url`、TWA）：效果和直接用 PWA 差不多；没网时连界面都打不开；服务器一旦被攻破，远程代码就能调用 App 的原生能力；而且 `server.url` 官方只建议开发时使用。
- **以后重新考虑的条件**：需要桌面小组件、深度系统集成，或 WebView 性能明显不够用。

### D2　App 用 Bearer 令牌登录，Web 继续用 Cookie

- **理由**：App 页面的来源是 `https://localhost` 或 `capacitor://localhost`，和服务器跨源，`SameSite=Strict` 的 Cookie 不会被发送。令牌需要客户端显式附加，不会被其他网站借用，所以天然不受 CSRF 影响。
- **规则**：见第 3 节。

### D3　服务器对 `/api/*` 开启 CORS 白名单，不允许携带凭据

- 默认白名单：`https://localhost`（Android）、`capacitor://localhost`（iOS），可以用环境变量 `TRAVEL_CORS_ORIGINS` 修改。
- 永远不返回 `Access-Control-Allow-Origin: *`，永远不返回 `Access-Control-Allow-Credentials`。
- Cookie 会话保持 `SameSite=Strict`，所以 CORS 不会给 Cookie 登录开口子；令牌登录本来就不依赖来源。

### D4　App 的服务器地址在登录页填写，只允许 HTTPS

- 用户第一次打开 App 时，在登录页填写服务器地址和密码。
- 地址只取「协议 + 域名 + 端口」，忽略路径。发布版只接受 `https://`；调试版额外允许 `http://`，方便连接电脑上的开发服务器。
- **先确认再发密码**：先请求 `GET /api/meta`，确认对方是旅行记录服务器且接口版本兼容，然后才发送密码。
- **这一步能防什么、不能防什么**：它能防止把地址误填成一个普通网站或不兼容的服务器时，密码被顺手发出去。但 `/api/meta` 的内容是对方自己报的，刻意伪造的恶意服务器同样能通过检查，所以**它不能证明服务器可信**。真正保证「连的是自己服务器」的，是 HTTPS 证书校验加上用户填对域名。界面和文档都不得把这一步说成身份验证。（P0 审查时由执行者指出，2026-10-19 补充。）

### D5　令牌和服务器地址存在 `@capacitor/preferences`，并禁用系统备份

- 存在 App 的私有存储里，受系统沙箱保护。Capacitor 官方不建议把重要数据放在 WebView 的 `localStorage` 里，因为系统可能会清理它。
- Android 关闭 `allowBackup`，并通过数据提取规则排除全部数据，避免令牌随备份离开手机。
- 没有选择 Keystore 加密存储：那需要第三方插件或自写原生代码，而按这个工具的威胁模型，沙箱加禁用备份已经足够。手机丢失时，在服务器上运行 `set-password` 就能让所有令牌失效。以后需要时，可以自写一个小插件升级为 Keystore 加密。

### D6　原生能力只经过一个薄桥 `window.TravelNative`

- `mobile/src/native.js` 只导入 Capacitor 官方插件，打包成 `native.js`，构建时注入到 App 的 `index.html`。它对页面暴露的接口见第 5 节。
- `static/` 里只有 `platform.js` 可以访问 `window.TravelNative`，`app.js` 和 `dashboard.js` 只调用 `Platform`。
- Web 端不加载 `native.js`，服务器提供的页面里仍然没有任何第三方 JS。

### D7　接口版本与兼容

- `GET /api/meta` 返回 `api_version`，目前为 `1`。
- 同一个 `api_version` 内，服务器只做向后兼容的新增：新增接口、新增响应字段、新增有默认值的可选请求字段。删除或改名字段、收紧校验、改变已有字段的含义，都必须把 `api_version` 升到 2。
- 安装包需要手动更新，所以 App 的版本常常落后于服务器。客户端必须忽略不认识的字段，遇到不认识的枚举值（如新的交通方式）要降级显示，不能崩溃。
- App 启动和登录时检查 `api_version`：
  - 比 App 支持的版本新：提示「服务器版本较新，请更新 App」。
  - 缺失或比 App 支持的版本旧：提示「服务器版本过旧，请先更新服务器」。
- 数据库结构只通过追加迁移函数修改（`MIGRATIONS` 列表），已有的迁移永远不改。

### D8　第一版 App 只做在线功能

- 没网时显示「无法连接到服务器」和重试按钮，不清除登录状态；只有服务器返回 401 时才回到登录页。
- 离线记录需要同步协议，包括客户端生成 ID、冲突处理、删除记录的同步，复杂度很高，列为后续可选阶段，见第 7 节。

### D9　分发方式：自签名 APK 侧载，不上架应用商店

- 签名用的 keystore 由用户生成和保管，不进仓库。keystore 一旦丢失，就无法覆盖安装更新，只能卸载重装。数据在服务器上，卸载重装后重新登录即可。
- 每次发布 APK 时附上 SHA-256 校验值，并在文档中记录签名证书指纹，便于核对安装包。

### D10　iOS 复用同一个 `mobile/` 工程

做完安卓后，在同一个工程里执行 `npx cap add ios`。iOS 的页面来源 `capacitor://localhost` 已经在 CORS 默认白名单里。iOS 的计划另写。

### D11　可选 Cloudflare Workers＋D1 部署（2026-10-26 用户授权）

- 原有 `server.py` 与本地 SQLite 部署继续保留；Cloudflare 使用 Python Worker 请求入口、D1 持久数据库，同一份 `static/`，API 与业务规则不变。
- 仅此部署适配允许官方 `workers-py`／运行时 SDK、Wrangler 及其构建工具依赖；版本在 `pyproject.toml`、`uv.lock`、`pylock.toml`、`package-lock.json` 锁定。原有 Python 服务仍然只用标准库。
- Python Worker 的 WASM 运行时缺少 `hashlib.pbkdf2_hmac`。用户另行授权仅 Cloudflare 适配使用 `cryptography`，采用 Pyodide 支持的精确版本；保持 PBKDF2-HMAC-SHA256、600000次、16字节随机盐、恒定时间比较和现有哈希格式，不自行降低参数。
- Worker临时文件系统不保存业务数据。D1使用 `cloudflare/migrations/` 中独立的追加式SQL迁移，原服务的 `MIGRATIONS` 及已有迁移不改。行程与区段写入、整批导入由D1事务保证原子性；内部批次关联字段不进入API响应。
- 生产密码哈希作为 `PASSWORD_HASH` Worker Secret；用户在本机交互终端输入密码，明文不离开本机。会话额外绑定密码版本指纹，修改Secret后旧Cookie和令牌即失效；D1只存会话令牌SHA-256。
- 登录失败计数保存在D1，跨Worker实例共用，不以进程内字典限流；只保存限流所需IP哈希及时间，不加统计或埋点。认证期限、CORS、安全头及Web行为继续按原契约。
- 只打包明确列出的运行模块及锁定依赖，静态目录原样上传；不上传本地数据库、虚拟环境、测试秘密或个人行程。配额不足时先报告，不降安全参数，不自行开通付费。

## 3. 认证规则

| | Web | App |
|---|---|---|
| 登录 | `POST /api/login` → 设置 Cookie `tl_session` | `POST /api/tokens` → 返回令牌 |
| 携带方式 | Cookie（HttpOnly、SameSite=Strict，HTTPS 下加 Secure） | 请求头 `Authorization: Bearer <令牌>` |
| 有效期 | 30 天，固定 | 90 天，滑动续期：每次成功使用后，若剩余有效期不足 89 天，就续到 90 天（每天最多写一次库） |
| 退出 | `POST /api/logout` | `DELETE /api/tokens/current` |

- **判定顺序**：请求带了 `Authorization` 头时，只按令牌判断，令牌无效就返回 401，**不会**再看 Cookie；没带这个头时才看 Cookie。
- **两种凭据互不通用**：Cookie 会话的值不能当令牌用，令牌也不能放进 Cookie 用。数据库里用 `kind` 字段区分。
- **服务器只存哈希**：数据库只存令牌的 SHA-256。令牌只能出现在请求头里，不能出现在 URL、日志、错误信息中。
- **登录限流**：`/api/login` 和 `/api/tokens` 共用失败计数，同一 IP 10 分钟内失败 5 次后，返回 429。
- **改密码会让所有会话失效**：执行 `server.py set-password` 后，所有 Cookie 会话和令牌一起失效。

## 4. App 的连接流程

1. **首次打开**（没有保存的服务器地址或令牌）：显示登录页，包括服务器地址和密码两栏。
2. **规范化地址**：去掉首尾空白；没写协议时补上 `https://`；用 URL 解析，只保留来源（origin）。地址无效时提示「服务器地址无效」；发布版填了 `http://` 时提示「只支持 https:// 地址」。
3. **确认服务器**：请求 `GET {来源}/api/meta`，超时 10 秒。
   - 连不上：提示「无法连接到服务器」。
   - 返回的不是 `{"app": "travel-log", ...}`：提示「这不是旅行记录服务器」。
   - 版本不兼容：按 D7 提示。
4. **获取令牌**：`POST /api/tokens`，请求体为 `{"password": ..., "device_name": "Android App <版本号>"}`。密码错误、限流等情况，直接显示服务器返回的 `error`。
5. **保存**：把服务器来源存为 `serverOrigin`，令牌存为 `authToken`，然后加载数据。
6. **之后每次打开**：已有令牌时直接进入主界面并加载数据。
   - 网络错误：显示错误和重试按钮，保留令牌。
   - 401：清除令牌，回到登录页，保留服务器地址。
7. **退出登录**：先尽量调用 `DELETE /api/tokens/current`（失败也继续），再清除本地令牌。
8. **切换服务器**：退出登录，同时清除保存的服务器地址。

所有接口请求设 15 秒超时，超时提示「连接超时，请检查网络」。

## 5. 接口定义

### 5.1 原生桥 `window.TravelNative`（只在 App 中存在）

```js
window.TravelNative = {
  platform: "android",          // 或 "ios"
  appVersion: "1.0.0",          // 来自 mobile/package.json 的 version
  allowInsecureServer: false,   // 只有调试版为 true，允许 http:// 服务器
  prefs: {
    get(key),                   // → Promise<string | null>
    set(key, value),            // value 为字符串 → Promise<void>
    remove(key),                // → Promise<void>
  },
  shareFile(filename, text, mimeType),  // 把文本写入缓存目录，再调起系统分享 → Promise<void>
  onBackButton(handler),        // 注册返回键处理；handler 返回 true 表示已处理，
                                // 返回 false 时由原生侧退出或最小化 App
};
```

- 状态栏颜色由 `native.js` 自己跟随 `prefers-color-scheme` 切换，页面不需要管。
- 新增桥接能力时，先在这里补充定义，再实现。

### 5.2 平台层 `Platform`（`static/platform.js`，在 `app.js` 之前加载）

```js
const Platform = {
  isNative,                   // 是否在 App 中
  name,                       // "web" | "android" | "ios"
  async init(),               // App：读取保存的服务器地址和令牌；Web：什么都不做
  apiBase(),                  // Web：""；App：保存的服务器来源
  authHeaders(),              // Web：{}；App：{ Authorization: "Bearer …" }（没有令牌时为 {}）
  hasCredentials(),           // Web：true（是否已登录由 /api/session 判断）；App：是否已有令牌
  serverLabel(),              // App：服务器的主机名；Web：""
  async signIn(server, password), // Web：POST /api/login（忽略 server）；App：第 4 节第 2 ~ 5 步
  async signOut(),            // Web：POST /api/logout；App：第 4 节第 7 步
  async forgetServer(),       // App：第 4 节第 8 步；Web：同 signOut
  async onUnauthorized(),     // App：清除令牌；Web：什么都不做
  async saveFile(filename, text, mimeType), // Web：现有的分享或下载逻辑；App：TravelNative.shareFile
  onBackButton(handler),      // App：转给 TravelNative；Web：什么都不做
};
```

## 6. 安全基线（所有客户端）

- **传输**：只走 HTTPS。App 发布版禁止明文流量和混合内容；调试版只对开发地址放开。
- **服务器**：保持现有措施，即 PBKDF2 密码哈希、登录限流、CSP 等安全响应头、Cookie 属性、只存令牌哈希。新增 CORS 时遵守 D3。
- **App 依赖**：只允许 `@capacitor/*` 官方包，加上构建期用的 `esbuild` 和 `@capacitor/assets`。依赖锁定精确版本，提交 lock 文件，用 `npm ci` 安装。新增依赖要先获得同意。
- **App 行为**：
  - 不集成任何统计、埋点、崩溃上报、广告或远程配置。
  - 只和用户填写的服务器通信，所有代码打包在安装包里，不从网络加载代码。
  - 发布版关闭 WebView 远程调试，关闭系统备份。
  - 发布配置里不使用 `server.url`。
  - 除桌面图标外不注册任何 intent filter 或深链接。
- **页面 CSP**：App 的 `index.html` 在构建时注入 `<meta>` CSP，与服务器下发的 CSP 保持同样的严格程度，只是 `connect-src` 允许 `https:`，调试版再加 `http:`。
- **秘密**：密码、令牌、keystore 及其密码永不提交、永不写进日志。

## 7. 未决事项

执行者先按默认值推进；用户随时可以改，但标注了截止时间的，必须在截止前定下来。

| 事项 | 默认值 | 截止时间 |
|---|---|---|
| Android 应用 ID（applicationId） | `com.travellog.app` | 安卓 P3 开始前。装过之后再改，就会变成另一个 App |
| 是否需要离线记录 | 第一版不做 | — |
| 是否需要「已登录设备」管理（查看、撤销令牌） | 第一版不做，靠 `set-password` 让全部令牌失效 | — |
| 没网时是否显示上次加载的数据（只读缓存） | 第一版不做 | — |
| 最低安卓版本 | 采用 Capacitor 模板的默认值，另外要求系统 WebView ≥ 111 | 安卓 P3 |
