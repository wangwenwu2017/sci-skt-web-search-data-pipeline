# 第一章 总体流程

> 状态：讨论基线  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 1.1 项目目标

本项目建设一条从科学 Benchmark 或异构科学材料到可执行科学任务和高质量 Agent 轨迹的数据生产链。上游可以直接提供论文、论文配套数据、科研软件、已有运行环境或 ALE Task Card，也可以只提供一个 Benchmark、Task Card 集合或公开任务提案，由 Source Scout 自动寻找独立的论文、软件和数据并组成 Source Bundles。

Heta 负责把原始材料整理成统一的 Scientific Recipe 和 Scientific Skills；TaskGen 根据这些知识产物绑定具体输入、参数和运行环境，生成带有 reference solution 与 evaluator 的可执行 Task Package；通过验证的任务进入 fresh rollout；正确、完整且符合科学过程的执行轨迹被保留为训练数据或评测数据。

项目关注三次连续转换中的语义保持：

| 转换 | 核心问题 |
| --- | --- |
| Raw Source → Recipe / Skills | 是否忠实抽取了原始知识 |
| Recipe / Skills → Task Package | 是否忠实地将知识实例化为可执行、可评价的任务 |
| Task Package → Trajectory | Agent 是否正确完成任务并产生完整执行过程 |

Recipe 和 Scientific Skills 在链路中承担上游任务构造与审核的知识载体角色。正式 Solver 不接收 Campaign、Recipe、Scientific Skills、参考解或评分器，只在已验证的任务容器内根据公开题目、输入和输出合同执行、观察结果、修改代码或参数并重新运行。题目必须自包含，不能依赖 Solver 读取上游知识包。paired skill/no-skill rollout 可以在研究 Skill 增益、构建 SkillEval 或分析模型能力时启用，不进入核心数据生产流程。

## 1.2 端到端链路

```text
Benchmark / Task Card / Task Proposal
                         ↓
          Scientific Benchmark Source Scout
                         ↓
             Locator Source Bundle Selection
                         │
Paper / Raw Data / Software / Runtime / ALE Task Card
                         ↓
             Source Materialization
                         ↓
                    Heta Extraction
                         ↓
          Candidate Scientific Knowledge Bundle
               ├── Scientific Recipe
               ├── Scientific Skills
               └── Production Registry
                         ↓
                  Knowledge Reviewer
               ├── Knowledge Validity
               └── Task Generation Suitability
                         ↓
             Accepted Scientific Knowledge Bundle
                         ↓
               TaskGen + EnvironmentGen
                         ↓
                Executable Task Package
                         ↓
                 Task Verify / Repair
                         ↓
                   Fresh Rollout
                         ↓
              Trajectory Verification
                         ↓
        Verified Trajectory Dataset / Evaluation Set
                         ↓
                     SFT / Analysis
```

这条链路借鉴 SKT 的 Task Synthesis、Task Verification、Fresh Rollout 和 Trajectory Verification，并在其上游增加 Heta 知识形成层。SKT 接收已有 Agent Skills；本项目还要处理论文、数据和软件等原始来源，因此需要显式解决知识抽取、来源忠实性和 Scientific Recipe 形成问题。

## 1.3 四层核心产物

系统的数据对象分成 Source、Knowledge、Task 和 Trajectory 四层。Benchmark 与 Source Discovery Request 是 Source 层之前的检索输入，不成为 Solver-visible 科学知识。每层只承担本阶段稳定的信息，具体实例信息随着流水线逐步绑定。

| 层级 | 核心产物 | 主要职责 |
| --- | --- | --- |
| Source | Source Bundle | 固化原始文件、版本、许可、hash、解析结果和运行证据 |
| Knowledge | Scientific Recipe、Scientific Skills、Registry | 保存完整科学过程、可复用能力和来源 lineage |
| Task | Executable Task Package | 绑定具体输入、参数、环境、Task Card、reference solution 和 evaluator |
| Trajectory | Verified Trajectory | 保存完整执行、工具调用、结果 artifacts、验证结论和 lineage |

