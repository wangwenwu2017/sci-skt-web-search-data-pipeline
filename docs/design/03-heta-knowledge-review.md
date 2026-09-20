# 第三章 Heta 抽取与 Knowledge Reviewer

> 状态：MVP 已实现并完成首次独立 Knowledge Review  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 3.1 章节目标

本章定义 Heta 产生 Candidate Knowledge Bundle 后的审核逻辑。Knowledge Reviewer 需要快速判断两件事：当前 Recipe、Skills 和 references 是否忠实表达原始材料，以及这些知识是否足以生成可执行、可客观评价的科学任务。

MVP 采用一个 Codex 任务加载 `knowledge-reviewer` Skill 完成审核。Codex 可以渐进读取文件、检索来源并运行必要的只读分析，在一次 review 中输出两个独立结论。普通样本通过一次审核完成流转；来源冲突、高风险内容或明显不确定性再按需升级。

## 3.2 在总体流程中的位置

```text
Raw Source Bundle
        ↓
   Heta Extraction
        ↓
Candidate Recipe + Skills + References
        ↓
   Knowledge Reviewer
        ├── A. Knowledge Validity
        └── B. Task Generation Suitability
        ↓
Accepted → TaskGen
Revise   → Knowledge Repair
Reject   → Archive / Discard
```

Knowledge Reviewer 审核 `Source → Knowledge` 的转换结果，并判断 Knowledge 是否具备进入 TaskGen 的条件。生成后的 instruction、Docker、reference solution 和 evaluator 由 Task Verification 负责；rollout 的结果与执行过程由 Trajectory Verification 负责。

## 3.3 设计原则

### 3.3.1 一次阅读，两个判断

Recipe、Skills、references 和 source 彼此关联。一个 Reviewer 在同一上下文中完成两个判断，可以避免重复加载材料，也能综合理解完整科学过程、Skill 拆分和任务生成空间。

两个 judgment 必须分别给出 verdict。Knowledge 内容可能忠实可靠，但缺少数据、环境或客观验证方式，因此暂时不适合进入 TaskGen。这种样本可以保留在 Knowledge archive 中，不应因为 taskability 不足而被标记为错误知识。

### 3.3.2 只报告实质问题

Reviewer 只关心会产生实际影响的问题。一个问题满足以下任一条件时才具有阻塞性：

- 可能改变科学结论、计算结果或关键操作；
- 使输入、步骤和输出之间无法成立；
- 使 TaskGen 必须补写来源中不存在的科学规则；
- 使任务无法运行或无法客观验证；
- 使 Solver-visible 内容泄露 hidden answer 或 evaluator 信息。

措辞风格、标题偏好、非必要扩展、可有可无的示例和不影响执行的细节不构成阻塞问题。Reviewer 每次最多报告三个 blocking issues，使 repair feedback 保持集中。

### 3.3.3 信任 Agent 的整体语义判断

Reviewer 使用原始材料和知识产物做整体判断，不依赖机械字段打分。公式、表格、代码、数据或软件行为需要进一步确认时，Agent 可以调用相应工具。Reviewer 先读取 Recipe 和 Skill metadata，再按需打开 Skill 正文、references 和 source locators，避免一次加载所有材料。

### 3.3.4 基础读写约束留在基础设施

Markdown frontmatter 能否解析、文件路径是否存在、JSON 能否读取和 hash 是否一致，属于 loader 和 registry 的基础行为。它们不形成 Knowledge Reviewer 的质量维度。输入损坏时系统报告运行错误并停止 review；成功解析也不代表知识获得认可。

### 3.3.5 不预判 Skill 依赖性

Reviewer 不判断通用模型是否已经掌握 Skill 内容，也不要求任务在无 Skill 条件下失败。Skill 在本系统中承担知识组织和执行指导职责。paired skill/no-skill rollout 只在研究 Skill 增益、构建专门 benchmark 或分析模型能力时启用。

## 3.4 Reviewer 输入

一次 review 的逻辑输入包括：

