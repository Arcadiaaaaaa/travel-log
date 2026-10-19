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
