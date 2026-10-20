# 旅行记录

一个自托管的个人行程记录工具，用来替代“车票票”这类云端应用。部署在你自己信任的服务器上，iPhone 用 Safari 打开后“添加到主屏幕”即可像 App 一样使用。

- **数据只在你的服务器上**：一个 SQLite 文件，没有任何第三方服务、统计脚本或外部 CDN。
- **零依赖**：后端只用 Python 3.9+ 标准库，前端是原生 HTML/CSS/JS，全部代码一眼能读完。
- **单用户密码登录**：密码用 PBKDF2 加盐哈希保存；会话 Cookie 为 HttpOnly + SameSite=Strict；登录失败 5 次锁 10 分钟。

## 记录的内容

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| 交通方式 | 是 | 普快火车 / 动车组 / 高速动车组 / 公交车 / 地铁 |
| 出发时间、到达时间 | 是 | 到达时间不能早于出发时间，支持跨天 |
| 票价 | 是 | 单位元，最多两位小数（内部以“分”为整数存储，不会有浮点误差） |
| 车次号 / 线路 | 否 | 输入 G/D/K/T/Z 开头的车次时会自动切换对应的火车类型 |
| 交通工具型号 | 否 | 如 CR400AF、CRH2A |
| 坐席 | 否 | 动车组 / 高速动车组：二等座、一等座、商务座、二等卧、一等卧、无座；普快：硬座、硬卧、软卧、无座；公交、地铁不分坐席 |
| 里程 | 否 | 单位公里，手动填写，最多一位小数，留空记为 0 |
| 出发地、到达地 | 否 | |
| 备注 | 否 | |

### 地铁行程

地铁记录方式和火车不同：

- **地铁系统**（如“北京地铁”）：从下拉菜单选择；第一次选“+ 新增地铁系统…”输入后，以后就会出现在下拉选项里。
- **多段换乘**：一次地铁出行可以有多段，每段填线路、车型、上车站、下车站。点“+ 添加换乘”时，新一段的上车站自动填为上一段的下车站（换乘站），之后改动上一段的下车站也会跟着更新；手动改过的上车站不再跟随。换乘站不算目的地。整段行程的起止站自动取第一段上车站和最后一段下车站，票价、时间按整次出行填写。
- **线路**：下拉选项是该地铁系统里用过的线路，新线路同样可以“+ 新增线路…”。
- **车型**：下拉选择常见编组车型（3B、4B、6B、8B、4A、6A、8A、6As、8As、4L、6L），也可以“+ 其他车型…”。写法会自动规范，如 `6b` → `6B`。选过一次车型后，再选同一条线路会自动带出该车型。
- 记录列表筛选“地铁”时，会多出一行按城市（地铁系统）筛选。

从旧版本升级时，已有的地铁记录会自动迁移成单段行程（原“车次号”成为线路），地铁系统留空，编辑时补选即可。

“记录”页按月份分组显示，顶部统计行程次数、总花费、总乘车时长，可按交通方式筛选。右上角菜单可导出 / 导入 JSON 备份。

“看板”页可按年份或全部查看，分为四个页签：

- **总览**：次数、花费、时长、里程、出行天数、到过的地点；交通方式构成（次数 / 花费 / 时长 / 里程）；出行趋势；常去地点和路线；出发时间分布；记录之最。
- **铁路**（普快、动车、高铁）：总览数字、列车类型构成、坐席分布、出行趋势、车站 / 路线 / 车次 / 车型排行、出发时间、记录之最。
- **地铁**：可按城市筛选。站点排行分“常去站点”和“换乘站”，选“全部城市”时是总排行（标注城市），选某个城市时是该城市排行；换乘站不计入常去站点。线路和车型每个城市分别排行。
- **公交**：总览数字、出行趋势、站点 / 路线 / 线路 / 车型排行、出发时间、记录之最。

出行趋势可切换“月 / 年”视图：月视图在选定年份时显示 12 个月，选“全部”时显示从第一条到最后一条记录的每个月（可左右滑动）；年视图对比全部年份。点柱子查看各交通方式的明细。

看板完全在浏览器里根据已有记录计算，不需要额外接口。交通方式的配色经过色盲区分度校验，浅色和深色模式各有一套。

