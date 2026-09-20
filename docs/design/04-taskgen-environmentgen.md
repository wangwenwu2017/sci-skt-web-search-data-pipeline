# 第四章 TaskGen 与 EnvironmentGen

> 状态：MVP 已实现并完成首个真实 Candidate Task Package  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 4.1 章节目标

本章定义已接受科学知识如何被实例化为一个具体、可执行且可客观评价的 Candidate Task Package。TaskGen 负责选择任务模式、绑定输入和参数、形成 Task Card 与产物合同；EnvironmentGen 负责解析或构建隔离 runtime；同一次 authoring run 还要生成 verifier-only 的 reference solution、evaluator 和 lineage。

该设计借鉴 SKT 的 template-driven authoring：Task Author 读取 Skills 后填充固定任务包，并同时产出隔离环境、执行设置、reference solution 和 evaluator。SKT 随后的 rule-based verification、Agent verification 和 feedback-guided repair 由本项目第五章承接。[SKT Stage II: Task Synthesis](https://arxiv.org/html/2608.02287v1#S3.SS2)

本项目在 SKT 输入侧增加 Accepted Scientific Recipe、source assets 和 runtime evidence，使 Task Author 能够从来源支持的科学过程构造任务；任务是否依赖 Skill 以及固定 Solver 的 pass-rate 不属于核心 authoring 合同。

## 4.2 阶段合同与职责边界

```text
Accepted Knowledge Bundle
├── Scientific Recipe
├── Scientific Skills
└── Registry lineage

Task Author Request
Source Assets
Runtime Candidates
Authoring Policy
        ↓
Codex + scientific-task-author Skill
        ↓
Candidate Task Package
├── Solver-visible task surface
├── selected Skills
├── isolated runtime definition
├── hidden reference and evaluator
└── authoring evidence and lineage
        ↓
Task Verification / Repair
```

一次 Codex authoring run 只生成一个 Candidate Task Package。批量生成由 controller 分发多个独立任务，使每个候选拥有清楚的输入、输出、失败状态和 authoring trace。Accepted Knowledge Bundle 在 authoring 期间只读；Codex 只修改 candidate output 和临时分析目录。

第四章的终点是结构完整的 candidate。第五章负责在 fresh workspace 中验证 clean build、reference full credit、evaluator 有效性、语义忠实性与信息隔离。Task Author 可以为调试运行局部命令和 smoke check，但这些结果不构成正式 qualification。

## 4.3 Task Author 输入

### 4.3.1 `TASK_REQUEST.md`

每次 authoring 使用一个轻量请求文件固定 Recipe 和任务模式：

```yaml
---
name: crop-rotation-reproduction-001
recipe: crop-rotation-audit@0.1.0
mode: reproduction
---
```

必填内容只有：

- `name`：本次 candidate 的稳定请求名称；
- `recipe`：已通过 Knowledge Review 的 Recipe ID 与版本；
- `mode`：`reproduction`、`controlled_variable`、`multi_stage` 或 `diagnostic_recovery`。

正文可以按需提供目标数据范围、允许的参数区间、资源预算、网络策略、许可证限制或其他生成约束。具体输入、Skills 和 runtime 可以由 request 明确绑定，也可以交给 Task Author 从已授权候选中选择。

一个请求对应一个任务实例，不设置 `task_count`。需要从同一 Recipe 生成多个任务时，controller 创建多个 request，使每个实例可以独立重试、审核、丢弃和追踪。

### 4.3.2 完整逻辑输入

```text
Task Author Input
├── TASK_REQUEST.md
├── accepted-knowledge-bundle/
├── source-assets/                 # optional：可绑定的数据和文件
├── runtime-candidates/            # optional：Docker 或 Runtime Catalog entries
└── authoring-policy.md            # optional：网络、资源和安全限制
```

Task Author 使用 Recipe 确定任务族和验证意图，使用 Skills 理解执行方法，使用 source assets 绑定具体实例，使用 runtime candidates 决定复用或构建环境。Registry 用于确认产物版本、内容 digest 和 source lineage，不向 Solver 暴露。

输入资产必须来自 Source Bundle、受控数据生成器或可审计的外部 locator。Task Author 可以根据 Recipe 允许的输入空间进行采样、子集选择和来源支持的变换；会改变科学含义的合成规则必须在 Recipe 或 source 中有依据。

## 4.4 Codex + Scientific Task Author Skill

### 4.4.1 MVP 运行方式

MVP 由一个 Codex 任务加载 `scientific-task-author` Skill，同时完成 TaskGen 和 EnvironmentGen。这个选择减少 Recipe、input binding、runtime 和 evaluator 在多个 Agent 之间反复传递产生的语义损失，也便于用一条 authoring trace 追踪完整候选包。

建议的 Skill 结构为：

```text
scientific-task-author/
├── SKILL.md
└── references/
    ├── task-package-contract.md
    ├── task-modes.md
    └── environment-authoring.md
```

`SKILL.md` 保存每次 authoring 都需要的核心流程、知识边界、停止条件和第五章交接要求。Task Author 在实例化任务时读取 package contract 与当前 mode；只有需要构建或扩展 runtime 时才读取 environment authoring 指南，从而保持渐进式披露。

EnvironmentGen 在 MVP 中是 Task Author 的内部阶段。规模化后可以把镜像构建、依赖解析和安全检查拆成独立 Agent 或 builder service，只要继续消费 Environment Capability Request 并产生相同的 runtime artifacts，TaskGen 接口无需变化。

### 4.4.2 Authoring 主流程

```text
1. 读取 TASK_REQUEST.md、Recipe metadata 和 Recipe 正文
2. 确认任务模式以及可用 input/runtime candidates
3. 选择完成该实例所需的 Skills 并记录各自角色
4. 绑定具体输入、参数、控制变量和预期产物
5. 形成 Solver-visible Task Card 与 output contract
6. 解析 Environment Capability Request，复用或构建 runtime
7. 实现 verifier-only reference solution 与 evaluator
8. 写入 package manifest、lineage 和 authoring trace
9. 执行产物级自检并提交 Candidate Task Package
```

实际 authoring 可以在第 4 至第 7 步之间迭代。例如真实数据格式可能改变依赖选择，reference solution 的实现也可能暴露 output contract 中的歧义。最终产物仍需同时满足同一 Recipe、输入绑定和环境能力要求。

### 4.4.3 Agent 权限边界

Codex Task Author 可以：

- 读取 Accepted Knowledge Bundle、source assets 和 runtime evidence；
- 在 request 允许范围内选择、复制或生成具体输入；
- 写入 Candidate Task Package；
- 在临时目录执行数据检查、依赖探测和 authoring smoke tests；
- 通过受控 builder 构建 candidate Docker image。

Codex Task Author 不能修改 Accepted Recipe、Skills 或 Registry，也不能把 evaluator、reference solution 和 gold values 写入 Solver-visible surface。它不对自己的 candidate 作最终通过判断，不启动 Solver rollout，也不根据 skill/no-skill 结果修改任务。

如果 authoring 发现 Recipe 缺少科学规则、输入空间无法实例化或验证意图不足，应返回上游 blocking issue。Task Author 不在本阶段补写来源之外的知识。

## 4.5 四类任务实例化合同

任务模式控制实例化方式，不预设固定 Skill 数量。一个任务可以使用一个或多个 Skills，每个被选择的 Skill 都需要在 Recipe workflow 中具有明确角色。

| Mode | Task Author 绑定内容 | 主要产物 | 有效性条件 |
| --- | --- | --- | --- |
| `reproduction` | 一组具体输入、参数与直接科学目标 | 复现结果及其必要中间产物 | 方法、输入前提和输出关系均来自 Recipe |
| `controlled_variable` | baseline、一个允许变化的变量与保持不变的条件 | baseline、intervention 及比较结果 | 干预具有科学含义，控制条件明确，比较可客观验证 |
| `multi_stage` | 两个或更多有依赖关系的阶段 | 中间 artifacts、最终 artifact 和阶段关系 | 阶段间输入输出可以衔接，每个阶段有独立作用 |
| `diagnostic_recovery` | 一个可识别且可恢复的故障 | 诊断证据、修复后的结果和复检记录 | 故障来自已知 failure mode，恢复路径不会泄露答案 |

### 4.5.1 Reproduction

Reproduction 从 Recipe 输入空间中选择一个具体实例，要求 Solver 按完整科学过程产生可观察结果。Task Author 需要绑定实际数据、参数、输出位置和必要约束，同时保留方法中的单位、schema、公式和科学不变量。

任务不要求逐字重复 source 中的原始任务描述。可以改变数据实例和文件布局，只要科学目标、执行逻辑与验证关系保持忠实。输入已经包含原始答案或 source 结果时，需要移除会直接泄露目标产物的部分。

### 4.5.2 Controlled Variable

Controlled Variable 选择 Recipe 明确允许变化的一个变量，并固定其余声明条件。Task Author 需要同时定义 baseline、intervention、比较指标和有效范围，使 evaluator 能检查两个结果各自正确以及它们之间的关系。

变量变化可以作用于参数、数据子集、实验条件或处理策略。为制造差异而加入的干预需要保持原科学问题成立，且不会引入 Recipe 未描述的新方法。

### 4.5.3 Multi-stage Composition

Multi-stage Composition 把 Recipe 中具有真实依赖关系的多个阶段组合成一个任务。前一阶段的 artifact 应成为后一阶段的输入或约束，最终 evaluator 同时检查必要的中间结果与端到端结果。

阶段数量不直接代表难度。Task Author 只组合具有科学关系的步骤，避免通过无关文件转换、重复命令或人为拆分增加长度。多个 Skills 可以分别指导不同阶段，也可以由一个 Skill 覆盖多个紧密相关步骤。

### 4.5.4 Diagnostic Recovery

Diagnostic Recovery 从 Skill 或 Recipe 已知 failure mode 中选择一个可恢复问题，例如 schema 不匹配、CRS 错误、缺失依赖、参数不一致或损坏的中间状态。Task Author 在 input 或初始 workspace 中植入故障，并保留足够诊断证据。

Solver 需要识别问题、执行恢复动作并重新完成受影响的科学检查。故障必须局部、可复现且可安全恢复；evaluator 检查最终 artifact 和关键恢复结果，不要求 Solver 命中唯一命令序列。

### 4.5.5 难度的处理方式

MVP 将 mode、输入规模、阶段关系、控制变量和故障形态记录为 task characteristics，不用固定 Solver pass rate 决定任务是否有效。任务首先满足来源忠实、可执行和可评价条件。

后续若需要构建特定难度分布，可以对已验证任务运行独立 calibration rollouts，保存模型、harness、采样参数和经验通过率。该结果属于实验性任务属性，不改变 Scientific Recipe 或 Candidate Task Package 的语义合同。

## 4.6 EnvironmentGen

### 4.6.1 Environment Capability Request

Task Author 根据 Recipe、selected Skills、input formats 和 reference/evaluator 实现整理一份环境能力请求：

```text
Environment Capability Request
├── operating system and architecture
├── language runtimes
├── system and language packages
├── data-format and device support
├── working directory and commands
├── network policy
├── mount and visibility policy
└── resource and timeout limits
```

能力请求描述任务需要什么，具体 Docker image、package lock 和 image digest 由 EnvironmentGen 决定。reference solution 与 Solver 使用同一基础 runtime，evaluator 可以在任务结束后由 harness 以 verifier 权限运行。

### 4.6.2 Runtime 解析优先级

EnvironmentGen 按以下顺序选择实现：

1. 复用 Source Bundle 或 request 已提供的 Docker image；
2. 复用 Runtime Catalog 中满足大部分能力的受控基础镜像，并添加缺失依赖；
3. 生成新的 Dockerfile、dependency locks 和 healthcheck。

已有环境进入 candidate package 前要固定 image digest、入口命令和关键依赖信息。第五章仍会从干净状态重新 qualification。来源提供的 Docker 可以直接成为候选；ALE QEMU 只提供软件清单、配置和行为证据，不成为长期生产链的必需 runtime。

### 4.6.3 Runtime artifacts

```text
environment/
├── runtime.yaml               # required
├── Dockerfile                 # built 或 extended 时 required
├── locks/                     # optional：系统或语言依赖锁定
├── setup/                     # optional：受控初始化文件
└── healthcheck/               # required：环境能力与关键输入检查
```

`runtime.yaml` 至少描述：

- runtime 来源为 `reused`、`extended` 或 `built`；
- image reference 与不可变 digest，或本地 build context；
- architecture、working directory 和默认 shell；
- input、output、Skills 与 hidden assets 的 mount policy；
- network、resource、timeout 和环境变量策略；
- healthcheck 与任务入口命令。

依赖尽量固定到可复现版本；base image 不使用不可变性未知的浮动 tag 作为最终标识。输入默认只读，output workspace 可写，Recipe、Scientific Skills 和 hidden assets 不进入 Solver workspace。凭证和私有 registry token 由 builder 注入，不写入 Task Package。

### 4.6.4 构建与记录边界

Docker build、依赖下载和环境调试属于 authoring activity。相关命令、日志定位、最终 digest 和失败类别进入 authoring evidence。Solver rollout 从已经准备并通过 qualification 的 fresh runtime 开始，因此这些 authoring 操作不进入 Solver trajectory。

如果任务目标本身要求 Solver 创建、修复或配置科学软件环境，Task Author 应把待处理环境作为 visible task input，并为 Solver 提供受控的上层 sandbox。此时 Solver 的环境操作属于任务过程，生产侧基础 sandbox 的构建记录仍留在 authoring trace。

## 4.7 Candidate Task Package

### 4.7.1 目录合同

```text
candidate-task-package/
├── task.json                       # harness-facing package index
├── visible/
│   ├── TASK.md
│   ├── inputs/
│   ├── output-contract.md
│   └── execution-settings.yaml
├── skills/
│   └── <selected-skill-packages>/
├── environment/
│   ├── runtime.yaml
│   ├── Dockerfile                  # optional
│   ├── locks/                      # optional
│   ├── setup/                      # optional
│   └── healthcheck/
├── hidden/
│   ├── reference-solution/
│   ├── evaluator/
│   └── expected-artifacts/         # optional
└── authoring/
    ├── request.md
    ├── lineage.json
    └── trace.jsonl
```

`task.json` 是轻量索引，保存 task ID、candidate version、mode、Recipe 与 Skill IDs、各 surface 入口路径以及 reference/evaluator 命令。正文内容保留在对应文件中，manifest 不复制 Task Card、Recipe 或 Skill 内容。

### 4.7.2 Solver-visible surface

`visible/` 构成 Solver 可见任务材料，配合已验证 runtime 和允许工具执行。Recipe 与 Scientific Skills 仅供上游构造和审核：

- `TASK.md` 清楚说明目标、可用输入、需要提交的 artifacts 和任务约束；
- `inputs/` 保存具体数据和初始 workspace 内容，或保存由 harness 解析的稳定 asset binding；
- `output-contract.md` 描述必须产生的路径、格式、字段和公开科学要求；
- `execution-settings.yaml` 描述工作目录、允许的入口、网络状态、资源限制与终止条件；
- `skills/` 保存任务构造所依据的完整 Skill packages，仅供 authoring/review 使用，不挂载给正式 Solver。公开题目必须自包含，不得要求读取这些文件。

Task Card 提供完成任务所需的任务事实，不重复教授已由 Skills 承担的详细方法。Output contract 应足够明确，使多个有效实现都能提交可评分结果，同时避免暴露 hidden reference values 和 evaluator internals。

### 4.7.3 Hidden authoring assets

`hidden/` 只对 Task Author、Task Verifier 和 harness 开放：

- `reference-solution/` 提供一个完整可执行的正确实现；
- `evaluator/` 根据公开产物合同和 Recipe 科学不变量计算分数与诊断；
- `expected-artifacts/` 保存确有必要的 gold values、fixture 或语义比较基准。

Reference solution 和 evaluator 分开实现。Evaluator 优先检查数值关系、schema、单位、不变量和 artifact 语义，避免只接受 reference 的字节级副本。存在多种科学上等价的输出时，评分逻辑需要容纳允许的顺序、表示和数值容差。

Task Author 可以运行 reference 与 evaluator 辅助调试。只有第五章在 fresh workspace 中重建或启动环境、仅从 visible inputs 执行 reference，并确认满分后，candidate 才能转为 verified task。

## 4.8 Authoring Trace 与 Lineage

Authoring trace 记录可审计的操作和决策证据，不保存 Codex 的隐藏思维过程。建议的最小事件包括：

```text
knowledge_loaded
source_asset_inspected
task_mode_bound
input_bound
skill_selected
runtime_reused | runtime_extended | runtime_built
reference_materialized
evaluator_materialized
candidate_emitted
```

每条 JSONL event 保存时间、event type、相关 artifact IDs、产生或读取的路径以及简短 evidence。Docker build log、探测结果和大文件摘要可以由 locator 引用，避免把完整日志复制进 trace。

`lineage.json` 保存稳定关系：

- Task request ID 与生成器版本；
- Recipe ID、版本和 digest；
- 每个 selected Skill 的 ID、版本、digest 和任务角色；
- source asset IDs、版本、hash 或 locator；
- runtime source 与最终 image digest；
- authoring run ID。

Candidate package digest 由 controller 在 Agent 完成后根据完整文件 inventory 计算，并写入 `authoring/package-inventory.json`。Inventory 文件自身不进入 digest，避免自引用；`lineage.json` 不要求 Agent 预先填写一个尚未确定的 package digest。

Authoring trace 用于调试、审计和 repair 定位，不进入 SFT 数据。Solver trajectory 只记录 fresh rollout 中 Solver 实际看到的上下文、工具调用、结果和产物。

## 4.9 Authoring 自检、失败与交接

Task Author 在提交 candidate 前完成轻量自检：

- request、Recipe 和 selected Skills 的引用可以解析；
- visible、environment、hidden 和 authoring 入口已经生成；
- Task Card、output contract 与 evaluator 指向同一组目标 artifacts；
- runtime capability request 已被具体环境覆盖；
- hidden paths 没有进入 visible surface；
- authoring trace 和 lineage 能够定位本次使用的知识与资产。

自检发现的文件、路径和 materialization 问题可以在同一次 run 中修复。出现以下问题时停止 authoring，并返回最多三个 blocking issues：

| 问题 | 返回位置 |
| --- | --- |
| Recipe 或 Skill 缺少关键科学规则 | Knowledge Repair |
| 没有可绑定且符合前提的输入 | Source/Asset Resolution 或 Knowledge Repair |
| 当前目标无法形成客观 evaluator | Knowledge Repair 或重新选择 task mode |
| runtime 构建在预算内持续失败 | Environment authoring failure |
| package 文件或 Task Card 实现缺陷 | Task Author retry |

成功的 Candidate Task Package 进入第五章 Task Verification。第五章可以把结构化 diagnosis 交给 TaskRepair；修订后的完整 package 重新执行 qualification。Trajectory failure 不回写本章产物，除非第五章确认它揭示了任务包本身的缺陷。

## 4.10 与 SKT 的继承和调整

本章直接继承 SKT 的四个关键思想：固定 Task Package 模板、隔离 runtime、visible/hidden 信息面、Task Author 与后续 Verifier/Repair 的反馈闭环。SKT 论文将 instruction、runtime、execution settings、evaluator 和 reference solution 作为同一个 task package，并要求 verifier 能同时查看 visible 与 hidden assets。[SKT Task Package and Verifier Inputs](https://arxiv.org/html/2608.02287v1#Sx2.SS1)

本项目根据科学数据生成目标作出以下调整：

- TaskGen 从 Accepted Recipe、Skills 和 source assets 出发，保留 `Source → Knowledge → Task` lineage；
- EnvironmentGen 显式支持已有 Docker 复用、受控扩展和从能力要求构建；
- 四类 task modes 来自 Recipe 中的科学变化空间；
- task validity 关注来源忠实、可执行和可评价；
- paired skill/no-skill rollout 与固定 Solver 难度 Gate 留作可选实验；
- authoring trace 与 Solver trajectory 完全分离。

## 4.11 已确认结论

- 一次 Codex + `scientific-task-author` Skill run 生成一个 Candidate Task Package；
- TaskGen 与 EnvironmentGen 在 MVP 中由同一个 Agent 完成，环境构建可以在规模化时拆分；
- `TASK_REQUEST.md` 固定 Recipe 和 task mode，其余输入与约束保持开放；
- 支持 `reproduction`、`controlled_variable`、`multi_stage` 和 `diagnostic_recovery`；
- 已有 Docker 优先复用并固定 digest，缺失环境时生成 Dockerfile、locks 和 healthcheck；
- Candidate Task Package 同时包含 visible、Skills、environment、hidden 和 authoring surfaces；
- reference solution 与 evaluator 在 authoring 阶段生成，在第五章执行独立 qualification；
- authoring trace 记录操作与证据，不进入 Solver trajectory；
- Task Author 不修改 Accepted Knowledge，也不运行 skill-dependence 准入检查。

## 4.12 待定问题

- Runtime Catalog 的索引、缓存和 image provenance 格式；
- Docker builder 的网络、镜像仓库、资源和并发策略；
- source assets 复制、只读挂载和外部 locator 的统一实现；
- evaluator 的标准进程接口与部分分数表示方式。

## 4.13 MVP 实现与产物

第四阶段实现集中在以下组件：

- `pipeline-skills/scientific-task-author/`：渐进读取 Recipe、Skills、task mode 和 environment contract 的项目级 Task Author Skill；
- `schemas/task-package-index.schema.json`：只保存 Task ID、知识 binding、surface 路径和三个命令入口的轻量 `task.json` 合同；
- `schemas/task-runtime.schema.json`：保存镜像、mount、网络、资源和 timeout 的轻量 `runtime.yaml` 合同；
- `src/skt_repro/authoring.py`：处理 accepted-input resolution、隔离快照、fresh Codex 调用、package qualification、Skill 字节检查、inventory 和恢复式 requalification；
- `author-task`：从 extraction run、Knowledge Review 和一个 Task Author Input 生成 Candidate Task Package；
- `verify-candidate-task`：检查 package 结构、surface、runtime、trace 和内部 binding；
- `finalize-authored-task`：Agent 已成功但 controller 合同发生修订时，保留旧报告、重新检查并冻结 inventory，不重跑或修改 Task Author 的科学产物。

当前机械 qualification 只确认 package structure 与 accepted-knowledge binding。它不会把 reference 满分或 evaluator 自测结果提升为正式 Task Verification verdict。

## 4.14 首个真实输入

首个 request 位于 `examples/task-author-inputs/ndvi-reproduction-001/`，绑定：

- Recipe：`sentinel-2-ndvi-zonal-statistics@0.1.0`；
- mode：`reproduction`；
- 两个 accepted Scientific Skills；
- 一个固定 seed 的 controlled geospatial fixture；
- Linux `amd64`、无网络 Solver 和 30 分钟资源策略。

本地 ALE checkout 和现有 QEMU 资产中没有可直接读取的 Windows NDVI TIFF 与 Shapefile，因此 fixture 根据 Recipe 允许的输入空间重新生成。它包含六波段 EPSG:3857 float32 raster、EPSG:4326 polygons、三个无效像元、数值外观不同的字符串 ID、边界敏感 polygon 和一个空 zone。`ASSET.md`、generator、seed、每个 materialized file hash 与 `original_ale_bytes: false` 共同固定 provenance。Task Author 在 visible Task Card 中也明确说明这些字节来自 controlled generator。

Fixture 重复生成后，六个数据文件的 byte-level hashes 完全一致。它验证 TaskGen 对 source-supported input space 的实例化能力，不冒充 ALE 原始隐藏数据。未来获得原始输入后，可以替换 source asset binding，并复用同一个 request、Skill 和 authoring controller。

## 4.15 首次真实 authoring run

Canonical 命令为：

```bash
PYTHONPATH=src python3 -m skt_repro author-task \
  runs/chapter-02/ale-ndvi-zonal-statistics-004 \
  --review-run runs/chapter-03/ale-ndvi-knowledge-review-001 \
  --request examples/task-author-inputs/ndvi-reproduction-001 \
  --output runs/chapter-04/ale-ndvi-task-authoring-002 \
  --model gpt-5.6-sol \
  --reasoning-effort high
```

Task Author 使用 fresh `gpt-5.6-sol/high`，运行 516.899 秒，生成一个 `reproduction` Candidate Task Package。产物包括：

- 面向 Solver 的 `TASK.md`、实际 GeoTIFF/Shapefile inputs、output contract 和 execution settings；
- 两个与 accepted knowledge 逐字节一致的 Scientific Skill packages；
- 基于固定 `python:3.12.10-slim-bookworm` digest 的 Dockerfile、Python dependency lock、system dependency 和 healthcheck；
- verifier-only reference solution 与独立 evaluator；
- request、source/knowledge/runtime lineage、authoring trace、environment smoke evidence 和 package inventory。

Agent 输出后的第一次 Docker smoke 暴露了 slim image 缺少 `libexpat.so.1`。Environment authoring 在同一个 candidate 中加入 `libexpat1=2.5.0-1+deb12u2`，固定基础镜像 digest，再在全新输出目录和 `--network none` 下重复执行：

1. healthcheck 通过；
2. reference 生成 `ndvi.tif` 与 `polygon_ndvi_stats.csv`；
3. evaluator 的八类结构与科学检查全部通过，`score=1.0`；
4. 最终 local image digest 为 `sha256:412ef8db08219867d33516496a419ac3fa5b59d991cd88afc37323514e2f507e`；
5. 最终 Candidate Task Package digest 为 `sha256:3bebe31baeea85ff64a295a39654da416736856a13d663f834461b333b363f9a`。

Smoke 的失败、修复、最终镜像、依赖版本、reference artifact hashes 和 evaluator report 保存在 `authoring/environment-smoke.json`。这些证据证明第四阶段产物具备进入第五章的条件；第五章仍会执行 fresh clean build、reference full credit、negative cases、信息隔离和语义审核。

外层网络沙箱导致 `ale-ndvi-task-authoring-001` 在连接模型前失败，Agent 没有生成 candidate，输入保持不变。该 run 原样保留用于基础设施审计；`002` 是 canonical 成功产物。

## 4.16 当前结论

Task Author 输入、两个轻量 Schema、Codex + Skill 调用、controlled asset materialization、Docker EnvironmentGen、visible/hidden package、reference、evaluator、authoring trace、lineage 和 package digest 已完成一次真实 vertical slice。第四阶段的终点保持为 immutable Candidate Task Package；下一步进入第五章，把现有 authoring smoke 转为独立、可重复并带负例的 Task Verification / Repair 流程。
