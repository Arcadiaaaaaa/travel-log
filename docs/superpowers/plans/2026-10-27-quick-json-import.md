# 快速JSON导入 Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans in the current session; user has approved implementation and tests. Steps use checkbox syntax.

**Goal:** 提供可复制的严格AI提示词、粘贴自动预览及显式确认追加导入。
**Architecture:** 新增纯JavaScript提示词／解析模块，app.js负责现有dialog与POST /api/import集成。JSON来源不可信；不执行代码，不推测修复数据；服务端继续负责整批字段校验。
**Tech Stack:** 原生HTML/CSS/JavaScript；Node标准库测试；原Python／Worker后端不改。
**Spec:** docs/superpowers/specs/2026-10-27-quick-json-import-design.md（用户已确认）。

## Global Constraints
- 分支codex/quick-json-import；不新增依赖、接口、数据库迁移、AI网络通信或持久草稿。
- 保留原有文件导入、规则、架构、安全头与既有测试断言；界面使用简体中文、h()和现有颜色变量。
- 所有测试只用合成数据；证据保存至仓库外持久目录；实现并提交后停下审查，部署另行确认。
- 文件白名单：static/quick-import.js（新）、static/index.html、static/app.js、static/style.css、tests/test_quick_import.cjs（新）、README.md、docs/quick-json-import-log.md（新）、本设计及计划文档。

## Review Focus
- 粘贴或修改JSON不应写数据库，旧预览不能与新输入混用。
- 双击、超时及重试不能自动重复追加；请求期间锁住输入和确认按钮。
- 数组元素为null／原始值、空列表、尾逗号、解释性文字、多个代码围栏都应报错，不能静默丢弃。
- 中文大文本应按UTF-8实际请求大小限制5MiB，不以字符数代替字节数。
- 提示词的格式示例必须能通过真实validate_trip，不能猜票价、时间或地铁车型；示例不得混入用户输出。

### Task 1: 提示词与解析
**Files:** Create static/quick-import.js, tests/test_quick_import.cjs。
**Interfaces:** QuickImport.parse(text) -> {trips, bytes}，失败抛出中文Error；QuickImport.buildPrompt(referenceDate) -> string，日期来自用户设备本地日期。
- [x] 先写Node测试，覆盖数组／trips对象／原导出对象、单JSON围栏、错误输入、逐条对象结构、20000条边界及UTF-8请求5MiB边界；观察缺模块导致失败。
- [x] 实现严格JSON解析与格式提示；只去除整段唯一JSON围栏，拒绝猜取或eval；不改变已解析字段。
- [x] 实现完整提示词：追问模式与最终纯JSON模式、所有枚举／字段限制／金额单位／墙上时间、地铁整程／区段、隐私与不臆造，包含仅用于格式解释的有效示例。
- [x] Node测试转绿，并用原server.validate_trip验证实际提示词中的示例。

### Task 2: 快速导入界面
**Files:** Modify static/index.html, static/app.js, static/style.css。
**Consumes:** QuickImport.parse/buildPrompt；既有api()/h()/showDialog()/loadTrips()/fmtPrice()/TRANSPORTS。
- [x] 新增菜单和底部面板；复制提示词和手动选择回退、textarea自动解析、前20条安全文本预览、总条数与明确确认按钮。
- [x] 输入变化立即使确认按钮及旧预览失效；解析使用短延迟避免长输入逐键卡顿；真正提交时再解析当前原文。
- [x] 请求期间禁止重复提交和输入修改；成功清空关闭并刷新；失败保留文本显示原错误；网络结果不确定不自动重试并提示核对。
- [x] 关闭时清空所有草稿、错误、计时器及预览；不改原importFile行为；脚本在app.js前加载。
- [x] 实际浏览器验证复制、手动回退、粘贴不写入、预览、坏字段整批不写入、成功追加、双击、关闭清空、深色和375px布局；新增功能不依赖系统confirm／文件选择对话框。

### Task 3: 验收与交付
**Files:** Modify README.md；Create docs/quick-json-import-log.md；更新本计划勾选状态。
- [x] 完整后端测试、Node新增测试、全部JS语法、git diff --check通过；核对既有测试和受保护文件未改。
- [ ] Web附录A回归，以服务器日志核对请求错误；记录实际完成项及局限，不把模拟或未完成项说成通过。
- [x] README解释手动AI流程、先追问必填、只追加不去重及错误处理；日志写明检查输出和持久证据路径。
- [x] 敏感信息检查、提交并推送功能分支；停下等待审查，未确认不部署。

## 收尾状态

实现与自动检查完成。真实浏览器已覆盖主要操作，但连接连续超时且系统窗口焦点发生变化，停止继续操作；附录A第8条严格数量翻倍、第9条主动退出重登、第11条最终Console／Network仍待补。详见docs/quick-json-import-log.md，不宣称验收全部通过。剪贴板失败回退由真实事件处理器测试覆盖，实际浏览器已验证复制成功，未在浏览器中强制制造剪贴板失败。
