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