一个 Knowledge Bundle 包含一个 Scientific Recipe，以及该 Recipe 引用的一个或多个 Scientific Skills：

```text
knowledge-bundle/
├── recipes/<recipe-name>/RECIPE.md
├── skills/<skill-name>/SKILL.md
│   ├── scripts/       # optional
│   ├── references/    # optional，Task Author / Reviewer 按需读取
│   └── assets/        # optional
└── registry/
    ├── recipes/<recipe-name>.json
    └── skills/<skill-name>.json
```

Scientific Skill 遵循 Agent Skills 的 file-first 格式。Scientific Recipe 使用相似的 Markdown 主体和轻量 frontmatter，描述完整科学过程、任务输入空间、Skill 协作、产物合同、验证意图、难度变化和环境能力。Source provenance、抽取工具、内容 hash 和审核状态保存在 registry，不进入 Solver workspace。

## 1.4 Benchmark-guided Source Discovery

Scientific Benchmark Source Scout 是一个 Codex + Pipeline Skill 阶段。它读取用户给出的 Benchmark、单个 Task Card、Task Card 集合或公开任务提案，提取科学操作、输入类型、交付物、运行方式和 verifier 形态，再寻找能够独立支持新任务的论文、代码、数据、科学软件和实践证据。

用户可以指定 Source Bundle 数量、领域比例、相似度比例、年份、开放访问、软件、数据和 runtime 条件。缺省情况下，每个明确的 benchmark task 目标为 12 个 Bundle，并采用 70% direct、20% variant、10% frontier 的软配比。Agent 会超额检索并保留达到质量门槛的候选；数量不足会形成明确的 qualification failure，不使用不相关来源补数。

Source Scout 只合并真实的来源实体重复，包括相同 DOI、规范化 GitHub 仓库、数据集 accession、fork、镜像和同一项目的换名记录。不同团队在不同数据、软件或科学条件上训练相似能力的来源可以同时保留。

正式产物包括：

```text
candidate-source-selection/
├── REPORT.md
├── catalog.jsonl
├── selection.yaml
└── source-bundles/<domain>/<bundle-id>/SOURCE.md
```

该阶段输出的是 locator-only Source Bundles。确定性 qualification 检查数量、合同、实体去重、Benchmark 资产隔离、GitHub 仓库和固定 commit；随后 Source Materialization 才下载有界的官方代码与文档，记录 hash 并形成可进入 Heta 的 Source Bundle。已有合格 `selection.yaml` 时可以跳过 Agent 检索，直接进入 Materialization。

Benchmark 的输入数据、答案、测试、隐藏 evaluator、reference solution、oracle 轨迹和近似复刻仓库不得成为 Source Bundle。公开任务描述只用于理解任务形态；科学来源必须能够脱离原 benchmark 实例支持新的任务生成。

## 1.5 Heta 知识形成

Heta 接受不同形态的原始材料，并将其中与科学执行有关的信息转化为 Recipe、Skills 和 supporting references。不同来源可以使用不同 parser 和 extractor，但下游只消费统一的 Knowledge Bundle。

Heta 的主要职责包括：

- 识别原始材料中的科学目标、输入、参数、方法、输出和验证线索；
- 区分完整科学流程与可复用局部能力；
- 形成一个 Recipe 和相关 Skills；
- 将 Task Author 和 Reviewer 需要的补充科学知识放入 Skill references；
- 将 Task Author 需要的构造知识放入 Recipe 或 Recipe references；
- 保存来源定位和转换 lineage；
- 对无法确认、存在冲突或来源不足的内容显式保留不确定性。

对于 ALE，Task Card 是第一批 raw source。已有 QEMU 环境可以用于观察正确行为、补充依赖信息、验证数据和软件关系。长期生产模块从 Knowledge Bundle、输入资产和 Runtime Catalog 生成独立任务环境，不依赖 ALE QEMU 作为最终 runtime。