```text
Source Bundle
├── source manifest
├── paper / data / software / task card
├── available source locators
└── runtime evidence（如有）

Candidate Knowledge Bundle
├── RECIPE.md
├── selected SKILL.md files
├── references / scripts / assets
└── registry source records

Review Context
├── review policy version
├── target task domain（可选）
└── previous blocking findings（仅 repair 后复审）
```

Extractor 的内部推理过程默认不提供给 Reviewer，减少对生成结论的锚定。Reviewer 可以看到稳定 source locators 和转换产物，并自行检查关键内容。复审时可以附带上一轮 blocking findings，帮助确认问题是否解决。

## 3.5 Judgment A：Knowledge Validity

Knowledge Validity 回答：

> 当前 Recipe、Skills 和 references 能否作为原始材料的可信、连贯且边界合理的知识表达？

Reviewer 从四个方面综合判断。

### 3.5.1 来源忠实性

- 核心方法、公式、条件、参数和步骤得到 source 支持；
- 合理归纳没有改变原始科学语义；
- 没有模型自行补出的关键规则或结论；
- 没有遗漏会改变执行结果的重要前提；
- 来源中存在冲突时，产物没有静默选择某一结论。

Reviewer 无需逐句核对说明性文字，重点关注会改变 Agent 行为、Task 构造或最终结果的内容。

### 3.5.2 内部逻辑

- 输入能够支持声明的方法；
- 方法步骤的顺序和依赖关系成立；
- 输出与目标一致；
- 公式、单位、字段和参数在不同文件中保持一致；
- `SKILL.md`、Recipe 和 references 不存在实质矛盾。

### 3.5.3 抽象质量

- Recipe 表达完整科学过程或任务族；
- Skill 表达可复用局部能力；
- Task 特定输入、固定路径和答案没有进入通用 Skill；
- Skill 没有被拆成缺少独立意义的通用操作；
- 多个 Skills 的职责能够区分，并共同覆盖 Recipe 所需过程。

### 3.5.4 信息边界

- Scientific Skill 只包含来源支持的可复用科学知识与资源，供 Task Author 和 Reviewer 使用；不向正式 Solver 暴露；
- Task Author 使用的构造策略留在 Recipe 或 Recipe references；
- provenance、抽取和审核信息保存在 registry；
- evaluator、reference solution、gold values 和 hidden answers 没有进入 Skill。

### 3.5.5 Verdict 语义

| Verdict | 含义 |
| --- | --- |
| `accept` | 没有发现会影响忠实性、科学逻辑或知识边界的问题 |
| `revise` | 知识整体可用，但存在明确且可修复的阻塞问题 |
| `reject` | 来源不足、核心内容不可信，或当前抽象无法在合理修改内成立 |

## 3.6 Judgment B：Task Generation Suitability

Task Generation Suitability 回答：

> 当前 Knowledge Bundle 是否包含足够信息，使 TaskGen 能够忠实地产生具体、可执行、可客观评价的科学任务？

Reviewer 从四个方面综合判断。

### 3.6.1 可实例化

- 能够确定或构造具体输入数据；
- 能够绑定必要参数和控制变量；
- 能够声明清楚的目标产物；
- Recipe 的输入空间至少支持一个有意义的任务实例。

同一个 Recipe 能否产生多个变体会影响数据扩展价值，但不作为单个有效任务的硬性前提。

### 3.6.2 可执行

- 所需软件、数据和系统能力可以获得；
- 已有 runtime 可以复用，或 EnvironmentGen 能够合理构建环境；
- 方法没有依赖无法访问、无法授权或无法模拟的关键外部条件；
- 输入输出能够在受控 workspace 中完成。

### 3.6.3 可客观验证

- 最终结果具有可观察 artifact、数值或行为；
- 能够生成确定性检查、隐藏 reference 或其他客观 evaluator；
- evaluator 有机会区分正确、部分正确和错误结果；
- 验证目标与原始科学目标一致。

### 3.6.4 忠实任务化

