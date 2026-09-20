# 第八章 MVP 实现与技术选型

> 状态：部分方案已确认  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 下一版选型（2026-09-15）

采用 NeMo Data Designer 组织任务生成，人工先准备来源输入与生成配置，后续接入来源适配 Agent；通过自定义步骤调用 Task Author Agent + Skill。任务执行采用 NeMo Gym + Harbor，项目侧保留科学质量控制与数据集发布。详见[第十三章](13-data-designer-gym-harbor-architecture.md)中的职责、流程图和验收步骤。该方案尚待集成验证，下文保留早期 MVP 决策。

## 章节目标

把长期设计映射为可以运行的第一版系统，并记录组件、模型、成本、里程碑和验收标准。

## 已确认结论

- 第一批 raw sources 使用本地 ALE 60 个 Task Cards；
- 先选择少量 CLI 可验证任务完成单条端到端闭环；
- MVP 的 Agent stages 统一优先采用 Codex + stage-specific Skill；
- Knowledge Reviewer 的 canonical path 已确定为单个 Codex 任务加载 `knowledge-reviewer` Skill，一次输出 Knowledge Validity 与 Task Generation Suitability 两个结论；
- Reviewer 对 Source Bundle 和 Candidate Knowledge Bundle 只读，唯一正式产物是 `knowledge-review.json`；
- 单次结构化 LLM 调用暂不进入 MVP 主链路，后续可依据真实审核数据评估为 fast path；
- 已有 Docker 优先复用，缺失环境再生成；
- 先冻结 Recipe、Skill、Task Package 和 Trajectory 产物，再实现批量流程。

## 待定问题

- 首批 ALE tasks 的选择；
- Codex 模型版本、运行参数和 harness；
- Docker 执行基础设施；
- 组件接口和目录布局；
- 成本、并发、失败预算和阶段里程碑。