## 1.6 Knowledge Reviewer

Knowledge Reviewer 是一个具备工具使用能力的 LLM Agent。它一次读取原始材料和 Candidate Knowledge Bundle，做出两个独立判断。

### 1.6.1 Knowledge Validity

该判断回答：Recipe、Skills 和 references 是否可以作为原始材料的可信知识表达。

Reviewer 重点检查：

- 核心方法、公式、条件和步骤是否得到 source 支持；
- 是否存在改变科学含义的遗漏、矛盾或虚构；
- 输入、过程和输出是否逻辑连贯；
- Recipe 与 Skills 的抽象层次是否合理；
- references 是否与正文一致；
- 知识产物是否混入实例隐藏答案和 evaluator 信息，以及公开任务是否泄露这些信息。

### 1.6.2 Task Generation Suitability

该判断回答：当前 Knowledge Bundle 能否忠实地实例化成可用科学任务。

Reviewer 重点检查：

- 是否可以绑定具体数据、参数、输入和输出；
- 是否存在可获得或可构建的运行环境；
- 是否能够生成客观 evaluator；
- 任务目标、变化方式和验证策略是否来自已有知识；
- TaskGen 是否需要临时发明新的科学规则才能完成任务设计。

Reviewer 输出 `accept`、`revise` 或 `reject`。它只报告会影响科学正确性、任务构造或验证有效性的阻塞问题，不评价措辞偏好，也不要求补充无实际作用的内容。普通情况使用一次 Agent review；来源冲突、高风险内容或明显不确定性可以触发第二次独立审核或人工确认。

文件能否解析、引用路径是否存在、hash 是否一致等检查属于基础读写约束，由基础设施自动完成，不作为知识质量判断的独立阶段。

## 1.7 TaskGen 与 EnvironmentGen

TaskGen 读取一个已接受的 Recipe、相关 Skills、具体 source assets 和目标任务模式，将知识实例化为 Task Package。EnvironmentGen 可以是同一个 Codex Agent 的内部阶段，也可以在后续规模化时拆成独立 Agent。

TaskGen 负责：

- 绑定具体数据、参数、控制变量和输出位置；
- 生成接近 ALE Task Card 的清晰任务说明；
- 记录任务构造所依据的 Skills，仅供上游构造、审核与 lineage 追踪；
- 生成或引用 reference solution；
- 生成 hidden evaluator；
- 记录本次任务与 Recipe、Skills 和 source 的 lineage。

EnvironmentGen 负责：

- 判断已有 Docker image 是否可以直接复用；
- 在缺少环境时根据软件与能力要求生成 Dockerfile 和 setup；
- 固化依赖版本、基础镜像 digest 和构建结果；
- 生成 healthcheck；
- 保证 inputs 只读、outputs 可写、hidden assets 与 Solver 隔离。

已有环境可以直接复用并重新执行 qualification。环境生成过程保存在 authoring trace 和 environment report 中。只有当构建环境本身属于 Solver 任务目标时，这部分操作才进入 Solver trajectory。

## 1.8 Task Package 与任务验证

Task Package 区分 Solver-visible、authoring/review-only 和 verifier-only 信息面；包内存在文件不代表会向 Solver 挂载：

```text
task-package/
├── task.json
├── visible/
│   ├── TASK.md
│   ├── inputs/
│   ├── execution-settings/
│   └── output-contract.md
├── skills/                  # authoring/review-only，不挂载给 Solver
├── environment/
├── hidden/
│   ├── evaluator/
│   ├── reference-solution/
│   └── expected-artifacts/
└── authoring/
    ├── lineage.json
    └── trace.jsonl
```

Task Verification 检查知识是否被忠实实例化，以及当前任务是否真正可执行、可评价：

- 数据与参数满足 Recipe 和 Skills 的前提；
- `TASK.md` 明确说明目标、输入、输出和限制；
- Docker 环境可以 clean build 或从受控镜像启动；
- reference solution 在 fresh workspace 中正常执行并获得满分；
- evaluator 能拒绝空输出和代表性的错误结果；
- visible 内容不泄露 gold values、reference solution 或 evaluator internals；
- 任务变化和难度设计没有超出 source-supported knowledge。