- Task 的目标和约束能够从 Recipe、Skills 或 source 得到支持；
- 参数变化、控制变量和故障设计具有来源依据或合理科学含义；
- TaskGen 无需临时发明新的科学规则；
- 为增加难度所做的变化不会改变原始任务的科学性质。

Reviewer 在这一阶段不估计模型通过率，也不判断具体 Task Package 的 instruction、Docker 或 evaluator 实现质量。这些内容在 TaskGen 完成后验证。

### 3.6.5 Verdict 语义

| Verdict | 含义 |
| --- | --- |
| `accept` | 已有知识足以生成至少一个忠实、可执行、可客观评价的 Task |
| `revise` | 补充或调整 Recipe、Skill、reference 或 source binding 后可以进入 TaskGen |
| `reject` | 当前来源或方法缺少任务化所需的输入、环境或客观验证条件 |

## 3.7 Reviewer 输出

Reviewer 返回一份简洁、机器可读的 `knowledge-review.json`。不采用综合分数，避免数字掩盖阻塞问题。

```json
{
  "knowledge_validity": {
    "verdict": "accept",
    "reason": "The Recipe and Skill preserve the source workflow and geospatial invariants.",
    "blocking_issues": []
  },
  "task_generation_suitability": {
    "verdict": "revise",
    "reason": "The workflow is executable, but the current Recipe does not define an objectively checkable output relationship.",
    "blocking_issues": [
      {
        "target": "recipe",
        "issue": "The output contract does not identify which result can be checked independently.",
        "impact": "TaskGen cannot construct a reliable evaluator.",
        "suggested_action": "Describe a source-supported structural or numerical invariant for the output."
      }
    ]
  },
  "routing": "repair_recipe"
}
```

每个 judgment 包含：

- `verdict`：`accept`、`revise` 或 `reject`；
- `reason`：一段能够独立解释结论的简短理由；
- `blocking_issues`：零到三个阻塞问题。

每个 blocking issue 包含：

- `target`：`recipe`、`skill:<name>`、`reference:<path>`、`source_binding` 或 `runtime_evidence`；
- `issue`：具体问题；
- `impact`：为什么会影响知识或任务生成；
- `suggested_action`：修复方向，不直接代写科学内容。

## 3.8 流转与 Repair

两个 judgment 独立保存，系统根据组合结果决定流转：

| Knowledge | Taskability | Routing |
| --- | --- | --- |
| accept | accept | `release_to_taskgen` |
| revise | 任意 | `repair_knowledge` |
| reject | 任意 | `reject_or_manual_review` |
| accept | revise | `repair_recipe_or_binding` |
| accept | reject | `archive_non_taskable` |

Knowledge Repair 接收原始 Source Bundle、Candidate Knowledge Bundle 和 blocking findings，只修改明确受影响的 Recipe、Skill、reference 或 binding。Reviewer 不直接编辑产物。修复完成后重新进行一次完整的双 judgment review，避免局部修改引入新的语义问题。

普通样本保持短链路：一次 extraction、一次 review、一次 TaskGen。只有 `revise`、来源冲突、高风险内容或 Reviewer 明确表示无法判断时，才增加 repair、第二 Reviewer 或人工确认。

## 3.9 Reviewer Prompt 基线

以下提示词定义 Reviewer 的稳定行为。具体 source adapter 和工具说明可以按来源类型追加。

```text
You are an independent reviewer of a Scientific Knowledge Bundle.

You can inspect the original source bundle, one candidate Scientific Recipe,
the Scientific Skills referenced by that Recipe, and their supporting files.
Read progressively: begin with the Recipe and Skill metadata, then inspect
full files and source locators only where they affect the judgments.

Make two independent judgments.

A. Knowledge Validity
Decide whether the Recipe, Skills, and references are a faithful, logically
coherent, appropriately abstracted, and correctly separated representation
of the source material.

B. Task Generation Suitability
Decide whether the bundle contains enough supported information to generate
at least one concrete, executable, and objectively verifiable scientific task
without inventing new scientific rules.

Focus only on material issues that could change scientific correctness,
task construction, evaluator validity, executability, or information leakage.
Do not reject for writing style, optional improvements, or missing details
that do not affect execution or verification.

Do not assess whether a general model already knows the Skill.
Do not require a no-Skill rollout to fail.
Do not estimate task difficulty or model pass rate.
Do not rewrite the artifacts.

For each judgment return accept, revise, or reject. Give one concise reason
and no more than three blocking issues. Each issue must identify its target,
material impact, and a repair direction grounded in the available source.
```

