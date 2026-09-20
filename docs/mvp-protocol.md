# SKT MVP 验证协议

> 历史说明：本页记录 2026-08-18 的 legacy JSON trajectory smoke protocol。当前正式的
> Task 与 Trajectory 合同分别以[第五章](design/05-task-package-verification.md)和
> [第六章](design/06-rollout-trajectory-verification.md)为准；其中 agent/LLM gates 已实跑，
> 正式 Solver 不接收 Recipe、Scientific Skills、参考解或评分器，执行边界以[第十二章](design/12-interactive-container-rollout.md)为准。下文挂载 Skills 与 access 检查仅记录历史协议。

早期实现遵循 SKT 论文的控制流，但把当时尚未实现的 agent/LLM gates 显式标成 `not_run`。

## Task qualification

```text
rule-based package/reference gate
        ↓ pass
semantic validity gate
        ↓ pass
paired with-skill / without-skill rollout
        ↓ r+ > r-
difficulty rollouts (N=5)
        ↓ p_pass < 0.6
accepted task
```

Task 失败返回第一个 blocking gate 的结构化 diagnosis。`repair_task_document` 只自动处理
语义不变的缺字段（例如补写已声明的 output path 或 skill role）；不会生成控制变量、reference
answer 或 evaluator。任何 repair 后都必须从 rule gate 重新开始。

## Fresh rollout

每次调用 `rollout` 都创建新的临时 workspace，只复制：

- `visible/` 内容；
- `skills/` 内容。

`hidden/` reference 和 evaluator 不进入 solver workspace。失败 retry 要重新调用 rollout，新的
context id、workspace 和进程环境不会包含上一轮 trace、score、failure 或 verifier feedback。

## Trajectory qualification

deterministic validator 要求：

- evaluator score 等于 1；
- 正常完整终止；
- trace 可解析；
- 每个 required skill 有显式 access；
- 未暴露 verifier feedback。

MVP 的 `skill_use_proxy` 要求 access 发生在 `skill_application` 前，application 带 concrete
operation 和 evidence。它只是透明的结构代理；正式复现还需论文中的 LLM validator 检查每个
skill 是否真正影响决策且使用正确。

## SFT export

只有 trajectory qualification 通过的记录才能导出。generic MVP 格式用 `loss` 显式表示：

- system/task/tool observation：`false`；
- assistant response/reasoning/tool call：`true`。

正式训练应保留 harness-native schema，不把不同 harness 强行映射成统一 tool vocabulary；超过
64k 的完整轨迹应丢弃而不是截断。
