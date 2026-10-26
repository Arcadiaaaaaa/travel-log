# Cloudflare 部署执行记录

日期：2026-10-26。分支：`codex/cloudflare-deploy`，基于 `987a329`。安卓暂停，没有开始 P3。部署说明见 [cloudflare.md](cloudflare.md)。

## 完成情况与证据

- GitHub：先检查全部历史的38个唯一文本对象，再上传私有仓库 `https://github.com/Arcadiaaaaaa/travel-log`。只推送 main、已有安卓阶段分支；不推内部检查点。首次审查只有历史测试固定密码的3处候选，均为测试夹具，无生产凭据；报告 `travel-github-sensitive-audit.json`。
- 新增 Python Worker、异步D1数据层与独立SQL迁移；复用原后端校验和安全常量。`server.py`、`static/`、`tests/test_server.py`、业务规则和OpenAPI与基线完全相同。
- D1数据库 `travel-log`：`02083134-6488-416e-b9c6-8a162d1b6e45`；初始迁移在本机和远端成功执行。没有上传个人数据库。
- Cookie固定30天；令牌90天滑动续期且条件更新限制每日写入；两种kind隔离、Authorization不回退Cookie、只保存SHA-256。密码Secret变更使两个会话种类失效。CORS覆盖应用错误响应，没有通配来源或Allow-Credentials。
- 共用失败次数持久保存在D1；并发测试先观察9次401的失败，再修正事务条件插入，得到5次401、4次429；云端交替调用两个登录入口得到5次401、第6次429，见 `travel-cf-limit-check.txt`。
- 导入使用分块JSON与单次D1 batch事务，新增真实SQLite执行测试覆盖800条多区段大导入、区段归属与中途失败整批回滚。
- 准确锁定Wrangler4.152.0、workers-py1.17.9、uv0.13.4、cryptography47.0.0及运行时SDK，提交npm／uv／WASM锁文件。`npm ci`、`uv sync`、实际Worker构建和运行成功。禁用Wrangler指标和Worker可观测性采集。
- 完整测试67项通过（原49项原样保留，新增15项D1／API、3项加密适配），见 `travel-cf-all-final.txt`；三个前端脚本语法检查和 `git diff --check` 通过。
- 临时验证Worker `travel-log-check-20261026.2200735309.workers.dev` 真实运行60万次PBKDF2：登录200，总耗时约2.2秒；Cookie读取、令牌签发／撤销、换乘写入与删除通过。令牌只输出前6位，随机密码只留在进程内。部署包压缩约2311KiB、启动约749ms；未开通付费或降低迭代次数。这是成功请求证据，不代表所有负载下的配额保证。

## Web附录A逐条回归

运行环境为真实本地Python Worker与D1，375×812视口，使用合成记录；证据目录下 `web/` 保存截图及DOM记录。

| 项 | 结果和证据 |
|---|---|
| 1 登录 | 错误密码提示「密码错误」，正确密码进入空列表；Web不显示服务器地址。`01-login-error.png` |
| 2 新增高铁 | G1／CR400AF／二等座，553.50元、1318.5km，跨年行程显示次日与1小时30分。`02-hsr.png` |
| 3 修改与推断 | G1改D301自动切动车，保留二等座，CRH2A保存；`03-inference.txt` |
| 4 地铁与换乘 | 北京2号线→1号线，两段；改前段下车站为建国门，后段上车站跟随；6b保存为6B。另建上海2号线。`04-linked.json`、`04-metro-card.png` |
| 5 公交与删除 | 新增18路／宇通E12，2元；另建0元临时记录，经确认删除，5条变4条。`05-records.txt`及服务器DELETE日志 |
| 6 筛选与金额 | 全部4条564.50元；地铁2条9元55分钟，北京1条5元40分钟。`06-filter.txt`、`.png` |
| 7 看板 | 四页签、2024／2025／2026／全部年份；月图横向滚动267→133.5；提示2026年10月地铁1次；年视图及城市、线路、站点／换乘排行核对。`07-*.txt`、`07-scroll.json`、`07-tooltip.png` |
| 8 导出导入 | 浏览器实际下载4条共56450分，再通过文件选择和确认导入4条，最终8条1129元。`08-import.txt`、`.png`、`exported-synthetic-trips.json` |
| 9 退出重登 | 退出回登录页，重登仍为8条。`09-relogin.txt` |
| 10 深色模式 | Chrome渲染仿真，正文375宽、背景黑、正文rgb(242,242,247)，列表及看板截图。`10-dark-*.png`、`10-colors.json` |
| 11 控制台／网络／日志 | 重载后控制台0条消息；应用资源同源。Web回归日志52个请求：200×22、304×22、201×5、故意错密码401×1、DevTools探测404×2，无5xx。用户已明确允许排除两次Chrome探测，保留完整日志。`11-console-after.txt`、`11-network.txt`、`web-server-segment.txt`、`web-server-summary.json` |

## 偏差与排查