## 3.10 MVP 实现：Codex + Skill

### 3.10.1 运行单元

一次 Knowledge Review 对应一个独立的 Codex 任务。任务启动时加载稳定版本的 `knowledge-reviewer` Skill，并接收以下路径：

```text
review-run/input/
├── source-bundle/
├── candidate-knowledge-bundle/
├── knowledge-reviewer/
├── knowledge-review.schema.json
└── review-context.json
```

`source-bundle/`、`candidate-knowledge-bundle/` 和 Reviewer Skill 都是由程序创建的隔离快照。Extractor trace、final message 和内部推理记录不会进入 Reviewer 输入。Codex 使用 `read-only` sandbox，只能读取、检索和运行不产生写入的检查命令。

Reviewer 的最终响应由 `knowledge-review.schema.json` 约束为纯 JSON。程序解析响应、检查两个 judgment 的字段、blocking issue 数量和 routing 一致性，随后物化唯一正式产物 `knowledge-review.json`。Reviewer 不在同一次任务中触发 repair，确保审核意见与被审产物相互独立。

每次审核使用 fresh context，只提供当前输入、Reviewer Skill 和必要的上一轮 blocking findings。Heta 的内部推理记录不进入上下文。

### 3.10.2 Reviewer Skill

MVP 的 Skill 采用以下轻量结构：

```text
knowledge-reviewer/
├── SKILL.md
└── references/
    ├── knowledge-validity.md
    ├── task-generation-suitability.md
    └── review-output.md
```

- `SKILL.md` 定义审核目标、渐进读取流程、工具使用边界、双 judgment 和停止条件；
- `knowledge-validity.md` 解释来源忠实性、内部逻辑、抽象质量和信息边界；
- `task-generation-suitability.md` 解释可实例化、可执行、可客观验证和忠实任务化；
- `review-output.md` 固定 verdict、blocking issue 和 routing 的输出契约。

来源类型相关的读取说明优先由 Source Bundle adapter 提供。只有跨样本稳定复用的审核知识才进入 Reviewer Skill，避免 Skill 随 ALE、论文或软件来源不断膨胀。

### 3.10.3 Codex 权限边界

Codex Reviewer 可以：

- 读取和检索 Source Bundle、Recipe、Skills、references 与 registry；
- 检查数据格式、目录结构、代码、软件说明和已有 runtime evidence；
- 执行不会产生写入的只读检索和辅助分析；
- 根据证据生成一个符合契约的审核结果。

Codex Reviewer 不获得候选 Knowledge Bundle 的写权限，也不启动 Knowledge Repair、TaskGen、EnvironmentGen 或 rollout。基础设施在任务开始前完成路径解析和输入装载，在任务结束后校验 JSON 是否可解析以及必需字段是否存在。这些校验只保障调用契约，不代替语义审核。

输入装载前，程序要求第二章的 materialization qualification 已通过，并重新确认 Source Bundle 与 extraction inventory 一致。审核完成后，原始输入和隔离快照都会重新计算完整文件 inventory；任何变化都会使该次 review 失败。

### 3.10.4 后续演进

单次结构化 LLM 调用保留为未来的 fast path。积累一批人工复核过的 Reviewer 结果后，可以比较它与 Codex + Skill 在准确率、漏检率、成本和延迟上的表现；只有紧凑、规范且无需工具检查的 Knowledge Bundle 才考虑走 fast path。MVP 的 canonical path 保持为 Codex + Skill。

## 3.11 明确排除的职责

