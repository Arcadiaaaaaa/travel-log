@AGENTS.md

## 给 Opus 的补充

在这个项目中，Opus 负责制定方案和审查。审查执行代理的成果时：

- 对照 `docs/android-plan.md` 中对应阶段的「验收」，以及附录 C 中的材料，逐条核对。
- 发现与 `docs/rules.md`、`docs/api/openapi.yaml`、`docs/architecture.md` 不一致的地方，或者未写进日志的偏差，就判为不通过。
- 安全相关的改动（认证、CORS、存储、清单文件、网络配置）要逐行读代码，不能只看测试是否通过。
