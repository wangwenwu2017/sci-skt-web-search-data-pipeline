# 第七章 Dataset、SFT 与 Evaluation

> 状态：MVP 已实现并以真实 Verified Trajectory 实跑通过  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 7.1 章节目标

本章定义 Verified Trajectories 如何组成可审计、可复现的数据集，并进一步生成面向特定模型和 harness 的 SFT records。第六章决定单条轨迹是否可信；第七章当前负责数据收集、精确去重、序列化、版本管理和发布。内部 executable evaluation set 属于数据生产链跑通后的下一阶段，本章只保留接口边界。

原始 Verified Trajectory 始终作为数据源事实。训练模板、tokenizer、loss mask 或目标 harness 的变化只产生新的派生数据集，不修改原始轨迹。这样同一批可信执行记录可以支持不同模型、不同训练框架和后续分析。

SKT 将通过验证的完整轨迹保留为 harness-native interaction，再使用目标 tokenizer 和 chat template 进行端到端序列化；assistant 生成的 reasoning、tool calls 和 responses 接受监督，system、task 和 tool observations 只作为条件上下文。[SKT Training on Verified Trajectories](https://arxiv.org/html/2608.02287v1#S3.SS4) 本章继承这一基本思路，并增加完整 lineage 和可复现的数据版本。

## 7.2 阶段合同

```text
Verified Trajectory Store
Knowledge and Source Registry
Dataset Build Request
        ↓
Dataset Curation
├── eligibility
├── exact deduplication
├── coverage and quality statistics
└── immutable release manifest
        ↓
Dataset Release
├── Raw Verified Trajectory Dataset
└── Target-specific SFT Dataset

Future Extension
└── Held-out Executable Evaluation Set
```

一次 Dataset Build 只读取上游 immutable objects，通过 manifest 引用 task、trajectory、artifact 和 registry digests。相同输入集合、build policy 和 serializer version 应产生相同的 record IDs 和 release digest。

## 7.3 输入与数据对象

### 7.3.1 Dataset Build Request

```text
Dataset Build Input
├── verified-trajectory-registry
├── verified-task-registry
├── knowledge-and-source-registry
├── dataset-policy
│   ├── eligibility
│   ├── deduplication
│   └── release restrictions
└── serializers/
    └── <target-model-and-harness-config>
```

Dataset policy 描述当前 release 的用途、允许的数据来源、去重规则、长度限制和许可证范围。它不改变 trajectory verdict，也不依据文风或主观偏好重新评分轨迹。

### 7.3.2 三类输出对象

| 对象 | 内容 | 主要用途 |
| --- | --- | --- |
| Raw Verified Trajectory Dataset | harness-native trace、artifacts、verification 和 lineage locators | 数据事实、审计和重新序列化 |
| SFT Dataset | 面向目标模型的 messages、tool protocol、supervision spans 和 loss mask | 监督微调 |
| Executable Evaluation Set | held-out Task Packages、Skills、runtime 与受控 evaluator | 后续 Agent system 评测 |

三类对象共享同一套 Source → Recipe/Skills → Task → Environment → Trajectory lineage。当前 MVP 只发布前两类对象。SFT record 是 Verified Trajectory 的派生表示；后续 Evaluation Set 的核心对象是可执行 Task Package，不需要提供 teacher trajectory。

## 7.4 Raw Verified Trajectory Dataset

### 7.4.1 权威数据范围

Raw Dataset 不复制或改写第六章的 native trace。它通过 release manifest 固定以下对象：

- verified trajectory attempt digest；
- harness-native messages、tool calls 和 tool results；
- output artifact manifests 与 content digests；
- terminal status、evaluator outcome 和 trajectory verification report；
- Task Package、runtime、Recipe、Skills 和 Source lineage；
- model、harness、system prompt、tools 和 sampling configuration。

失败 attempts 可以进入受限的分析库，用于统计 runtime、task 和 Solver failure，但不进入 Raw Verified Trajectory Dataset，也不进入默认 SFT serialization。

### 7.4.2 Dataset Release 目录

```text
dataset-release/<dataset-id>/<version>/
├── manifest.json
├── build/
│   ├── request.json
│   ├── dataset-policy.yaml
│   ├── serializer-config.yaml
│   ├── serializer-implementation.json
│   └── serializer-implementation/
├── raw/
│   └── trajectories.jsonl
├── sft/
│   ├── manifest.json
│   └── records.jsonl
├── statistics.json
├── lineage.jsonl
├── _verification/
│   └── report.json
└── DATASET_CARD.md
```

`trajectories.jsonl` 保存稳定 ID、digest 和 storage locator，不要求把大型 artifacts、Docker images 或 Task Packages 复制进 release 目录。外部对象由 manifest-of-digests 固定；需要离线分发时再由 exporter 物化完整 bundle。未来增加 evaluation release 时，再添加独立的 `evaluation/manifest.json` 和 `tasks.jsonl`。

### 7.4.3 Release manifest

`manifest.json` 至少记录：

```json
{
  "dataset_id": "scientific-agent-trajectories",
  "version": "0.1.0",
  "build_policy_digest": "sha256:<digest>",
  "registry_snapshot_digest": "sha256:<digest>",
  "counts": {
    "verified_trajectories": 0,
    "sft_records": 0
  },
  "release_digest": "sha256:<digest>"
}
```

Release 一旦发布即保持不可变。新增数据、修复 lineage 或更换 serializer 都产生新版本，并通过 parent release 记录演进关系。

## 7.5 Eligibility 与集合级质量控制

Dataset Builder 只纳入满足以下条件的轨迹：

- 对应 Task Package digest 仍处于 verified 状态；
- trajectory deterministic qualification 为 `pass`；
- Scientific Process Validity 为 `accept`；
- native trace、artifacts 和 verification report 均可读取且 digest 一致；
- model、harness、environment 和 task lineage 完整；
- 不存在尚未处理的 `suspected_task_issue`；
- Source、software、data 和生成产物满足当前 release policy。

这些条件只确认上游结论和数据完整性。Dataset Builder 不调用新的 LLM judge，也不根据 Skill 是否被访问过滤通用 scientific-correctness 数据。

集合级统计用于观察覆盖和偏差，包括 source family、Recipe、task mode、科学领域、输入规模、artifact 类型、model、harness、trajectory length、tool-call count 和 recovery events。Balancing policy 可以据此进行上限采样或分层抽样，但不会制造新的轨迹或修改已有记录。

## 7.6 MVP 去重与后续数据划分

MVP 只处理能够通过 digest 和 lineage 客观确认的重复：

- 相同 trajectory digest 只保留一个 registry entry；
- 相同 Task Package digest 只保留一份 task metadata，不合并其不同成功轨迹；
- 同一 attempt 的不同 serializer 输出通过共同 `trajectory_id` 关联，不计为新的原始轨迹；
- 内容完全相同但路径不同的 artifacts 使用 content digest 合并存储。

同一 Task 上由不同 model、harness 或 sampling 产生的成功轨迹可以同时保留，因为它们代表不同执行行为。Dataset policy 可以限制每个 task 的最大轨迹数，防止少量任务在训练集中占据过高权重。

当前阶段不构建内部 train/evaluation split。首批 Verified Trajectories 可以全部进入候选训练池，最终效果使用 ALE 或其他外部 benchmark 验证。开始建设内部 executable evaluation set 时，再根据当时的 Recipe 和 Source 分布选择隔离单位；同一个 Recipe 派生的任务至少需要保持在同一侧。

## 7.7 SFT Serializer

### 7.7.1 Serializer 边界

Serializer 接收一条 Verified Trajectory 及其目标配置：

```text
Verified Trajectory
Target model and tokenizer
Chat template
Target harness tool schema
Maximum sequence length
Supervision policy
        ↓
SFT Record
```

原始 harness-native trace 保持权威。Serializer 只生成派生表示，完整保留执行失败后的恢复过程，也不把多条轨迹拼接成一条成功记录。目标 harness 需要协议转换时，adapter 必须逐项记录转换规则，并让每个派生消息能够回指 native event 或冻结 submission。

一个 serializer 只处理与目标 tool protocol 兼容的轨迹。不同 harness 之间需要明确且经过验证的 adapter；缺少可靠 adapter 时保留原生工具结构，为对应 harness 分别生成 SFT dataset。

### 7.7.2 Supervision 与 loss mask

MVP 采用以下默认规则：

| Segment | Conditioning | SFT loss |
| --- | --- | --- |
| System prompt | 是 | `0` |
| Task Card / user instruction | 是 | `0` |
| Recipe / Scientific Skills | 正式 Solver 不接收，不进入正式 SFT 上下文 | 不适用 |
| Tool results and environment observations | 是 | `0` |
| Assistant analysis/reasoning fields | 由目标模板决定 | `1` |
| Assistant tool calls | 是 | `1` |
| Assistant final response | 是 | `1` |
| Post-termination logging | 否 | 不进入 record |

模型学习的是完整 Agent behavior，包括工具选择、参数构造、文件操作、科学决策、错误恢复和最终回答。工具返回、任务内容和 Skill 文本继续作为条件上下文，不作为模型要预测的目标。

每个 assistant span 在渲染前具有明确 supervision flag；token-level loss mask 由目标 tokenizer 渲染后生成。Serializer 同时保存 template、tokenizer 和 serializer version，避免 chat template 更新后无法解释旧数据。

### 7.7.3 完整轨迹与长度处理

一条 SFT record 对应一条 uninterrupted Verified Trajectory。发生错误后成功恢复的步骤完整保留，因为这些 action 属于真实成功过程。

超出目标模型长度上限的记录默认标记为 `overlength` 并从该 SFT build 排除，Raw Dataset 继续保留。静默截断可能破坏 tool call/result 配对、删除最终 evaluator 对应的操作或改变监督含义，因此不作为默认策略。SKT 的实验同样保留完整记录并丢弃超过 64k tokens 的样本，而不进行 token-level truncation。[SKT Serialization and Supervision](https://arxiv.org/html/2608.02287v1#Sx4.SS1)

### 7.7.4 SFT record

```json
{
  "record_id": "sft-<digest>",
  "trajectory_id": "traj-<id>",
  "task_digest": "sha256:<digest>",
  "serializer_id": "<model>-<harness>-v1",
  "messages": [],
  "supervision_spans": [],
  "token_count": 0,
  "lineage_ref": "lineage:<id>"
}
```

`record_id` 由 trajectory digest、serializer config digest 和 supervision policy digest 确定。同一轨迹通过不同 tokenizer、chat template 或 harness adapter 渲染时会得到不同 record ID，但继续引用同一个 `trajectory_id`。

### 7.7.5 `codex-batch-docker` adapter

首个 serializer 为 `reprolab-codex-batch-o200k/0.1.0`，只接受 `codex-batch-docker/0.1.0` 轨迹。它按 native JSONL 顺序保留 completed assistant messages 和 shell calls；shell observation 作为 `tool` message 保留且 loss 为 `0`。临时 authoring workspace 的绝对路径统一映射为 `/workspace`，不改变命令的其余内容。

Codex native `file_change` event 当前只含被修改的路径，没有 patch body。adapter 不推测缺失的 patch，而是将最后一条 schema-constrained Agent response、冻结的 `submission.json` 与 `submission/files/` 合成一个 terminal `batch_submission`。该 submission 保存真实 command、summary、文件路径、文件 hash 和 UTF-8 全文。每条 SFT record 的 `transformations` 会记录被这一 terminal submission 承接的 file-change 数量。

渲染采用项目定义的 `reprolab-segmented-messages-v1` 模板和 `tiktoken 0.13.0` 的 `o200k_base` encoding。每个 message wrapper 保持 loss `0`，assistant content 按 supervision policy 赋值为 `1`。record 同时保存 rendered text、token IDs 和等长 loss mask，qualification 会重新渲染并逐项比较，避免 message、token 与 mask 彼此漂移。

## 7.8 SFT Run 与模型 Lineage

SFT Dataset 是训练系统的输入，具体训练 run 继续记录：

```text
base model and revision
dataset release and serializer ID
tokenizer and chat template
training framework and version
optimizer and schedule
sequence and batching policy
random seed
output checkpoint digests
```

训练配置不回写 Dataset Release。每个 checkpoint 通过 training run manifest 关联准确的数据版本和 SFT build，使模型结果可以追溯到 Source、Recipe、Task 和原始轨迹。

本章只规定训练数据接口和 lineage。具体 base model、optimizer、学习率、epoch、packing 和 checkpoint selection 属于实验配置，应在第九章和对应 run manifest 中记录，而不固定进通用数据合同。

## 7.9 后续 Held-out Executable Evaluation Set

### 7.9.1 延后原因与评测对象

内部 evaluation split 需要足够数量且具有多样性的 Recipe、Source 和 Task。当前先完成任务生产、轨迹采集和 SFT serialization，避免在样本数量不足时提前固定复杂分组规则。

后续 Evaluation Set 保存经过第五章验证且属于 held-out groups 的 Task Packages：

```text
evaluation-set/
├── manifest.json
├── tasks.jsonl
├── solver-visible package locators
├── runtime locators
└── verifier-only evaluator locators
```

Solver 只获得自包含 Task Card、inputs、公开 output contract、允许工具和 runtime；Campaign、Recipe、Scientific Skills、reference solution、evaluator internals、teacher trajectories 和历史结果保持 hidden。评测运行沿用第六章的 fresh session、fresh workspace 和 harness-native recording，但评测轨迹不自动进入训练数据。

### 7.9.2 评测指标

核心指标来自 task evaluator：

- mean normalized score；
- full-success rate；
- 按 task mode、Recipe family、科学领域和 artifact 类型的分组结果；
- timeout、tool failure 和 policy violation 等 execution outcomes；
- 多次完整运行的均值与波动。

评测报告需要固定 model、harness、system prompt、tools、sampling 和 Task Package digests。科学过程 Reviewer 可以用于错误分析或高可信评测，但主排名优先使用可执行 evaluator outcome，保持结果客观且可重复。

SKT 的 SkillEval 使用与训练任务相同的合成与验证管线，同时来自独立 skill/task pool，评测任务及其轨迹不进入 SFT 数据。本项目后续采用相同的 held-out executable task 思路，再根据实际数据分布决定按 Recipe 或 Source 隔离。[SKT SkillEval Composition](https://arxiv.org/html/2608.02287v1#Sx3.SS2)

## 7.10 Lineage 与可撤回性

每个 SFT record 和 evaluation task 都可以沿以下链路解析：

```text
Dataset Release
  → SFT Record or Evaluation Task
  → Verified Trajectory                         # SFT only
  → Rollout Attempt + Verification
  → Verified Task Package + Environment
  → Accepted Recipe + Scientific Skills
  → Source Bundle
```

Registry 可以根据 source、Recipe、Task、environment 或 evaluator digest 查询全部下游对象。若上游产物后来被确认存在问题，系统创建 revocation record，列出受影响的 trajectories、SFT records、dataset releases 和 checkpoints。已发布 release 继续保持不可变，通过新版本和撤回清单表达状态变化。

## 7.11 Dataset Card 与统计报告

每个 release 生成 `DATASET_CARD.md` 和机器可读 `statistics.json`，至少说明：

- 数据来源范围、许可证和 release restrictions；
- Knowledge、Task 和 Trajectory verification 流程；
- 当前 release 的数据选择范围，以及是否包含内部 evaluation split；
- Recipe、task mode、领域、artifact、model 和 harness 分布；
- trajectory length、assistant turns、tool calls 和 recovery 统计；
- evaluator score 与成功轨迹数量；
- SFT serializers、length filtering 和 loss-mask policy；
- 已知限制、排除来源和撤回记录。

统计报告只汇总正式 registry 字段，不通过重新读取隐藏 CoT 或 Reviewer analysis 生成额外标签。

## 7.12 与 SKT 的继承和调整

| SKT | 本项目第七章 |
| --- | --- |
| 仅使用 verified successful trajectories | 完整保留 |
| 保留 harness-native tool schema 和 action structure | 完整保留 |
| assistant reasoning、tool calls、response 接受监督 | 完整保留，并由 serializer policy 显式记录 |
| system、task、tool observations mask loss | 完整保留 |
| 不拼接或截断完整轨迹 | 完整保留；overlength 只退出当前 SFT build |
| SkillEval 使用 held-out skill/task pool | 作为后续扩展，届时按 Recipe 或 Source 隔离 |
| 单一实验配置的数据转换 | 增加 immutable Raw Dataset 与多 serializer 派生层 |

本项目当前先把 Raw Verified Trajectory 与 SFT rendering 分开管理，保证原始执行证据不受训练格式影响。Executable evaluation 在核心数据生产链跑通后单独建设。

## 7.13 明确排除的操作

第七章不执行：

- 重新判断 Task 或 Trajectory 是否正确；
- 修改、裁剪、拼接或修复原始轨迹；
- 在启用内部评测后使用 evaluation trajectories 生成训练记录；
- 根据 Skill access 过滤通用科学轨迹；
- 把 hidden evaluator、reference solution 或 Reviewer analysis 写入 SFT context；
- 在通用数据合同中固定某个模型的训练超参数。

Task 与 evaluator 问题返回第五章；轨迹执行问题返回第六章；训练与评测实验结果进入第九章。

## 7.14 当前设计基线

- Raw Verified Trajectory 是权威数据源，任何 SFT record 都是可重建的派生产物；
- Dataset Build 只消费 verified objects，不重新调用质量 Reviewer；
- harness-native trace 完整保留，公共 event index 只用于检索和统计；
- MVP 不构建内部 evaluation split，Verified Trajectories 先形成统一候选训练池；
- SFT serializer 绑定目标 model、tokenizer、chat template 和 tool schema；
- assistant 生成内容接受监督，conditioning 与 observations 使用 loss mask；
- 一条 SFT record 对应一条完整轨迹，overlength 默认排除而不截断；
- 后续 held-out evaluation 的核心对象是 executable Task Package；
- 每个 release、record、checkpoint 和 evaluation result 都保留完整 lineage；
- Dataset Release 使用不可变版本和 revocation record 管理演进。

## 7.15 待定问题

- 启动内部 evaluation 后采用 Recipe 还是 Source 作为隔离单位；
- 不同 harness tool schema 之间允许哪些受控转换；
- artifacts 的在线 locator、离线 bundle 和访问权限方案；
- Dataset Card 中许可证与来源限制的统一表达。

## 7.16 实现状态

第七章 MVP 已实现以下组成部分：

- [`dataset_release.py`](../../src/skt_repro/dataset_release.py) 实现 verified-only eligibility、精确去重、每 Task 上限、Raw registry、lineage、SFT serialization、统计、Dataset Card 和 release qualification；
- [`dataset-release-manifest.schema.json`](../../schemas/dataset-release-manifest.schema.json) 与 [`sft-record.schema.json`](../../schemas/sft-record.schema.json) 固定首版机器合同；
- [`ndvi-release-001`](../../examples/dataset-build-inputs/ndvi-release-001) 固定 dataset policy、目标 tokenizer、chat template 和 supervision policy；
- CLI 提供 `build-dataset` 与 `verify-dataset-release`；
- release 内保存 serializer 配置与实现源码快照，release digest 覆盖所有数据 payload；
- qualification 共检查 11 个 component，包括上游 source evidence、Task/Knowledge lineage、serializer snapshot、token/loss 重渲染和训练信息边界。

内部 executable evaluation 继续延后。当前实现没有调用新的 LLM judge，也没有把 evaluator、reference solution、Reviewer trace 或 post-termination outcome 加入训练消息。

## 7.17 首次实跑结果

Canonical release 位于 [`runs/chapter-07/scientific-agent-trajectories-0.1.0`](../../runs/chapter-07/scientific-agent-trajectories-0.1.0)，输入是第六章 NDVI Verified Trajectory `sha256:0582b2a6…b81325b`。构建命令为：

```bash
PYTHONPATH=src python -m skt_repro.cli build-dataset \
  runs/chapter-06/ale-ndvi-trajectory-001/verified-trajectory.json \
  --policy examples/dataset-build-inputs/ndvi-release-001/dataset-policy.yaml \
  --serializer-config examples/dataset-build-inputs/ndvi-release-001/serializer-config.yaml \
  --output runs/chapter-07/scientific-agent-trajectories-0.1.0
```

| 指标 | 结果 |
| --- | ---: |
| Verified Trajectories | 1 |
| SFT records | 1 |
| Native / public events | 39 / 42 |
| Output artifacts | 2 |
| SFT messages | 34 |
| Total tokens | 18,106 |
| Supervised tokens | 5,614 |
| Conditioning tokens | 12,492 |
| Supervised fraction | 0.310063 |
| Overlength excluded | 0 |
| Qualification components | 11 / 11 pass |

Release digest 为 `sha256:058419d4…6006e3d8`。Raw record 只保存 workspace-relative locators 与 digests；SFT record 保存完整 target rendering。全仓测试结果为 61 tests 与 9 subtests 通过，其中第七章覆盖真实 release 构建、schema、精确去重、role-aware loss mask、隐藏信息排除和消息篡改检测。