Knowledge Reviewer 不负责：

- 修复或重写 Recipe、Skills 和 references；
- 生成具体 Task instruction；
- 构建 Docker environment；
- 实现 reference solution 和 evaluator；
- 运行 paired skill/no-skill 对照；
- 估计任务难度或模型通过率；
- 验证最终 Solver trajectory；
- 对非阻塞的写作风格进行打分。

这些职责分别属于 Knowledge Repair、TaskGen、EnvironmentGen、Task Verification 和 Trajectory Verification。

## 3.12 待定问题

- Source Bundle 提供给 Reviewer 的检索接口；
- 高风险科学领域的升级条件；
- repair budget 和人工确认策略；
- 对论文、数据、软件和 ALE Task Card 是否需要不同的附加 reviewer instructions。

## 3.13 MVP 实现与运行产物

第三章已经实现为 [review.py](../../src/skt_repro/review.py) 与两个 CLI 命令：

- `review-knowledge`：从一个通过资格检查的 extraction run 创建隔离快照，启动 fresh Codex Reviewer，并在合同通过后物化正式审核结果；
- `verify-knowledge-review`：独立检查已有 review 的字段、verdict/blocker 关系、整次审核最多三个 blocker，以及 routing 一致性。

Reviewer 使用 [knowledge-reviewer](../../pipeline-skills/knowledge-reviewer/SKILL.md)。三个 reference 分别保存 Knowledge Validity、Task Generation Suitability 和输出合同，核心 Skill 只保留渐进读取、证据纪律、verdict 纪律与职责边界。结构化响应使用轻量 [knowledge-review.schema.json](../../schemas/knowledge-review.schema.json)，没有引入评分、置信度或传统字段打分。

一次 review run 的完整目录如下：

```text
review-run/
├── input/                         # Source、Candidate、Reviewer Skill 隔离快照
├── request.md
├── agent/
│   ├── events.jsonl
│   ├── stderr.log
│   └── final-message.md
├── knowledge-review.json          # 唯一正式审核产物
├── review-qualification.json      # 调用合同与 routing 检查
└── review-record.json             # 模型、输入 digest、运行与不变性记录
```

## 3.14 首次真实审核

首次审核使用第二章 canonical extraction [ale-ndvi-zonal-statistics-004](../../runs/chapter-02/ale-ndvi-zonal-statistics-004/)：

```bash
PYTHONPATH=src python3 -m skt_repro review-knowledge \
  runs/chapter-02/ale-ndvi-zonal-statistics-004 \
  --output runs/chapter-03/ale-ndvi-knowledge-review-001 \
  --model gpt-5.6-sol \
  --reasoning-effort high
```

[ale-ndvi-knowledge-review-001](../../runs/chapter-03/ale-ndvi-knowledge-review-001/) 在 read-only sandbox 中完成。Agent 返回码为 0，输入在运行后保持不变，[review-qualification.json](../../runs/chapter-03/ale-ndvi-knowledge-review-001/review-qualification.json) 没有 finding。

正式 [knowledge-review.json](../../runs/chapter-03/ale-ndvi-knowledge-review-001/knowledge-review.json) 给出：

- Knowledge Validity：`accept`；
- Task Generation Suitability：`accept`；
- blocking issues：0；
- routing：`release_to_taskgen`。

Reviewer 重新确认了 NDVI 公式、精确无效像元规则、float32 阶段交接、栅格网格保持、polygon reprojection、pixel-center inclusion、标识符语义、属性透传、空区域行为和序列化舍入。Taskability 判断确认至少一个实例可以绑定输入、在已有地理运行能力上执行，并通过栅格结构、finite mask、NDVI 数值、polygon coverage、zonal statistics、排序和格式建立客观验证。

这一 routing 表示 Candidate Knowledge Bundle 已具备进入 TaskGen 的审核依据。Reviewer 不修改 Candidate registry；后续流水线消费 Candidate Bundle 与该 review 的组合，并在正式 catalog 层完成发布状态变更。
