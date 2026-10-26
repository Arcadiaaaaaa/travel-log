# 安卓开发日志

每个阶段结束时，由执行者按下面的模板在文件末尾追加一节。只写事实；凡是和计划不一致的地方，都必须写进「偏差」。

## 模板

```markdown
### Pn 阶段名称（分支 `android/pn-xxx`，YYYY-MM-DD）

**完成情况**（对应计划里该阶段的「验收」，逐条列出）
- [x] 验收项……（证据：测试名称、命令输出摘要或截图文件名）
- [ ] 未完成的项……（原因）

**偏差**（没有就写「无」）
- 计划要求……；实际做法……；原因……

**运行过的检查**
- `python3 -m unittest discover -s tests -v`：共 N 个测试，全部通过
- 附录 A Web 回归清单：通过（不通过的项写在这里）
- ……

**依赖变化**（从 P3 开始填写）
- 包名@精确版本：用途

**遗留问题和需要决定的事**
- ……
```

---

## 记录

### P0 仓库准备（分支 `android/p0-repo`，2026-10-19）

**状态**：仓库准备和检查记录已完成，提交供 Opus 审查。附录 A 第 11 项存在未通过的问题，**本阶段尚未满足完整验收**。用户已明确选择「保持 P0 范围，记录问题交审」，不应用额外修复，不进入 P1。

**完成情况**（对应 P0 验收）

- [x] 在项目根目录初始化 `main`，创建基线提交 `a7e6e21`（`chore: 初始提交`），共跟踪 22 个文件；随后建立 `android/p0-repo` 分支记录 P0 结果。
- [x] `.gitignore` 已追加计划中的全部 8 项：`.claude/launch.json`、`mobile/node_modules/`、`mobile/www/`、`mobile/dist/`、`mobile/android/keystore.properties`、`*.jks`、`*.keystore`、`.DS_Store`。按 P0 任务顺序，这些忽略规则包含在初始提交中。
- [x] `python3 -m unittest discover -s tests -v`：原有 14 个测试全部通过，未改动现有测试。
- [x] `git ls-files` 核对：没有数据库、`__pycache__`、`.claude/launch.json` 或签名文件；`git check-ignore` 的 10 个示例路径全部匹配忽略规则。
- [x] 基线提交后、写入本记录前，`git status --short --branch` 只有 `## android/p0-repo`，工作区干净。提交本记录后的状态另见交审材料中的命令输出。
- [ ] 附录 A 全部通过：实际为第 1～10 项通过，第 11 项未通过，原因和用户决定见下表及「偏差」。

**附录 A Web 回归逐项记录**

回归使用 `http://127.0.0.1:56866/`、375px 宽度、系统临时目录中的专用数据库和测试密码，未使用业务数据。交互检查于 2026-10-18 至 2026-10-19 执行；2026-10-19 重新运行接口测试和语法检查后整理本记录。

| 项目 | 结果 | 实际输入或观察证据 |
|---|---|---|
| 1. 登录 | 通过 | 错误密码显示「密码错误」；正确测试密码进入空列表。 |
| 2. 新增高铁 | 通过 | G1、CR400AF、二等座、553.50 元、1318.5 公里；卡片显示对应车次、车型、坐席、票价及里程。跨年行程从 2025-12-31 23:30 到 2026-01-01 01:00，显示「次日 01:00 · 1小时30分」。 |
| 3. 车次推断 | 通过 | 编辑上述行程，把 G1 改为 D301，交通方式自动切换为动车组，二等座保留；修改车型为 CRH2A 后保存成功。 |
| 4. 地铁换乘 | 通过 | 新增北京地铁的两段行程，新增第 2 段时上车站为复兴门；把第 1 段下车站改为建国门，第 2 段同步为建国门；保存后卡片显示西直门到国贸、2号线 → 1号线、换乘 1 次。 |
| 5. 编辑、删除 | 通过 | 编辑 D301 行程后列表反映修改；另建一条零票价临时公交，确认删除后行程数从 5 恢复为 4，提示「已删除」。 |
| 6. 筛选 | 通过 | 地铁筛选显示 2 条、9 元、55 分钟，并出现北京地铁和上海地铁城市选项；选北京后只显示其 1 条行程。 |
| 7. 看板 | 通过 | 总览、铁路、地铁、公交均显示对应数据；切换 2024、2025、2026 年及全部范围，月／年视图正常；全部月份图宽 590px、容器宽 323px，横向滚动位置发生变化；点击 2026 年 10 月柱子显示「地铁 1 次」。地铁常去站点不含建国门，换乘站排行显示建国门，线路按北京、上海分别分组。 |
| 8. 导入导出 | 通过 | 导出文件 `travel-log-20261018.json`，大小 2512 字节，`app=travel-log`、`version=1`、4 条行程；通过系统文件选择框导入此文件，提示「已导入 4 条」，列表从 4 条变成 8 条，金额从 564.50 元变成 1129 元。 |
| 9. 退出重登 | 通过 | 退出后等待并观察到只有密码框和登录按钮的登录页；重新登录后显示「全部 8」。 |
| 10. 深色模式 | 通过 | 目视核对记录页与总览看板，背景为黑色、卡片与文字可区分；DOM 实测页面宽 375px，背景 `rgb(0, 0, 0)`。截图：`/tmp/travel-p0-evidence/p0-dashboard-dark.jpg`。 |
| 11. Console／Network | **未通过** | Console 有两条 `/favicon.ico` 的 404 资源错误。Network 中应用的 HTTP 请求均指向 `127.0.0.1:56866`；另外可见已安装浏览器扩展注入的 `chrome-extension://` 资源。没有把含这些记录的 Console／Network 宣称为「无报错、只有同源请求」。证据：`/tmp/travel-p0-evidence/console-errors.txt`、`p0-console.png`。 |

**偏差**

- 附录 A 第 11 项未通过。直接请求确认 `/favicon.ico` 返回 404，现有 `/icons/icon-192.png` 返回 200、类型为 `image/png`。`serve_static()` 直接按文件路径查找，项目没有默认 favicon 文件或对应映射。
- 已准备但**未应用**最小修复提案：`/tmp/travel-p0-evidence/favicon-proposal.patch`，仅为默认 favicon 映射到现有图标，并新增一个测试。因超出 P0 文件范围，征询用户后，用户选择保留范围并记录交审；`server.py`、`static/`、`tests/` 均未修改。
- 内置浏览器的删除确认框阻塞自动化，改用 Chrome 验证删除。下载／文件选择事件等待也未可靠完成，导出改由系统下载记录和实际文件验证，导入改用系统文件选择框操作。没有把工具超时直接判为业务功能失败。
- 中断后临时服务已停止，恢复时从上述 4 条合成行程备份重建专用临时数据库，再完成导入和重登检查；没有写入项目的 `data/`。

