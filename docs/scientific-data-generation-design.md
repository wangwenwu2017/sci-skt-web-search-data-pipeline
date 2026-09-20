# Heta × Scientific SKT 科学任务与轨迹数据生成设计

> 当前前半段的统一入口见[第十五章：输入包规范](design/15-input-package-contract.md)，可运行入口见[第十六章：管线实现](design/16-mock-pipeline.md)。本期包含参考解与测试的程序化自测；正式 Solver 试做与难度校准后置。mock 已验证，真实 Harbor 三角色已通过一个科学任务的端到端验收，见[运行记录](design/18-live-acceptance.md)。

> 文档类型：持续演进的技术设计索引  
> 更新日期：2026-09-15

本文档是整个项目设计的入口。先阅读本页了解章节范围，再按当前任务加载一个对应章节。各章节独立维护结论、边界、待定问题、实现状态和实验结果，从而控制 Agent 的上下文成本，并使局部修改不必加载整份报告。

## 下一版技术选型

已确认采用 **NeMo Data Designer 组织任务生成，NeMo Gym + Harbor 承接 rollout**。输入由人工先准备，后续接入来源适配 Agent；具体任务构造通过 Agent + Skill 自定义步骤完成。该方案尚待集成验证，职责、流程图和验收步骤见[第十三章 技术选型](design/13-data-designer-gym-harbor-architecture.md)。

## 当前正式 Solver 边界

正式 Solver 不接收 Campaign、Recipe、Scientific Skills、参考解或评分器，只在已验证任务容器内根据公开题目、输入和输出合同执行、观察结果、修改代码或参数并重新运行。Recipe 与 Scientific Skills 用于上游任务构造和 Reviewer 审核。Solver 结束后，Controller 才运行隐藏评分器。具体执行合同见[第十二章](design/12-interactive-container-rollout.md)。历史 skill-assisted 实验不代表当前生产规则。

## 推荐阅读方式

快速了解阶段职责、输入输出与 Solver 边界，先看[管线流程图（Mermaid）](pipeline-overview.md)。

1. 首次进入项目时阅读本索引；
2. 需要理解完整系统时阅读第一章；
3. 设计或实现某个阶段时只加载对应章节及其直接引用；
4. 更新设计时修改权威章节，其他章节通过链接引用，避免复制定义；
5. 汇总 proposal 或 report 时按章节顺序组合，并根据章节状态补充实现和实验结果。

## 章节目录

| 章节 | 内容 | 状态 |
| --- | --- | --- |
| [第一章 总体流程](design/01-overall-pipeline.md) | Source Scout、端到端链路、核心产物和总体原则 | Source Discovery 已接入固定管线 |
| [第二章 Scientific Recipe 与 Scientific Skill](design/02-scientific-knowledge.md) | Source Bundle、Codex extraction、Recipe、Skill、references 和 registry | MVP 已实现 |
| [第三章 Heta 抽取与 Knowledge Reviewer](design/03-heta-knowledge-review.md) | Source Bundle、抽取、两个 Reviewer 判断和 repair | MVP 已实现 |
| [第四章 TaskGen 与 EnvironmentGen](design/04-taskgen-environmentgen.md) | Task Author、任务模式、Docker 和 authoring trace | MVP 已实现 |
| [第五章 Task Package 与 Verify/Repair](design/05-task-package-verification.md) | visible/hidden、reference、evaluator 和任务修复 | MVP 已实现 |
| [第六章 Rollout 与 Trajectory Verification](design/06-rollout-trajectory-verification.md) | fresh rollout、harness、轨迹验证和 lineage | MVP 已实现并实跑通过 |
| [第七章 Dataset、SFT 与 Evaluation](design/07-dataset-sft-evaluation.md) | 数据集、序列化、训练和 held-out evaluation | MVP 已实现并实跑通过 |
| [第八章 MVP 实现与技术选型](design/08-mvp-implementation.md) | ALE 60 cards、组件、模型、成本和里程碑 | 部分方案已确认 |
| [第九章 实验结果与分析](design/09-results-analysis.md) | 生成统计、失败案例、训练与评测结果 | 实现后补充 |
| [第十章 Agent Factory 与批量生产](design/10-agent-factory-production-pipeline.md) | AgentSpec、Pipeline Skills、Source Discovery 与八阶段生产控制器 | MVP 已实现 |
| [第十一章 Campaign 与 Prompt 编译](design/11-campaign-brief-prompt-compilation.md) | 批次意图的阶段投影与 Solver 隔离 | 已有设计与实现记录 |
| [第十二章 交互式容器 Rollout](design/12-interactive-container-rollout.md) | 当前容器内 Solver 执行合同 | 已有设计与实现记录 |
| [第十三章 Data Designer + Gym / Harbor 技术选型](design/13-data-designer-gym-harbor-architecture.md) | 下一版组件分工、输入输出、生产与 rollout 流程图 | 选型已确认，待集成验证 |
| [第十四章 DeepSeek 数据管线开发与资源方案](design/14-deepseek-data-pipeline-implementation.md) | 开发阶段、接口、质检与难度、CPU/API预算、训练扩展 | 设计方案，附离线预算工具 |

## 文档维护约定

每章采用相同结构：

```text
章节目标
已确认结论
详细设计
接口与产物
待定问题
实现状态
实验与观察
```

章节可以根据内容省略尚未开始的部分。已确认结论与待定问题需要明确区分。核心概念只在一个章节定义；原型实现与长期边界分别说明；普通流程保持简洁，冲突、高风险和不确定情况按需展开。

现有专项文档继续作为章节的直接参考：

- [2026-08-24 周会技术汇报](weekly-report-2026-08-24.md)
- [Scientific Recipe 与 Scientific Skill 产物合同](scientific-skill-spec.md)
- [Heta 抽取规则](heta-extraction-rules.md)
- [MVP 验证协议](mvp-protocol.md)
- [早期 Proposal 基线](scientific-data-generation-proposal.md)
- [MVP 原型结果](mvp-results.md)