- 用户明确批准Workers＋D1架构、官方运行依赖例外；又明确批准cryptography，保持PBKDF2-SHA256 600000次。原Python版仍只用标准库。
- Pyodide缺失hashlib.pbkdf2_hmac，真实Worker先返回500；改用批准的cryptography预编译WASM后，经标准向量、原哈希对照、本地及云端登录验证。
- 真实SDK的空请求体是JsNull、静态绑定已返回Python Response、D1 batch负责自动RPC序列化；均以实际错误为依据适配。早期开发原始日志保留这些已解决的500，附录A按明确的Web回归日志片段验收。
- Wrangler默认收集目录会打入虚拟环境等内容，改用独立构建目录仅复制四个运行模块；不修改原页面或后端。
- 默认urllib客户端标识被Cloudflare拒绝403／1010；如实标识为TravelLog-DeploymentCheck后通过，没有关闭平台防护。连接仅在命令中复用本机已有代理，不修改系统代理或SSH全局设置。
- 一轮追加云端检查出现一次503，其后5次401。该次503未保留正文，原因无法确认；后续明确采集正文、耗时及请求编号，复测连续5次401、第6次429。原失败输出 `travel-cf-remote-final.txt` 亦保留，不将这次异常说成已定位。
- 生产密码必须由用户在本机终端交互初始化，没有默认密码、测试密码或自动迁移的个人行程。

## 材料与遗留事项

全部截图、原始开发／回归请求日志、测试输出、敏感审查报告、合成导出文件保存在 `/Users/niuniu/Documents/travel-log-review/cloudflare/`。凭据配置日志、密码哈希文件和工具认证文件不纳入证据。

正式部署信息与最终清理结果在下方追加。密码初始化前登录返回503，属于拒绝未配置认证的预期行为；用户初始化后还需用个人密码自行登录确认。Cloudflare适配尚未经过Opus审查；未合并main。

## 正式发布结果

- 适配提交 `7a8e727c5245b046a623430d5f500c036e48e337` 已推送私有远端 `codex/cloudflare-deploy`，未合并main。
- 正式地址：`https://travel-log.2200735309.workers.dev`；Worker版本 `5cd14c26-2cb2-4420-b0c7-95a621572db7`。压缩包2310.75KiB，正式启动2122ms。`travel-cf-production-deploy.txt`。
- 正式线上：根页面、platform.js／app.js／dashboard.js、favicon.ico、meta均200且安全头存在；未登录行程及未知API均401，白名单来源带指定CORS及Vary，无Allow-Credentials；允许预检204、拒绝预检403；未设置密码的登录503。`travel-cf-production-check.txt`。503提示沿用原API文字，Cloudflare实际初始化命令以部署文档为准。
- 临时Worker `travel-log-check-20261026` 已删除，其随机测试Secret随之删除；正式部署没有PASSWORD_HASH绑定。本机测试专用 `.dev.vars` 已删除，本地验证进程已停止。
- 发布前D1检查：行程0、区段0、会话0、失败计数0；只清理本轮新库中已知临时失败计数。`travel-cf-clean-final.txt`。
- 发布前最终完整测试再次通过：67项、28.908秒、无失败；`travel-cf-suite-release.txt`。三项JavaScript语法检查通过。
- 第二次敏感审查覆盖53个历史文本对象、41个跟踪路径，无风险文件路径或凭据模式命中；`travel-cf-sensitive-audit.json`。只记录位置／类型，不输出候选值。
- 所有持久证据生成SHA-256清单 `SHA256SUMS.json`。正式密码仍由用户终端初始化：`python3 tools/cloudflare_admin.py`；已发出交接请求，未获取用户密码。用户配置前网站会显示登录页但无法登录。

## 2026-10-26 Opus审查后的登录限流修复

范围：仅修改 `server.py`、`cloudflare_core.py`，新增两份测试文件中的测试，并追加本节。P2已获用户转述的Opus通过结论；Cloudflare分支的本次修复仍等待审查，不据此自行宣布通过。未重新部署。

### 修复

- `/api/login` 与 `/api/tokens` 在密码校验之前原子占用一次尝试名额；不能取得名额时直接429，不执行密码校验。校验成功清除该IP全部记录；错误密码保留已占用的记录，不再重复记一次。
- Python版在同一 `_failures_lock` 临界区清理过期记录、检查数量并插入；Worker复用D1事务中的条件插入及其实际写入行数。两端移除原先独立的先查再校验路径。
- Worker尚未设置密码的提示改为在本机运行 `python3 tools/cloudflare_admin.py`。没有修改数据库迁移、业务规则、API文档、安全参数、依赖或前端文件。

### 测试与证据

证据目录：`/Users/niuniu/Documents/travel-log-review/cloudflare/auth-reservation-20261026/`。