**运行过的检查**

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`：2026-10-19 最后运行 14 项全部通过（6.686 秒），完整输出保存在 `/tmp/travel-p0-evidence/backend-tests.txt`，内容如下。

```text
test_v0_metro_rows_become_single_leg (test_server.MigrationTest.test_v0_metro_rows_become_single_leg) ... ok
test_change_password_revokes_sessions (test_server.ServerTest.test_change_password_revokes_sessions) ... ok
test_cookie_flags (test_server.ServerTest.test_cookie_flags) ... ok
test_crud (test_server.ServerTest.test_crud) ... ok
test_export_import_roundtrip (test_server.ServerTest.test_export_import_roundtrip) ... ok
test_legacy_metro_import (test_server.ServerTest.test_legacy_metro_import) ... ok
test_logout (test_server.ServerTest.test_logout) ... ok
test_metro_legs (test_server.ServerTest.test_metro_legs) ... ok
test_requires_json_content_type (test_server.ServerTest.test_requires_json_content_type) ... ok
test_requires_login (test_server.ServerTest.test_requires_login) ... ok
test_seat_and_distance (test_server.ServerTest.test_seat_and_distance) ... ok
test_static_files (test_server.ServerTest.test_static_files) ... ok
test_validation (test_server.ServerTest.test_validation) ... ok
test_wrong_password_and_rate_limit (test_server.ServerTest.test_wrong_password_and_rate_limit) ... ok

----------------------------------------------------------------------
Ran 14 tests in 6.686s