失败任务进入 TaskRepair。知识层问题回流到 Heta 或 Knowledge Repair；Task Card、环境、reference 和 evaluator 问题在 Task Package 内修复。修复后重新执行完整验证。

## 1.9 Fresh Rollout 与轨迹验证

通过 Task Verification 的任务在全新会话和 workspace 中执行。每次 rollout 不继承前一次失败轨迹、evaluator 结果或 verifier feedback。系统记录 model messages、tool calls、tool results、terminal status 和输出 artifacts。

Trajectory Verification 关注：

- evaluator 结果满足任务要求；
- Agent 正常、完整地结束执行；
- 工具调用和文件操作记录结构完整；
- 关键数据处理、参数和科学决策符合 Task 与 Recipe；
- 输出 artifacts 存在、可读取并具有稳定 hash；
- trajectory 可以追溯到 source、Recipe、Skills、Task、environment、model 和 harness。

正式 Solver 的 workspace、挂载与轨迹应确认没有 Recipe 或 Scientific Skills 暴露。Reviewer 可以读取知识包核对科学过程，但不向 Solver 传递知识内容或审核反馈。

## 1.10 数据集输出

通过验证的轨迹进入统一数据集。完整原始轨迹保持 harness-native tool protocol，避免过早丢失执行细节。SFT serializer 根据目标模型和 harness 生成训练记录，并明确区分 conditioning tokens 与 assistant-generated tokens。

数据集至少保留：

- source、Recipe、Skill 和 Task IDs；
- 所有关键 artifact 和环境 digest；
- teacher model、harness、attempt 和 fresh-context 标识；
- 完整消息和工具事件；
- evaluator 结果和 trajectory verdict；
- 上游 Recipe / Skill lineage 与 Solver 信息面隔离证据；
- SFT loss mask 和序列化版本。

同一条生产链可以输出两类数据：一类用于 SFT，另一类使用独立 source、Recipe 或 Task split 形成 held-out evaluation set。

## 1.11 总体设计原则

当前总体方案遵循以下原则：

1. **忠实性优先**：每次转换都保持原始知识和任务语义；
2. **文件优先**：Recipe 和 Skill 使用 Agent 易读、易编辑的 Markdown 产物；
3. **LLM 主导判断**：语义、抽象和任务可行性由具备工具能力的 Reviewer Agent 综合判断；
4. **客观结果验证**：Task 与 Trajectory 使用可执行 evaluator 检查；
5. **可见面隔离**：Solver 公开任务材料、authoring knowledge 和 verification secrets 分开管理；
6. **问题回到所属层**：知识、任务、环境和 evaluator 问题分别修复；
7. **完整 lineage**：source、knowledge、task、environment 和 trajectory 全程可追踪；
8. **按需复杂化**：普通样本走短链路，冲突、高风险和不确定样本才升级审核；
9. **实现可演进**：MVP 可以由一个 Codex 配合 Skills 完成，接口稳定后再拆分组件。
10. **检索与生成解耦**：Benchmark 指导来源发现，Source Bundle 经过独立物化和知识审核后才进入任务生成。

## 1.12 与后续章节的关系

本章只定义总体方向。各阶段的正式边界和实现细节分别维护在后续章节中：

- [Scientific Recipe 与 Scientific Skill](02-scientific-knowledge.md)
- [Heta 抽取与 Knowledge Reviewer](03-heta-knowledge-review.md)
- [TaskGen 与 EnvironmentGen](04-taskgen-environmentgen.md)
- [Task Package 与 Verify/Repair](05-task-package-verification.md)
- [Rollout 与 Trajectory Verification](06-rollout-trajectory-verification.md)
- [Dataset、SFT 与 Evaluation](07-dataset-sft-evaluation.md)