- 新增两端 `test_concurrent_wrong_passwords_verify_at_most_five_times`，交替向两个登录入口并发发送9个错误密码请求，对真正的密码校验函数计数：修复前均为9次；修复后最多5次，并核对5个401、4个429。
- 新增Worker `test_concurrent_correct_passwords_do_not_bypass_reserved_limit`：先留下4次失败，再同时发送1个错误密码与8个正确密码。修复前正确密码越过限额返回200／201；修复后仅1次校验，正确密码请求全部429且未校验。
- 新增Python `test_concurrent_mixed_passwords_skip_verification_when_full`：先留下4次失败，再并发发送含正确密码的9个请求。暂停已进入的真实校验，确保其余请求先得到拒绝；仅1次校验，8个429逐一核对未进入校验。允许唯一获准请求根据密码返回200或401。
- 新增Worker初始化提示测试覆盖两个入口503及正确管理工具路径。
- Python并发测试在测试辅助方法中将监听队列设为16，排除默认队列过小造成的连接重置；没有修改生产监听参数。初次连接重置及之后因计数9而失败的输出均保留。
- 定向5项测试通过，见 `travel-auth-reservation-green.txt`；完整 `PYTHONDONTWRITEBYTECODE=1 uv run python -m unittest discover -s tests -v`，72项全部通过、30.519秒，见 `travel-auth-all-tests.txt`。两条RuntimeError诊断来自已有的故意事务回滚测试，测试结果为OK。
- AST逐方法比较确认两份测试文件的所有既有方法与断言完全不变；只新增辅助方法和测试。三个前端脚本 `node --check` 与 `git diff --check` 通过。

### Web回归进度及限制

本次使用临时SQLite数据库、现有测试夹具密码和本机 `http://127.0.0.1:8766`，不涉及线上密码或个人行程。实际CSS视口375×812；系统当前为深色模式。

1. 错误密码提示与正确登录通过，`web/01-login-error.png`。
2. 高铁G1／CR400AF／二等座／1318.5公里、跨年1小时30分保存成功，`web/02-hsr.png`。
3. 编辑D301自动切到动车并保留二等座，保存通过，`web/03-inference.txt`。
4. 北京地铁两段换乘，前段下车站由复兴门改建国门，后段跟随；卡片显示换乘1次，`web/04-linked.txt`。
5. 编辑通过；浏览器删除确认自动化尚未完成，未声称删除成功。
6. 地铁2条9元55分钟、北京1条5元40分钟，`web/06-filter.txt`。
7. 四页签、2024／2025／2026／全部年份、月／年、月图横向滚动266.8→0、图表提示框、按城市线路及站点／换乘站排行通过，`web/07-*.json`、`web/07-*.txt`。
8. 浏览器实际导出4条、56450分，文件为下载目录 `travel-log-20261026 (4).json`；浏览器文件导入尚未完成。
9. 退出重登仍有4条，`web/09-relogin.txt`。
10. 深色列表、看板通过，背景rgb(0,0,0)、正文rgb(242,242,247)，`web/10-dark-*.png`。
11. 捕获的控制台error／warn共0条；DOM中应用资源均为同源相对路径，另有测试工具注入的data图标（非网络请求）。服务器日志37次请求：200×32、201×4、故意错密码401×1，无其他4xx／5xx。见 `web/11-console.json`、`web/11-dom-resources.json`、`web-server.log`、`web-summary.json`；未打开Network面板，不将DOM资源清单冒充完整网络抓包。

自动审批拒绝切换到标题为“Codex Reset”的用户窗口，理由是窗口标题与回归无关、可能读取私人内容。没有绕过拒绝；仅对本次测试标签页调用直接对话框API仍未完成删除。已请求用户把“🧪 登录限流回归”测试页置前，等待操作；第5条删除、第8条导入未完成，不将本次Web清单记为全部通过。修复代码和全部自动测试不依赖此UI操作。

### 2026-10-27 Opus 接手完成与审查结论

执行者额度用完，由 Opus 接手，在执行者未提交的改动基础上完成本次修复。

- **代码审查**：两端都改为「先原子占用名额，再校验密码」，与审查要求一致。删除了两端已不再使用的 `too_many_failures`，避免以后再出现先查后记的写法。
- **测试修正**：新增的 `test_concurrent_mixed_passwords_skip_verification_when_full` 偶发失败。原因是唯一拿到名额的正确密码请求如果走 `/api/tokens`，返回的是 201，而断言只允许 200 或 401。已把 201 加入允许值；这是新增测试自身的问题，代码行为正确。修正后完整测试连续跑 5 次，72 个全部通过。
- **Web 回归第 5、8 条补测**（临时数据库，本机 8768 端口）：
  - 第 5 条：在页面里把 `confirm` 换成自动确认后，通过编辑面板的「删除这条记录」删除，行程从 4 条变成 3 条，提示「已删除」。
  - 第 8 条：导出得到 3 条，通过导入文件框的 change 事件导入，提示「已导入 3 条」，列表变为 6 条。
  - 控制台无报错；服务器日志全部为 200，没有 4xx/5xx。
  - 局限：这两条用脚本模拟了确认框和文件选择，没有点系统原生对话框。
- **结论**：限流修复审查通过，Web 回归 11 条全部通过。**尚未重新部署**，线上仍是修复前的版本。