OK
```

- `node --check static/app.js`、`node --check static/dashboard.js`：均退出 0。
- `git diff --exit-code main -- server.py static tests docs/rules.md docs/architecture.md docs/api/openapi.yaml`：退出 0，确认业务代码、测试、规则和契约均与初始基线一致。
- `git ls-files -- data '*.db' '*.db-wal' '*.db-shm' .claude/launch.json ':(glob)**/__pycache__/**' '*.jks' '*.keystore'`：无输出。
- `git check-ignore`：`data/travel.db`、`__pycache__/server.cpython-314.pyc` 及计划新增的 8 类路径示例全部命中。
- 附录 A：10 项通过，1 项未通过；没有引入依赖，没有读取、生成或使用用户签名密钥。

**遗留问题和需要决定的事**

- 请 Opus 审查 favicon 404 及本次未完成完整验收的状态。按用户决定，本次只记录，不越过 P0 开始 P1。
- P3 开始前仍须重新核对开发工具。只读检查发现本机已有 Temurin JDK 25.0.3，与计划里「没有 Java」的历史描述不同；本阶段没有安装或改动开发工具。
- 后续认证审查需注意：`/api/meta` 的自报标识只能确认协议格式，恶意服务器也能伪造，不能据此证明服务器可信。此处只记录安全边界，没有更改既定架构。
- `/tmp/travel-p0-evidence/` 是本地临时审查材料，包含合成数据的截图和检查输出，不提交仓库，系统清理临时目录后需重建。

### P0 审查结论（Opus，2026-10-19）

**结论：通过。** 可以合并到 `main`，然后开始 P1。

**逐条核对**

- `git status`：在分支 `android/p0-repo`（`5fcb76c`）上复核，工作区干净。
- 测试：复跑 14 个，全部通过；`node --check` 检查两个脚本，均通过。
- `git ls-files`：没有数据库、`__pycache__`、`.claude/launch.json`，也没有签名文件。
- 基线提交 `a7e6e21` 正是执行者开始前的 22 个文件：
  - 所有业务代码文件的修改时间都早于 P0 开工，最晚的是 `static/dashboard.js`（2026-10-18 02:33）；
  - `.gitignore` 修改于 03:12，基线提交于 03:16；
  - P0 分支只新增了本日志。
- `.gitignore` 新增的 8 项与计划一致。

**附录 A 第 11 条**

- **复现**：在 Chromium 内核的浏览器里第二次打开页面时，服务器日志出现 `GET /favicon.ico 404`。页面已经声明了图标 `/icons/icon-192.png`，但浏览器仍会请求默认的 `/favicon.ico`。这个问题从第一版就有，与 P0 无关，不算 P0 引入的回归。
- **处理**：
  - 修复放进 P1，计划新增了 P1.0，可以直接用准备好的补丁。
  - 附录 A 第 11 条补充了说明：浏览器扩展产生的条目不算，以服务器日志为准。
- **评价**：执行者如实记录了未通过项，没有越出 P0 的范围改代码，并先征求了用户意见，做法正确。

**执行者提出的两点**

- **JDK**：说法正确。本机装有 Temurin JDK 25.0.3，我之前的检查在沙箱里没有找到它。计划第 2 节已更正，并写明构建安卓工程用 Android Studio 自带的 JDK，不用 JDK 25。
- **`/api/meta` 的信任边界**：说法正确。architecture.md 的 D4 已补充说明：这一步只能防止误填地址，不能证明服务器可信；真正保证身份的是 HTTPS 证书校验和填对域名。既定流程不变。

**对 P1 的提醒**

- 先做 P1.0（favicon），单独提交。
- 只改计划列出的文件；`docs/api/openapi.yaml` 只允许删除已实现项上的 `x-status: planned`。
- 交审时附上附录 C 要求的材料。证据要么直接贴进日志，要么放在仓库外不会被自动清理的位置，因为 `/tmp` 会被系统清理。

### P1 服务器元信息、令牌认证与 CORS（分支 `android/p1-server-auth`，2026-10-26）

**状态**：P1.0～P1.7 已实现，49 项后端测试及六条 curl 演示通过；附录 A 的 11 项均通过。第 11 项按用户于 2026-10-26 确认的口径，排除两条 Chrome DevTools 自动探测 404，完整保留原始证据。P1 执行与验收已完成，提交供 Opus 审查，未开始 P2。

**完成情况**（对应 P1 计划和验收）

- [x] 从 `main` 的 `16b9fb34b0ef4158e718e42f4c0bebd94200fe3a` 新建 `android/p1-server-auth`；实现按 P1.0～P1.7 顺序推进。
- [x] P1.0：`/favicon.ico` 映射到现有 `icons/icon-192.png`，返回 200、`image/png`，未新增图标文件或 MIME 类型；`test_favicon` 核对字节完全相同。独立提交 `c691921`（`fix: 为 /favicon.ico 返回应用图标`）。
- [x] P1.1：`SERVER_VERSION="1.0.0"`、`API_VERSION=1`；未登录读取 `/api/meta` 返回恰好三个约定字段（`test_meta`、下方 curl 输出）。
- [x] P1.2：只在 `MIGRATIONS` 末尾追加 `migrate_v3`，新增四列及规定默认值；v2 Cookie 会话的值和有效期不变，再次打开不重复迁移（`test_v2_cookie_session_survives_v3`）。`migrate_v1`、`migrate_v2` 的 AST 与 main 完全一致。
- [x] P1.3：签发 201、`Bearer`、`expires_in=7776000`、没有 `Set-Cookie`；设备名默认空、去首尾空白、限制 50 字，非文本及过长按契约报 400；凭据由 `secrets.token_urlsafe(32)` 生成，数据库只有 SHA-256。撤销只影响当前令牌，Cookie 调用撤销接口返回 401（对应测试见下表）。
- [x] P1.4：`Authorization` 存在时只判断令牌，空值、错误格式、重复头或无效令牌均不回退 Cookie；`kind` 隔离两种凭据；Cookie 30 天固定有效期，令牌不足 89 天时续为 90 天，并更新 `last_used_at`。固定时钟及六路并发测试验证每轮只写一次库；过期令牌不续期。Web 登录与 App 登录共享失败计数，改密码撤销两类会话。
- [x] P1.5：只对 `/api/*` 的精确白名单来源返回 `Access-Control-Allow-Origin` 与 `Vary: Origin`；默认 Android/iOS 两来源，可设为空关闭。预检 204／403、静态路径 OPTIONS 405、400／401／404／413／415／429／500／501／503 等响应均有对应覆盖；从不输出 `*` 或 `Access-Control-Allow-Credentials`。
- [x] P1.6：README 增加 `TRAVEL_CORS_ORIGINS` 及认证说明；OpenAPI 仅删除三个接口和 bearerAuth 上四行 `x-status: planned`，文本对比确认无其他契约改动。
- [x] P1.7：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`：49 项全部通过（29.374 秒）；原有 14 个测试方法 AST 完全相同，仅新增 35 个，辅助 `request()` 增加请求头支持。
- [x] 六条 curl 演示：200／200／201／200／204／403，原始响应头和脱敏响应体见下方。实际运行命令行 `set-password` 后，原 Cookie 和 Bearer 请求均返回 401；测试只用临时数据库和临时密码，未记录密码，令牌仅保留前 6 位。
- [x] 本阶段证据按模板写入本日志；附录 C 材料保存在持久交审目录，验收例外及用户确认如实列出。
- [x] 附录 A 全部 11 项通过：第 11 项按用户确认排除两条 Chrome DevTools 非应用探测 404，完整原始日志保留，详见下表和「偏差」。

**P1.7 测试主题与证据**

| 计划主题 | 直接证据（测试名称或实际结果） |
|---|---|
| 1. 公开元信息 | `test_meta`：状态 200，响应恰好为 app、api_version、server_version。 |
| 2. 签发及访问 | `test_token_issuance`、`test_token_authenticates_trips_and_session`：201、Bearer、90 天、无 Cookie，令牌可访问 trips/session；库中查到哈希并确认没有明文令牌。 |
| 3. 设备名 | `test_token_device_name_defaults_to_empty`、`test_token_device_name_validation`：省略为空；null、数字、布尔、列表、对象报「设备名称必须是文本」；51 字报「设备名称最多 50 个字」；去空白后的 50 字可签发。 |
| 4. 共享限流 | `test_token_wrong_password_shares_login_limit`、`test_token_login_limit_is_shared_in_reverse`：两方向失败 5 次后另一接口也返回 429；JSON 类型、未设密码另有测试。 |
| 5. kind 隔离 | `test_token_and_cookie_cannot_be_interchanged`：Cookie 当 Bearer、Bearer 放 Cookie 均 401。 |
| 6. 不回退 Cookie | `test_authorization_never_falls_back_to_cookie`、`test_authorization_duplicate_headers_are_rejected`、`test_token_rejects_malformed_bearer_with_valid_cookie`：有效 Cookie 不掩盖无效 Authorization；session 返回 authenticated=false。 |
| 7. 撤销 | `test_token_revocation`、`test_token_revocation_rejects_cookie`、`test_token_revocation_does_not_revoke_other_sessions`：当前令牌失效，其他令牌和 Cookie 继续有效。 |
| 8. 改密码 | `test_token_and_cookie_revoked_by_password_change`，以及 `verify_http.py` 的实际 CLI 检查：两类旧凭据均 401。 |
| 9. 有效期与续期 | `test_token_renews_only_when_below_89_days`：10 天续为 90 天，同一时刻及恰好一天后不重复写；超过一天写一次。`test_token_renewal_is_atomic`：六路请求全 200，仅一次更新。`test_token_expired_is_not_renewed`、`test_cookie_lifetime_remains_fixed`：过期 401、不续期；Cookie 固定 2592000 秒。 |
| 10. 迁移 | `test_v2_cookie_session_survives_v3`：v2 会话升级后 kind=cookie、旧有效期不变，新列默认值正确，user_version=3，重开仍只有一条会话。 |
| 11. CORS | `test_cors_preflight_allowed_origins`、`test_cors_preflight_rejects_other_origins`、`test_cors_success_and_error_responses`、`test_cors_empty_and_custom_configuration`、`test_cors_environment_configuration` 等：逐项验证预检、错误响应、无 Origin、空／自定义配置、静态路径、禁止凭据头和通配符；`test_cors_state_resets_on_keep_alive_connection` 验证不串到静态响应。 |

**附录 A Web 回归逐项记录**

2026-10-26 在 Chrome 的专用测试标签访问 `http://127.0.0.1:8765/`，使用系统临时目录中的专用数据库。校正本地站点缩放后，DOM 实测 `innerWidth=375`、`bodyWidth=375`、`innerHeight=812`（`viewport.json`）；在该宽度重新核对高铁显示、D301 推断、换乘联动及筛选。截图、导出文件、原始请求日志及核对结果均放在 `/Users/niuniu/Documents/travel-log-review/p1/`，未放在 `/tmp`，未使用业务数据库。

| 项目 | 结果 | 实际观察证据 |
|---|---|---|
| 1. 登录 | 通过 | 故意输入错误的临时密码显示「密码错误」；正确测试密码进入空列表。服务器仅有一条预期的 `/api/login` 401。 |
| 2. 新增高铁 | 通过 | G1、CR400AF、二等座、553.50 元、1318.5 公里；卡片显示「G1 · CR400AF · 二等座」及「1,318.5公里」。跨年行程显示次日 01:00、1小时30分；`01-high-speed-375.jpg`。 |
| 3. 车次推断 | 通过 | G1 改成 D301 后，动车组 radio.checked=true，二等座保留；修改车型 CRH2A 后保存成功。 |
| 4. 地铁换乘 | 通过 | 新增北京地铁、2号线／1号线及 6B；第二段上车站先为复兴门，第一段下车站改为建国门后第二段同步为建国门；卡片显示「换乘 1 次」。`metro-linkage.txt`、`02-metro-transfer-375.jpg`。另建上海地铁 2号线 8A 作为城市对照。 |
| 5. 编辑、删除 | 通过 | 编辑后卡片显示 D301／CRH2A；新增零票价临时公交，使用 Chrome 原生确认按钮删除，提示「已删除」，5 条恢复为 4 条。原始日志有 `DELETE /api/trips/5 200`。 |
| 6. 筛选 | 通过 | 地铁筛选为 2 条、9 元、55 分钟；选北京地铁后只显示 1 条、5 元、40 分钟。导入后在准确 375px 下再次核对北京筛选为 2 条、10 元。 |
| 7. 看板 | 通过 | 总览 4 条／564.50 元，铁路 1 条／553.50 元，地铁 2 条／9 元，公交 1 条／2 元；2024、2025、2026 年分别为 1、1、2 条。月／年图正常；全部月图 scrollWidth=590、clientWidth=323，原生横向滚动后 scrollLeft 从 267 变为 133.5。点 2026 年 10 月柱子提示地铁 1 次。常去站点仅端点，换乘站为建国门，线路按北京／上海分组。`03-trend-375.jpg`、`metro-rankings.txt`、`metro-transfer-rankings.txt`。 |
| 8. 导入导出 | 通过 | 实际下载 `travel-log-20261026.json`（2512 字节、app=travel-log、version=1、4 条）；确认框显示追加 4 条，导入后提示「已导入 4 条」，列表 4→8，花费 564.50→1129 元，时长 2.9→5.8 小时。`export-check.json`、`04-import-375.jpg`、`import-result.txt`。 |
| 9. 退出重登 | 通过 | 退出后等待密码框出现，确认只有登录页；重新登录显示「全部 8」，金额和时长保留。检查结束时再次退出并关闭专用标签。 |
| 10. 深色模式 | 通过 | DevTools 临时模拟深色；DOM 背景 rgb(0,0,0)、文字 rgb(242,242,247)、页面宽 375px，目视看板和记录页正常。`05-dashboard-dark-375.jpg`、`06-records-dark-375.jpg`。完成后关闭 DevTools、恢复站点原有 125% 缩放并重置临时视口。 |
| 11. Console／Network／服务器日志 | 通过（用户确认例外） | Console 初始唯一应用错误为故意输错密码的 401；重载后显示「控制台中有 0 条消息」。Network 的应用请求全部同源且成功，favicon 三次 GET 都是 200；扩展资源另列。原始 Web 日志共 56 个请求：48 个 200、5 个 201、1 个故意触发的 401，另有 Chrome DevTools 自动发现请求产生的 2 个 404。用户于 2026-10-26 明确回复「允许排除，保留原始证据」，本轮据此排除这两条非应用探测请求，原始日志未删改；`console-errors-before-reload.txt`、`console-after-reload.txt`、`network-after-reload.txt`、`web-server.log`、`web-log-audit.json`。 |

**偏差**

- 业务规则、接口契约和架构无变更；没有修改静态界面，也没有开始 P2。日志更新按本任务和 AGENTS.md 的阶段记录要求执行。
- P1.5 补充覆盖 Python 内置处理器返回的 501：先新增测试复现缺少 CORS 头，再把加头逻辑统一放入 `end_headers()`；单项由失败变为通过，最终完整 49 项通过。状态码和静态路径行为保持原样；证据 `p1.5-501-red.txt`、`backend-tests.txt`。
- 上一轮因删除确认框阻塞而暂停；本轮恢复时旧标签和临时服务均已关闭，因此新建临时数据库完整重跑回归。删除与导入确认使用 Chrome 原生按钮，导入使用系统文件选择框，下载按实际文件核验，没有依赖此前超时的事件等待。
- 浏览器沿用该本地站点的 125% 缩放，开始时实际 CSS 宽度小于目标；本轮已临时改为 100%，确认 375px，并在该宽度复核关键表单、显示和筛选，结束后恢复 125%。
- 第 11 项遇到 Chrome DevTools 自动工作区探测：官方文档说明打开开发者工具检查本地网站时会请求 `/.well-known/appspecific/com.chrome.devtools.json`，未提供时的 404 可以忽略（[Chrome 官方说明](https://developer.chrome.com/docs/devtools/automatic-workspaces)）。现有计划只明确排除浏览器扩展，因此先询问验收口径；用户于 2026-10-26 明确回复「允许排除，保留原始证据」。本轮仅将这两条指定路径的 404 作为非应用请求排除，原始日志完整保留；没有新增服务器端点、过滤原始日志或改动浏览器 flags。

**运行过的检查**

- 2026-10-26：`PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`，49 项通过（29.374 秒），完整输出见下方及 `backend-tests.txt`。
- `node --check static/app.js`、`node --check static/dashboard.js`：退出 0。
- `audit_scope.py`：原有 14 个测试、旧迁移、安全相关常量和函数 AST 核对通过；OpenAPI 仅四行计划标记删除；Web 静态代码、规则、架构、计划、AGENTS.md 与 main 一致；累计改动在白名单中；没有数据库、缓存或签名文件被跟踪。
- `git diff --check main`：退出 0。
- `verify_http.py`：实际 curl 和 CLI 检查均通过，响应见下方；专用服务停止，临时数据库已清理。
- 附录 A：11 项全部通过；第 11 项包含上述用户确认的两条非应用 DevTools 探测例外。原始日志完整保留。
- 后端仍只使用 Python 标准库，依赖未增加；没有读取、生成或使用用户签名密钥。

**完整后端测试输出**

```text
test_v0_metro_rows_become_single_leg (test_server.MigrationTest.test_v0_metro_rows_become_single_leg) ... ok
test_v2_cookie_session_survives_v3 (test_server.MigrationTest.test_v2_cookie_session_survives_v3) ... ok
test_authorization_duplicate_headers_are_rejected (test_server.ServerTest.test_authorization_duplicate_headers_are_rejected) ... ok
test_authorization_never_falls_back_to_cookie (test_server.ServerTest.test_authorization_never_falls_back_to_cookie) ... ok
test_change_password_revokes_sessions (test_server.ServerTest.test_change_password_revokes_sessions) ... ok
test_cookie_flags (test_server.ServerTest.test_cookie_flags) ... ok
test_cookie_lifetime_remains_fixed (test_server.ServerTest.test_cookie_lifetime_remains_fixed) ... ok
test_cors_absent_for_no_origin_and_static (test_server.ServerTest.test_cors_absent_for_no_origin_and_static) ... ok
test_cors_empty_and_custom_configuration (test_server.ServerTest.test_cors_empty_and_custom_configuration) ... ok
test_cors_environment_configuration (test_server.ServerTest.test_cors_environment_configuration) ... ok
test_cors_never_allows_wildcard (test_server.ServerTest.test_cors_never_allows_wildcard) ... ok
test_cors_password_not_configured (test_server.ServerTest.test_cors_password_not_configured) ... ok
test_cors_preflight_allowed_origins (test_server.ServerTest.test_cors_preflight_allowed_origins) ... ok
test_cors_preflight_does_not_apply_to_static (test_server.ServerTest.test_cors_preflight_does_not_apply_to_static) ... ok
test_cors_preflight_rejects_other_origins (test_server.ServerTest.test_cors_preflight_rejects_other_origins) ... ok
test_cors_state_resets_on_keep_alive_connection (test_server.ServerTest.test_cors_state_resets_on_keep_alive_connection) ... ok
test_cors_success_and_error_responses (test_server.ServerTest.test_cors_success_and_error_responses) ... ok
test_cors_token_login_response (test_server.ServerTest.test_cors_token_login_response) ... ok
test_cors_unsupported_method_response (test_server.ServerTest.test_cors_unsupported_method_response) ... ok
test_crud (test_server.ServerTest.test_crud) ... ok
test_export_import_roundtrip (test_server.ServerTest.test_export_import_roundtrip) ... ok
test_favicon (test_server.ServerTest.test_favicon) ... ok
test_legacy_metro_import (test_server.ServerTest.test_legacy_metro_import) ... ok
test_logout (test_server.ServerTest.test_logout) ... ok
test_meta (test_server.ServerTest.test_meta) ... ok
test_metro_legs (test_server.ServerTest.test_metro_legs) ... ok
test_requires_json_content_type (test_server.ServerTest.test_requires_json_content_type) ... ok
test_requires_login (test_server.ServerTest.test_requires_login) ... ok
test_seat_and_distance (test_server.ServerTest.test_seat_and_distance) ... ok
test_static_files (test_server.ServerTest.test_static_files) ... ok
test_token_and_cookie_cannot_be_interchanged (test_server.ServerTest.test_token_and_cookie_cannot_be_interchanged) ... ok
test_token_and_cookie_revoked_by_password_change (test_server.ServerTest.test_token_and_cookie_revoked_by_password_change) ... ok
test_token_authenticates_trips_and_session (test_server.ServerTest.test_token_authenticates_trips_and_session) ... ok
test_token_device_name_defaults_to_empty (test_server.ServerTest.test_token_device_name_defaults_to_empty) ... ok
test_token_device_name_validation (test_server.ServerTest.test_token_device_name_validation) ... ok
test_token_expired_is_not_renewed (test_server.ServerTest.test_token_expired_is_not_renewed) ... ok
test_token_issuance (test_server.ServerTest.test_token_issuance) ... ok
test_token_login_limit_is_shared_in_reverse (test_server.ServerTest.test_token_login_limit_is_shared_in_reverse) ... ok
test_token_rejects_malformed_bearer_with_valid_cookie (test_server.ServerTest.test_token_rejects_malformed_bearer_with_valid_cookie) ... ok
test_token_renewal_is_atomic (test_server.ServerTest.test_token_renewal_is_atomic) ... ok
test_token_renews_only_when_below_89_days (test_server.ServerTest.test_token_renews_only_when_below_89_days) ... ok
test_token_requires_configured_password (test_server.ServerTest.test_token_requires_configured_password) ... ok
test_token_requires_json (test_server.ServerTest.test_token_requires_json) ... ok
test_token_revocation (test_server.ServerTest.test_token_revocation) ... ok
test_token_revocation_does_not_revoke_other_sessions (test_server.ServerTest.test_token_revocation_does_not_revoke_other_sessions) ... ok
test_token_revocation_rejects_cookie (test_server.ServerTest.test_token_revocation_rejects_cookie) ... ok
test_token_wrong_password_shares_login_limit (test_server.ServerTest.test_token_wrong_password_shares_login_limit) ... ok
test_validation (test_server.ServerTest.test_validation) ... ok
test_wrong_password_and_rate_limit (test_server.ServerTest.test_wrong_password_and_rate_limit) ... ok

----------------------------------------------------------------------
Ran 49 tests in 29.374s

OK

```

**六条 curl 演示与实际 CLI 失效检查**

以下为实际响应；为便于验收同时保留了响应头，密码用占位符，令牌仅展示前 6 位。脚本将请求密码和令牌通过 curl 标准输入配置传入，不写入 URL 或持久请求文件。与故意测试 403／401 的 curl 请求对应的日志单独保存在 `curl-server.log`，未与 Web 回归日志混用。

```text
curl -sI http://127.0.0.1:8765/favicon.ico
HTTP/1.1 200 OK
Server: TravelLog/1.0
Date: Sun, 25 Oct 2026 16:23:43 GMT
Content-Type: image/png
Content-Length: 2222
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-cache

curl -s http://127.0.0.1:8765/api/meta
HTTP/1.1 200 OK
Server: TravelLog/1.0
Date: Sun, 25 Oct 2026 16:23:43 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 66
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"app": "travel-log", "api_version": 1, "server_version": "1.0.0"}

curl -s -X POST -H "Content-Type: application/json" -d '{"password":"<临时密码>","device_name":"curl"}' http://127.0.0.1:8765/api/tokens
HTTP/1.1 201 Created
Server: TravelLog/1.0
Date: Sun, 25 Oct 2026 16:23:43 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 103
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"token": "YH9M86[其余隐藏]", "token_type": "Bearer", "expires_in": 7776000}

curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/trips
HTTP/1.1 200 OK
Server: TravelLog/1.0
Date: Sun, 25 Oct 2026 16:23:43 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 13
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"trips": []}

curl -si -X OPTIONS -H "Origin: https://localhost" -H "Access-Control-Request-Method: POST" http://127.0.0.1:8765/api/trips
HTTP/1.1 204 No Content
Server: TravelLog/1.0
Date: Sun, 25 Oct 2026 16:23:43 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 0
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 600
Access-Control-Allow-Origin: https://localhost
Vary: Origin

curl -si -X OPTIONS -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST" http://127.0.0.1:8765/api/trips
HTTP/1.1 403 Forbidden
Server: TravelLog/1.0
Date: Sun, 25 Oct 2026 16:23:43 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 31
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"error": "来源不被允许"}

额外命令行验证：实际执行 set-password 后，原 Cookie 和 Bearer 请求均返回 401。临时密码未记录。

```

**遗留问题和需要决定的事**

- 验收口径已确认，没有待决定的实现问题；正式代码审查仍按项目分工交给 Opus。
- 实现提交为 `c691921`、`dbd66d2`；此前日志提交为 `4041dde`，本次补记用户确认和最终验收结论。
- 交审目录：`/Users/niuniu/Documents/travel-log-review/p1/`。附录 C 的提交列表、统计、完整 diff、完整测试输出及本阶段记录均在该目录；材料随本次日志提交刷新。未合并 main，未开始 P2。

**验收口径确认（2026-10-26）**

- 用户明确回复「允许排除，保留原始证据」。该确认适用于本轮第 11 项中 `GET /.well-known/appspecific/com.chrome.devtools.json` 的两条 404。
- `web-server.log` 的全部 56 条请求保持原样：48 个 200、5 个 201、1 个故意输错密码产生的 401，以及上述 2 个 DevTools 探测 404。`web-log-audit.json` 明列原始错误与用户确认的例外，没有删除或掩盖记录。
- 本次仅更新验收记录和交审材料；服务端、测试、README、接口文件均与已通过 49 项测试的 `dbd66d2` 内容一致。P1 在此停下，等待 Opus 审查。

### P1 验收材料补齐（分支 `android/p1-server-auth`，2026-10-26）

**状态**：用户已确认 P1 代码通过 Opus 审查。本次仅重新执行验收并补充材料；服务器、测试、README、接口契约及前端均不改，停在 P1。

**完成情况**（对应本次要求及第 4 节「P1 验收」）

- [x] 重新运行计划中的全部六条 curl：favicon 200、meta 200、令牌签发 201、Bearer 读取行程 200、白名单预检 204、非白名单预检 403。完整响应输出贴在下方；本次专用临时数据库与 Web 回归库相互独立，临时密码未记录，令牌只显示前 6 位。
- [x] 附录 A 的全部 11 条 Web 回归重新执行，逐条证据见下表。第 11 条以本轮完整 `web-server.log` 为准：共 50 个请求，42 个 200、5 个 201、1 个故意输错密码的 401；另有 2 个 Chrome DevTools 非应用探测 404，按本对话已经确认的例外单列并保留。
- [x] 后端全量测试重新运行，49 项全部通过（26.663 秒），没有修改现有测试；完整输出为本轮目录的 `backend-tests.txt`。
- [x] 截图、导出 JSON、原始服务器日志、Console／Network 观察及核对结果保存在 `/Users/niuniu/Documents/travel-log-review/p1/acceptance-20261026-101501/`，不覆盖之前的交审材料。
- [x] 本记录在既有日志末尾追加，已有记录逐字保留；本次单独以 `docs:` 提交。相对开始验收时的 `ee75a4d53ca867087e4d3e4b9932b079924c9eb6`，仓库仅允许本日志发生变化。

**附录 A Web 回归逐项证据**

使用 Chrome 专用测试标签、临时数据库和测试密码。开始前将该站点缩放临时调整为 100%，实测 `innerWidth=375`、`bodyWidth=375`、`innerHeight=812`（`viewport.json`），全部交互都在该宽度执行；结束后恢复原有 125% 缩放并重置视口。

| 项目 | 结果 | 本轮实际输入、观察和证据 |
|---|---|---|
| 1. 登录 | 通过 | 故意输错密码，提示「密码错误」；正确临时密码进入空列表。日志只有 1 条与此对应的 `/api/login` 401。 |
| 2. 新增高铁 | 通过 | G1、CR400AF、二等座、553.50 元、1318.5 公里；卡片显示车次、车型、坐席及「1,318.5公里」。跨年行程 2025-12-31 23:30→2026-01-01 01:00 显示「次日 01:00 · 1小时30分」。截图 `01-high-speed.jpg`。 |
| 3. 车次推断 | 通过 | G1 改为 D301 后，动车组 radio.checked=true，二等座仍为 true；车型改为 CRH2A 后保存，卡片实际更新为「D301 · CRH2A · 二等座」。 |
| 4. 地铁两段换乘 | 通过 | 新增北京地铁、2号线和1号线、6B 车型；新增第 2 段时上车站为复兴门，第 1 段下车站改为建国门后，第 2 段同步为建国门；保存卡片显示「换乘 1 次」。`metro-linkage.txt`、`02-metro-transfer.jpg`。另新增上海地铁2号线8A，为城市筛选提供对照。 |
| 5. 编辑和删除 | 通过 | 上述高铁编辑后显示 D301／CRH2A；另建零票价临时公交，用原生确认框确认删除后提示「已删除」，5 条恢复到 4 条。服务器日志 `DELETE /api/trips/5 200`。 |
| 6. 筛选 | 通过 | 地铁筛选显示 2 条／9 元／55 分钟；再选北京地铁，只有 1 条／5 元／40 分钟，卡片为西直门→国贸。 |
| 7. 看板 | 通过 | 总览4条564.50元、铁路1条553.50元、公交1条2元、地铁2条9元。切换2024／2025／2026年，分别1／1／2条。年图显示2024～2026；全部月图宽590px、容器323px，原生横向滑动使scrollLeft从267变为133.5；点2026年10月柱子提示「地铁 1 次」。常去站点仅起终点，换乘站排行为建国门，线路按北京／上海分组。`year-summaries.json`、`tab-summaries.json`、`trend-scroll.json`、`03-trend.jpg`、`metro-rankings.txt`、`metro-transfer-ranking.txt`。 |
| 8. 导入导出 | 通过 | 实际导出的4条记录下载为 `travel-log-20261026 (1).json`，2503字节；app=travel-log、version=1、金额合计56450分。系统文件选择框选取该新文件，确认框显示追加4条，导入后提示「已导入 4 条」，列表4→8、花费564.50→1129元、时长2.9→5.8小时。`exported-trips.json`、`export-check.json`、`import-result.txt`、`04-import.jpg`。 |
| 9. 退出重登 | 通过 | 退出后等待并观察到密码框与登录按钮；重新登录后仍显示8条、1129元、5.8小时。检查结束再次退出。 |
| 10. 深色模式 | 通过 | DevTools临时模拟深色；实测375px、背景rgb(0,0,0)、文字rgb(242,242,247)，目视看板和记录页正常。`dark-mode.json`、`05-dashboard-dark.jpg`、`06-records-dark.jpg`。 |
| 11. 开发者工具和服务器日志 | 通过（沿用已确认的非应用探测例外） | Console重载前的应用错误为故意输错密码的401，另有浏览器扩展错误／警告；重载后显示「控制台中有0条消息」。Network里应用请求均同源且成功，扩展资源单列；favicon两次GET均200。完整服务器日志仅有下列3条4xx：故意登录401，以及2条已确认排除的DevTools探测404，没有其他4xx/5xx。`console-before-reload.txt`、`console-after-reload.txt`、`network-after-reload.txt`、`web-server.log`、`web-log-audit.json`。 |

**六条 curl 的实际输出**

显示命令采用计划中的写法；执行脚本通过 curl 标准输入配置传入密码／Authorization，并额外保留响应头用于核对状态。下面仅去掉行尾空格，密码以占位符表示、令牌只保留前6位；原始脱敏文本为本轮的 `curl-demo.txt`。实际请求、状态和响应体均来自本轮临时服务。

```text
curl -sI http://127.0.0.1:8765/favicon.ico
HTTP/1.1 200 OK
Server: TravelLog/1.0
Date: Mon, 26 Oct 2026 02:15:56 GMT
Content-Type: image/png
Content-Length: 2222
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-cache

curl -s http://127.0.0.1:8765/api/meta
HTTP/1.1 200 OK
Server: TravelLog/1.0
Date: Mon, 26 Oct 2026 02:15:56 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 66
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"app": "travel-log", "api_version": 1, "server_version": "1.0.0"}

curl -s -X POST -H "Content-Type: application/json" -d '{"password":"<临时密码>","device_name":"curl"}' http://127.0.0.1:8765/api/tokens
HTTP/1.1 201 Created
Server: TravelLog/1.0
Date: Mon, 26 Oct 2026 02:15:56 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 103
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"token": "BvkPnb[其余隐藏]", "token_type": "Bearer", "expires_in": 7776000}

curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8765/api/trips
HTTP/1.1 200 OK
Server: TravelLog/1.0
Date: Mon, 26 Oct 2026 02:15:56 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 13
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"trips": []}

curl -si -X OPTIONS -H "Origin: https://localhost" -H "Access-Control-Request-Method: POST" http://127.0.0.1:8765/api/trips
HTTP/1.1 204 No Content
Server: TravelLog/1.0
Date: Mon, 26 Oct 2026 02:15:56 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 0
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Access-Control-Allow-Methods: GET, POST, PUT, DELETE
Access-Control-Allow-Headers: Authorization, Content-Type
Access-Control-Max-Age: 600
Access-Control-Allow-Origin: https://localhost
Vary: Origin

curl -si -X OPTIONS -H "Origin: https://evil.example" -H "Access-Control-Request-Method: POST" http://127.0.0.1:8765/api/trips
HTTP/1.1 403 Forbidden
Server: TravelLog/1.0
Date: Mon, 26 Oct 2026 02:15:56 GMT
Content-Type: application/json; charset=utf-8
Content-Length: 31
Content-Security-Policy: default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
X-Frame-Options: DENY
Referrer-Policy: no-referrer
Cache-Control: no-store
{"error": "来源不被允许"}

额外命令行验证：实际执行 set-password 后，原 Cookie 和 Bearer 请求均返回 401。临时密码未记录。
```

**第 11 条服务器日志核对**

以下摘录本轮原始日志中全部 4xx，以及 favicon 请求；完整日志不删改，保存在本轮 `web-server.log`。所有50条请求按状态计数的结果为：200×42、201×5、401×1、404×2，无5xx。Chrome探测路径为 `/.well-known/appspecific/com.chrome.devtools.json`，沿用用户在本对话明确回复「允许排除，保留原始证据」的处理方式。

```text
2026-10-26 10:17:47,776 INFO 127.0.0.1 "POST /api/login HTTP/1.1" 401 -
2026-10-26 10:23:18,199 INFO 127.0.0.1 "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 -
2026-10-26 10:24:28,953 INFO 127.0.0.1 "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 -
2026-10-26 10:24:29,165 INFO 127.0.0.1 "GET /favicon.ico HTTP/1.1" 200 -
2026-10-26 10:24:29,166 INFO 127.0.0.1 "GET /favicon.ico HTTP/1.1" 200 -
```

**偏差**

- 没有代码、测试、依赖或契约变更。用户已告知代码通过Opus审查，本次只增加验收记录；所有旧材料保留，本轮使用新的证据子目录。
- Chrome原生确认框用于删除与导入，系统文件选择框用于导入；没有依赖此前不可靠的浏览器事件等待。浏览器因同名文件存在而将下载文件加上`(1)`，实际导入的是本轮新下载文件，内容和金额均已核对。
- 第11条沿用此前用户确认的非应用DevTools探测例外，服务器原始日志、全部3条4xx及扩展Console来源均保留，没有修改服务器来消除探测日志，也没有过滤原始日志。除该已确认例外外，附录A无未通过项。

**运行过的检查**

- `PYTHONDONTWRITEBYTECODE=1 python3 verify_http.py`（仓库外的本轮验收脚本）：六条计划curl均通过；额外用实际`set-password`验证旧Cookie和令牌均401，未使用业务数据库。
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`：49项全部通过，完整输出在本轮目录的`backend-tests.txt`；摘要如下。

```text
----------------------------------------------------------------------
Ran 49 tests in 26.663s

OK
```

- `git diff ee75a4d -- . ':(exclude)docs/android-log.md'`：无输出，确认包括server.py、tests、README、OpenAPI和static在内的其余文件未修改。
- 附录A：11项通过，观察值和证据逐项列于上表；第11条以原始服务器日志和状态计数为准，例外单列。
- `git diff --check`：提交前通过；本次独立提交只包含本日志的追加内容。
- 专用测试标签和临时服务均已关闭，临时数据库已清理，浏览器站点缩放和视口已恢复。

**遗留问题和需要决定的事**

- 无新增实现问题。本次仅补验收材料；P1代码审查结论采用用户已确认的信息。
- 按本次指示停在P1，不合并分支，不开始P2。后续阶段由用户决定。

### P2 前端平台层（分支 `android/p2-platform`，2026-10-26）

**完成情况**（对应 P2.1～P2.3 及本阶段验收）

- [x] P1 前置条件：用户已确认 P1 代码通过 Opus 审查；P1 最后验收记录为 `9a70912`。本地 `main` 从 `16b9fb3` 快进到该提交，再建立本阶段分支。实现提交：`0754987 feat: 接入前端平台层与应用登录流程`。
- [x] P2.1：新增 `static/platform.js`，按既定 `Platform` 接口实现 Web Cookie／App Bearer 两条路径，只有该文件读取 `window.TravelNative`。`index.html` 在 `app.js` 前保留 `<!-- native-bridge -->` 标记并加载平台层。没有新依赖或接口扩展。
- [x] App 登录先规范化来源、检查 HTTPS（仅调试桥允许 HTTP），再以 10 秒超时探测 `/api/meta`；校验应用标识和版本之后才发密码到 `/api/tokens`。保存键为 `serverOrigin`、`authToken`；退出尽量撤销远端令牌，再清本地令牌；401 只清令牌；切换服务器同时清来源。证据：`platform-tests.cjs` 28 项，涵盖错误来源、非 JSON、版本不兼容、断网、超时、存储失败、退出和导出。
- [x] P2.2：`api()` 使用平台来源和认证头，Web `same-origin`／App `omit`，15 秒超时覆盖请求及响应体读取；401 先等待清凭据再显示登录页。App 启动检查版本，断网保留凭据、显示主界面提示和重试；重试恢复加载数据，重试遇 401 回登录。超时保留约定专用提示。证据：`app-tests.cjs` 21 项，完整输出 `frontend-tests.txt`（两套合计 49 项）。
- [x] 服务器地址栏、服务器／版本说明、切换服务器菜单只在 App 显示；返回键按实际打开顺序关闭最上层对话框，再依次隐藏图表提示、回记录页、返回 false。导出经 `Platform.saveFile()`；Web 原分享／下载流程迁至平台层，取消分享不触发下载。证据：上述行为验证及 `08-web-menu.png`、`08-export.json`、`08-import-double.png`。
- [x] 容错：未知交通方式显示原始文字、灰色徽标并阻止编辑；看板年份和统计均只取认识的交通方式；未知坐席仅在编辑原交通方式时作为选项保留、原样提交，不带到不同交通方式。验证包括 `ferry`、`constructor`、`__proto__` 及未知坐席。
- [x] P2.3：增加 `.t-unknown`、服务器地址栏、连接提示及原生菜单说明样式，全部使用既有主题变量，没有改交通方式配色。Web 新控件均隐藏，实测视口宽度和页面宽度均为 375px。
- [x] 三条语法验收命令全部通过，见 `syntax-checks.txt`：`node --check static/platform.js`、`node --check static/app.js`、`node --check static/dashboard.js`。
- [x] 附录 A 的 11 条 Web 回归全部通过；第 11 条包括 Network 面板同源检查和原始服务器日志核对，详见下表。
- [x] 下文列出全部改动／新增的 `app.js` 函数及事件处理器，说明 Web 行为保持方式。

交审材料保存在 **`/Users/niuniu/Documents/travel-log-review/p2/`**。其中包含仓库外的 Node 标准库验证脚本、首次失败证据、最终通过输出、截图、DOM 观察、原始服务器日志及附录 C 的 diff／提交列表。未使用业务数据库、未记录临时密码或完整令牌，未接触签名密钥。

**附录 A Web 回归逐项证据**

本轮使用 Chrome、375×812 CSS 像素、`http://127.0.0.1:8765/`，由 `start_web_review.py` 创建独立临时数据库和临时测试密码。截图均为本轮页面；浏览器本身的扩展不属于应用资源。

| 项目 | 结果 | 实际观察与证据文件 |
|---|---|---|
| 1. 登录 | 通过 | 错误密码提示「密码错误」，正确密码进入空列表。`01-login-error.png`，原始日志先 401 后 200。 |
| 2. 新增高铁 | 通过 | G1、CR400AF、二等座、553.50 元、1318.5 公里；2025-12-31 23:30～次日 01:00，卡片显示「G1 · CR400AF · 二等座」「1,318.5公里」「次日 01:00 · 1小时30分」。`02-hsr.png`。 |
| 3. 车次推断 | 通过 | 编辑为 D301，动车组自动选中，二等座保留；改车型为 CRH2A 后保存，卡片为「D301 · CRH2A · 二等座」。`04-metro-dom.txt`、`09-relogin.txt` 中仍有该卡片。 |
| 4. 地铁两段换乘 | 通过 | 新建北京地铁、2号线／1号线、6B。新增第 2 段时自动填复兴门；第 1 段下车站改建国门后，第 2 段同步。保存为西直门→国贸、40分钟、换乘1次、15公里。`04-link-observations.txt`、`04-metro-card.png`、`04-metro-dom.txt`。另建上海地铁2号线8A、人民广场→陆家嘴、4元15分钟。 |
| 5. 编辑和删除 | 通过 | D301 编辑成功；另建零票价临时公交再确认删除，数量5→4，提示「已删除」。`web-server.log` 的 PUT、DELETE 和随后 GET 均200；删除后总计4条、564.50元。 |
| 6. 筛选 | 通过 | 地铁筛选2条，合计9元55分钟；北京地铁筛选1条、5元40分钟。`06-filter-dom.txt`、`06-filter-beijing.png`。 |
| 7. 看板 | 通过 | 总览／铁路／公交／地铁均可打开。2026年2条9元，2025年1条553.50元，2024年1条2元，全部4条564.50元。全部月趋势容器323px、内容590px，横滑位置267→133.5；点击柱子提示「2026年10月／地铁／1次」，年趋势也显示。常去站点为行程端点，换乘排行有建国门，线路按北京／上海分组。`07-observations.txt`、`07-trend-tooltip.png`、`07-dashboard-metro.txt`、`07-transfer-rank.txt`。 |
| 8. 导入导出 | 通过 | 经新平台层实际下载 `travel-log-20261026 (2).json`，核对4条、56450分；通过系统选择框选同一文件，确认追加4条，提示「已导入4条」，数量变8，合计1129元、5.8小时。`08-export.json`、`08-import-double.txt`、`08-import-double.png`。 |
| 9. 退出后重登 | 通过 | 退出回到只含密码的 Web 登录页；重登仍为8条、1129元、5.8小时。`09-relogin.txt`、`11-final-dom.txt`。 |
| 10. 深色模式 | 通过 | DevTools 模拟 `prefers-color-scheme: dark`，背景 `rgb(0,0,0)`、文字 `rgb(242,242,247)`；记录与地铁看板可读，无横向溢出。`10-dark-records.png`、`10-dark-dashboard.png`。 |
| 11. 开发者工具与日志 | 通过 | Network 中应用的 HTML、CSS、三个 JS、图标、manifest、session、trips 全部是 `http://127.0.0.1:8765` 同源请求；扩展资源单列。Console 重新加载后0条消息，初始的故意错误登录401和扩展来源保留。`11-network.txt`、`11-console-before-reload.txt`、`11-console-after-reload.txt`；服务器65条请求：200×57、201×5、401×1、404×2，无5xx。完整 `web-server.log` 与 `11-server-audit.txt` 保留全部原始证据。 |

第11条的全部异常状态如下。401 是故意输错密码；两条 Chrome DevTools 自动探测 404 沿用用户此前明确回复「允许排除，保留原始证据」，单独列作非应用请求；没有通过改服务器或删日志掩盖它们。

```text
2026-10-26 16:39:45,525 INFO 127.0.0.1 "POST /api/login HTTP/1.1" 401 -
2026-10-26 16:44:46,533 INFO 127.0.0.1 "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 -
2026-10-26 16:46:15,082 INFO 127.0.0.1 "GET /.well-known/appspecific/com.chrome.devtools.json HTTP/1.1" 404 -
```

**`app.js` 全部函数变更及 Web 行为说明**

| 函数／处理器 | 改动与 Web 行为保持方式 |
|---|---|
| `api()` | 改走平台来源、认证头和15秒超时；Web 来源为空、认证头为空，仍为原同源路径、Cookie、JSON请求。Web 401 的清凭据调用为空操作，继续原登录页流程。超时属于计划明确要求的变更，覆盖响应体阶段。 |
| `tripCard()` | 认识的交通方式仍取原徽标和配色；仅对未知值按计划降级。 |
| `buildSeatOptions()` | 已有坐席数组和点击取消逻辑不变；额外选项仅针对未知坐席的原类型编辑，不修改全局选项。 |
| `openEditor()` | 已知类型仍填原表单并打开同一对话框；经 `showDialog()` 记录打开顺序。未知类型仅按计划提示，不编辑。 |
| `exportData()` | 仍 GET `/api/export`、同一日期文件名、同一 `JSON.stringify(data, null, 2)` 和 MIME；原 Blob／File／分享取消／下载／回收链接逻辑完整移入平台层 Web 分支。 |
| `showLogin()` | Web 仍关闭对话框、清列表／密码并聚焦密码；只额外清隐藏提示、填写隐藏服务器栏。App 才根据地址决定焦点。 |
| `showMain()` | 只额外更新 Web 中隐藏的服务器说明，仍切换原登录／主界面。 |
| `loadTrips()` | 请求与渲染不变；成功后收起提示，Web 该提示始终隐藏。 |
| `boot()` | 先初始化平台，Web 初始化为空操作；仍按 session→判断是否登录→trips 的顺序。仅 App 跳过 Cookie 会话、显示新控件并按凭据启动。 |
| 新增 `showDialog()` | 在原 `showModal()` 外记录打开顺序；对话框展示、关闭按钮和浏览器默认行为不变。 |
| 新增 `loadServerData()` | Web 直接调用 `loadTrips()`；仅 App 加入启动／重试版本检查。 |
| 新增 `showConnectionError()` | 仅 App 启动、登录后加载失败或重试调用；区分断网与专用超时提示。 |
| 菜单按钮点击处理器 | 同一菜单改经 `showDialog()` 打开，Web 菜单仍为导出／导入／退出／取消。 |
| 退出按钮异步处理器 | 改调 `Platform.signOut()`；Web 实现仍 POST `/api/logout`，最后回登录页。 |
| 登录表单异步处理器 | 改调 `Platform.signIn()`；Web 忽略服务器栏，仍 POST `/api/login`、显示服务端错误、加载行程，保留按钮禁用／恢复和原密码必填校验。 |
| 新增切换服务器、重试按钮处理器 | 控件在 Web 隐藏，仅供 App 使用；确认提示严格按计划。 |
| 新增 `Platform.onBackButton()` 回调 | Web 注册为空操作；App 才执行对话框→图表提示→记录页→false的优先级。 |

`dashboard.js` 仅修改 `renderDashboard()`：先过滤未知类型，再从同一集合产生年份及统计；所有既有类型、排行算法、数值与格式保持原样。`index.html` 的 App 控件默认隐藏；CSS 不改变原配色，Web 菜单的原按钮相邻关系保持不变。

**偏差**

- 无业务规则、契约、架构、依赖或文件范围偏离。仓库只改 `static/` 和本日志；现有测试、服务器、README、OpenAPI 均未改。
- 为遵守文件范围，新增的 Node 标准库测试和实施检查表放在仓库外交审目录，保留可复现脚本及失败→通过证据；没有在 `tests/` 添加或修改内容。
- 版本文字由 `Platform.init()` 读取桥中既有 `appVersion` 并写入专用文本节点；`app.js` 不读取原生桥，也不扩充 `Platform` 公共接口。App 的 URL 表单关闭浏览器自带格式校验，统一走平台层规范化，以支持计划允许的省略协议写法；Web 仍保留原校验。
- 导入使用此前已验证可用的原生文件选择框和原生确认框；自动化一度选错同名隐藏输入框，界面正确提示「第2段请选择线路」，修正测试定位后保存成功，没有为测试改业务逻辑。
- 第11条沿用用户确认的 Chrome 探测例外，完整日志保留。浏览器扩展来源按附录 A 原有规定排除。没有未说明的验收例外。

**运行过的检查**

- `node --check static/platform.js`、`node --check static/app.js`、`node --check static/dashboard.js`：全部通过；最终 `syntax-checks.txt`。
- `node --test /Users/niuniu/Documents/travel-log-review/p2/platform-tests.cjs /Users/niuniu/Documents/travel-log-review/p2/app-tests.cjs`：49项通过，0失败。平台层28项、界面层21项；完整 `frontend-tests.txt`。`platform-red.txt`、`app-red.txt`、`timeout-red.txt` 保留实现前或修复前的失败输出。
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -v`：49项全部通过，26.706秒，未修改测试；完整 `backend-tests.txt`。
- 附录 A：11项通过，逐项证据见上表；最后在最终文件上重新加载，8条记录、375px无溢出，所有 App 专用控件均隐藏。
- `git diff --check` 及实现提交前 `git diff --cached --check`：通过；范围核对确认服务器、测试、README、OpenAPI无差异。
- 临时服务已停止、数据库随临时目录清理；专用测试标签关闭，站点缩放、视口和 DevTools 临时深色模拟已恢复。

**遗留问题和需要决定的事**

- P2 无未完成验收项；App 模式当前通过桥边界模拟验证，真实 Capacitor／WebView、系统分享和硬件返回键按计划留在 P3／后续真机验收，不能将本轮测试称为安卓端到端通过。
- 按用户要求停在 P2；尚未创建 `mobile/`、安装任何 App 依赖或开始 P3。P2/P3 的 Opus 联合审查点保持计划原安排。