## 本机试用

```bash
python3 server.py set-password      # 设置密码（至少 8 位）
python3 server.py serve             # 打开 http://127.0.0.1:8765
```

数据默认保存在 `data/travel.db`。

## 部署到服务器

iPhone 的“添加到主屏幕”和 Secure Cookie 都需要 HTTPS，推荐用 Caddy 做反向代理，它会自动申请证书。

1. 把整个目录上传到服务器，例如 `/opt/travel-log`，并创建一个专用用户：
   ```bash
   sudo useradd --system --home /opt/travel-log travel
   sudo chown -R travel:travel /opt/travel-log
   ```
2. 设置密码：
   ```bash
   sudo -u travel python3 /opt/travel-log/server.py set-password --db /opt/travel-log/data/travel.db
   ```
3. 安装 systemd 服务（按需修改路径）：
   ```bash
   sudo cp deploy/travel-log.service /etc/systemd/system/
   sudo systemctl enable --now travel-log
   ```
4. 配置 Caddy：把 `deploy/Caddyfile` 中的域名改成你的，合并到 `/etc/caddy/Caddyfile`，然后 `sudo systemctl reload caddy`。
5. iPhone 上用 Safari 打开 `https://你的域名`，登录后点“分享 → 添加到主屏幕”。

服务默认只监听 `127.0.0.1`，不会直接暴露到公网，所有外部访问都经过 HTTPS 反向代理。

### 环境变量

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `TRAVEL_HOST` | `127.0.0.1` | 监听地址 |
| `TRAVEL_PORT` | `8765` | 监听端口 |
| `TRAVEL_DB` | `data/travel.db` | 数据库路径 |
| `TRAVEL_TRUST_PROXY` | 未设置 | 设为 `1` 时从 `X-Forwarded-For` 取客户端 IP（仅在反向代理后面开启） |
| `TRAVEL_COOKIE_SECURE` | `auto` | `always` / `never` / `auto`（根据 `X-Forwarded-Proto` 判断） |
| `TRAVEL_CORS_ORIGINS` | `https://localhost,capacitor://localhost` | App 来源白名单，逗号分隔；设为空字符串关闭 CORS，不支持 `*` |

Web 继续通过 `/api/login` 使用 30 天固定有效期的 Cookie。App 先读取公开的 `/api/meta` 检查接口版本，再通过 `/api/tokens` 获取 90 天滑动有效期的 Bearer 令牌，退出时调用 `DELETE /api/tokens/current`。CORS 只对 `/api/*` 的白名单来源开放，不允许跨源携带 Cookie。接口格式和认证规则见多端开发文档。

### 修改密码

再次运行 `set-password` 即可，所有已登录设备会被强制下线。

## 备份

- 在 App 菜单里“导出数据（JSON）”，iPhone 上会弹出分享面板，可以存到“文件”App。
- 或者在服务器上直接备份数据库（服务运行时也安全）：
  ```bash
  sqlite3 /opt/travel-log/data/travel.db ".backup '/path/to/backup/travel-$(date +%F).db'"
  ```

导入 JSON 时是**追加**，不会覆盖已有记录；文件里任意一条不合法则整批都不导入。

## 多端开发文档

项目正在扩展为 Web、安卓、iOS 三端，相关文档：

- [AGENTS.md](AGENTS.md)：执行代理的工作约定
- [docs/rules.md](docs/rules.md)：字段、校验、交互与统计口径（单一事实来源）
- [docs/architecture.md](docs/architecture.md)：多端架构与决策
- [docs/api/openapi.yaml](docs/api/openapi.yaml)：接口契约
- [docs/android-plan.md](docs/android-plan.md)：安卓 App 分阶段计划，执行记录在 [docs/android-log.md](docs/android-log.md)

## 开发

```bash
python3 -m unittest discover -s tests -v   # 运行接口测试
python3 tools/make_icons.py                # 重新生成图标
```

目录结构：

```
server.py            后端（HTTP 服务 + SQLite）
static/              前端页面、样式、脚本、图标
tests/               接口测试
deploy/              systemd 与 Caddy 配置示例
tools/make_icons.py  图标生成脚本
```
