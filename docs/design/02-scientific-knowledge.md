# 第二章 Scientific Recipe 与 Scientific Skill

> 状态：MVP 已实现并完成真实 ALE 输入实跑  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 2.1 章节目标

本章定义原始材料进入科学知识层时的输入、Agent 工作方式和正式产物。该阶段接收论文、数据、软件、runtime 或 ALE Task Card 等不同来源，通过 Codex 加 Scientific Knowledge Extractor Skill 形成 Candidate Scientific Recipe 与 Scientific Skills，随后交给 Knowledge Reviewer 独立审核。

这一阶段采用“固定输入信封、开放原始内容”的设计。系统只统一来源入口、必要上下文和输出目录，原始材料继续保留最适合自身的文件格式与目录结构。Agent 负责理解材料之间的关系、抽取科学过程，并决定 Recipe 与 Skills 的合理边界。

## 2.2 阶段合同

```text
Source Bundle
      ↓
Codex + scientific-knowledge-extractor Skill
      ↓
Candidate Knowledge Bundle
├── one Scientific Recipe
├── one or more Scientific Skills
└── provenance registry records
      ↓
Knowledge Reviewer
```

一次 extraction run 可以从一个 Source Bundle 形成零个、一个或多个 Candidate Knowledge Bundles。每个 Knowledge Bundle 以一个完整科学过程为中心，包含一个 Recipe 及其引用的一个或多个 Skills。来源不足以支持可靠抽取时，Extractor 应结束并报告缺少的证据，不为满足目录合同补写科学内容。

本阶段只完成 `Source → Knowledge`。具体任务 instruction、输入实例、Docker、reference solution、evaluator 和 gold values 在后续 TaskGen 与 EnvironmentGen 阶段产生。

## 2.3 Source Bundle：固定信封，开放内容

### 2.3.1 目录形式

Source Bundle 使用一个轻量入口文件组织开放材料：

```text
source-bundle/
├── SOURCE.md          # required：来源入口和必要上下文
├── materials/         # optional：本地原始材料，内部结构开放
├── runtime/           # optional：Docker、环境描述或已有运行资源
└── evidence/          # optional：执行记录、已知结果、截图或行为 oracle
```

目录名称表达材料在 extraction 中的用途，不要求所有来源创建每个目录。`materials/` 可以保存 PDF、Task Card、数据文件、代码仓库快照、软件文档或它们的组合；未复制进 Bundle 的大型数据和软件资源可以直接由 `SOURCE.md` 中的稳定 locator 作为 entrypoint。输入的最低要求是至少存在一个 Agent 可访问的 entrypoint。

已有 Docker 或其他可运行环境放入 `runtime/`，供 Extractor 识别依赖和方法边界。它可以在 TaskGen 阶段被复用和重新资格验证。已有 QEMU、参考输出和历史执行记录可以作为 evidence，帮助理解原始任务行为，但不会自动成为最终 Task runtime 或 gold answer。

### 2.3.2 `SOURCE.md` 最低合同

`SOURCE.md` 只固定两个前置字段：

```yaml
---
name: ale-crop-rotation-analysis
entrypoints:
  - materials/task-card.md
source_kinds:
  - task_card
  - data
  - runtime
---
```

- `name`：本次来源集合的稳定可读名称；
- `entrypoints`：Agent 应优先读取的一个或多个相对路径或稳定 locator；
- `source_kinds`：可选提示，可以同时声明 `paper`、`data`、`software`、`runtime`、`task_card` 等多种来源。

正文以自然语言补充 Agent 无法仅从文件推断的上下文，推荐覆盖：

- 材料的来源和科学背景；
- 各入口文件承担的作用；
- 论文、数据、软件与 runtime 之间的关系；
- 本次抽取范围，以及已知缺失或不可访问的内容；
- evidence 的含义和可信边界。

这些内容没有固定章节数量。信息能够从原始材料可靠获得时无需重复填写；存在多个相似文件、外部 locator 或特殊 runtime 时，应提供足以消除歧义的导航。

### 2.3.3 ALE 输入示例

```text
source-bundle/
├── SOURCE.md
├── materials/
│   ├── task-card.md
│   └── input/
│       └── parcels.gpkg
├── runtime/
│   └── qemu-environment.md
└── evidence/
    └── known-behavior.md
```

对应的 `SOURCE.md` 可以写成：

```markdown
---
name: ale-crop-rotation-analysis
entrypoints:
  - materials/task-card.md
source_kinds: [task_card, data, runtime]
---

# Context

这组材料来自 ALE 的农业数据分析任务。Task Card 描述原始目标，
GeoPackage 提供实际输入，QEMU 记录给出已知可运行环境的信息。

# Material Relationships

- Task Card 是主要任务语义来源；
- GeoPackage 用于确认真实 schema、CRS 和年份字段；
- QEMU 信息用于识别软件与依赖，不预先指定最终 Task runtime。

# Scope

抽取可复用的地块轮作分析过程、地理数据约束和结果检查方法。
```

论文源可以只提供 PDF 与必要附件；软件源可以把仓库说明、代码入口和测试放入 `materials/`；原始数据源可以提供数据字典、样本和稳定外部 locator。下游接口始终接收同一种 Source Bundle，Extractor 根据实际内容选择读取方式。

## 2.4 Heta Extraction：Codex + Skill

### 2.4.1 MVP 运行单元

MVP 中，一次 extraction 对应一个独立 Codex 任务。任务加载 `scientific-knowledge-extractor` Skill，获得 Source Bundle 的读取权限和 candidate output 的写入权限。Codex 可以检索文件、检查数据格式、阅读代码，并在临时目录运行必要的辅助分析。

Extractor Skill 保存跨来源稳定复用的抽取方法：

- 如何从入口文件开始渐进读取；
- 如何识别科学目标、输入、方法、约束、产物和验证依据；
- 如何区分完整 Recipe 与局部可复用 Skill；
- 如何处理来源冲突、缺失信息和模型推断；
- 如何组织 references、scripts 与 assets；
- 如何生成 registry 中的来源绑定；
- 如何完成产物自检并停止。

论文、ALE、软件和 runtime 的特殊解释信息由 Source Bundle 提供。只有跨样本稳定成立的抽取规则进入 Skill，使 Extractor 不随来源种类持续膨胀。

### 2.4.2 渐进式抽取流程

```text
1. 读取 SOURCE.md 和 entrypoints
2. 建立材料、科学目标与执行证据之间的关系
3. 找出一个或多个完整科学过程
4. 为每个过程定义 Recipe 边界
5. 把具有独立复用价值的局部能力组织成 Skills
6. 按需添加 references、scripts 和 assets
7. 写入来源绑定与 candidate registry records
8. 检查产物边界并结束 extraction
```

Agent 无需遍历与判断无关的全部材料。核心科学声明、操作规则或输出约束需要进一步确认时，Agent 再打开对应 source、数据、代码或 runtime evidence。Extractor 可以总结和组织来源内容；会改变科学含义的补全必须具有可定位的来源依据。

### 2.4.3 Recipe 与 Skill 的拆分判断

一个 Recipe 对应一个连贯的科学目标、输入空间、方法链路和可观察结果。相同方法在不同输入或参数上的任务变体通常属于同一个 Recipe；科学目标、主要产物或验证逻辑发生实质变化时，可以形成不同 Recipe。

一个 Skill 对应具有清晰触发条件和完成检查的可复用局部能力。Skill 数量不设固定目标，拆分取决于过程中的实际能力边界。普通文件操作、只在单个任务中有意义的路径绑定，以及缺少独立科学含义的步骤不单独形成 Skill。

多 Recipe 共享的 Skill 可以在 catalog 中复用。一个 Source Bundle 形成多个 Recipe 时，每个 Candidate Knowledge Bundle 仍维持“一份 Recipe 加其所需 Skills”的消费视图，registry 负责记录共享产物的版本与来源。

### 2.4.4 Extractor 权限边界

Extractor 可以创建和修改当前 candidate output，也可以在临时目录进行辅助计算。它不执行以下工作：

- 评价自己抽取的知识是否通过 Knowledge Review；
- 为具体任务选择输入实例或生成 instruction；
- 构建正式 Docker environment；
- 编写 evaluator、reference solution 或 gold values；
- 通过 skill/no-skill rollout 估计模型是否依赖该 Skill；
- 将来源无法支持的推断写成确定的科学规则。

抽取和审核分成独立 Codex 任务，使 Reviewer 可以直接比较 Source Bundle 与 Candidate Knowledge Bundle，不受 Extractor 内部推理过程影响。

## 2.5 Candidate Knowledge Bundle 产物

### 2.5.1 目录合同

```text
candidate-knowledge-bundle/
├── recipes/
│   └── <recipe-name>/
│       ├── RECIPE.md
│       └── references/        # optional：Task Author 按需读取
├── skills/
│   └── <skill-name>/
│       ├── SKILL.md
│       ├── references/        # optional：Task Author / Reviewer 按需读取
│       ├── scripts/           # optional：稳定、重复或脆弱操作
│       └── assets/            # optional：模板、lookup table 等资源
└── registry/
    ├── recipes/<recipe-name>.json
    └── skills/<skill-name>.json
```

Knowledge Bundle 的业务知识采用 file-first Markdown 组织，来源、hash、版本和审核状态进入 solver 不可见的 registry。Task 特定输入、环境和 hidden assets 不进入该目录。

### 2.5.2 Scientific Recipe

Scientific Recipe 描述一个完整科学过程或任务族，回答“哪些能力如何协作，可以从怎样的输入产生什么可验证结果”。它是 TaskGen 的主要知识输入，不挂载给 Solver。

`RECIPE.md` 使用轻量 frontmatter：

```yaml
---
name: crop-rotation-audit
description: Generate verifiable parcel-level crop-rotation audit tasks from year-indexed geospatial data.
version: "0.1.0"
skills:
  - name: audit-geopackage-layers
    role: Preserve geospatial invariants and validate complete and flagged outputs.
---
```

Recipe 的正文需要表达科学目标、输入空间、Skill 协作流程、产物合同、验证意图、难度杠杆和环境能力。具体标题和表达方式可以随领域调整，只要 TaskGen 能够可靠回答以下问题：

- 可以绑定哪些输入、变量和前提；
- 每个 Skill 在完整过程中的作用是什么；
- 阶段之间如何传递中间结果；
- 最终任务应产生哪些可观察 artifacts；
- 哪些科学不变量和关系可以转化为 evaluator；
- 哪些变化能够形成复现、控制变量、多阶段组合或诊断恢复任务；
- runtime 需要提供哪些能力。

Recipe references 保存 Task Author 需要、Solver 无需看到的长篇任务构造知识。MVP 在 `RECIPE.md` 足以完整表达任务族时可以不创建该目录。

### 2.5.3 Scientific Skill

Scientific Skill 描述边界稳定、可复用且能够影响 Agent 实际操作的科学能力，回答“这类科学操作应该怎样完成”。Skill 遵循 Agent Skills 开放格式，由 TaskGen 和 Reviewer 连同所需 resources 读取，不挂载给正式 Solver。

`SKILL.md` 至少包含规范要求的 `name` 与 `description`：

```yaml
---
name: audit-geopackage-layers
description: Produce and validate GeoPackage audit layers while preserving geometry, schema, identifiers, and CRS.
---
```

Skill 正文需要让 Task Author 和 Reviewer 理解目标、输入与前提、核心工作流、科学规则、输出检查以及必要的失败恢复方法。公式、规范和数据格式说明可以放入 `references/`，稳定的辅助程序放入 `scripts/`，输出模板和查找表等资源放入 `assets/`。这些资源只有在实际需要时创建，并由 `SKILL.md` 说明读取时机。

任务 instruction、具体文件名、固定输出路径、Docker image、evaluator、reference solution 和 gold result 不进入 Scientific Skill。

### 2.5.4 Registry records

每份 Recipe 和 Skill 对应一个生产侧 registry record，至少记录：

- artifact kind、稳定 ID、版本和入口路径；
- 入口内容 hash 与 candidate 状态；
- Source Bundle ID、source locator 和 source content hash；
- 可选的关键声明证据定位、抽取运行信息和后续审核结果。

Registry 用于追踪、去重、版本管理和审计，不挂载给 Solver。Extractor 的长篇思维过程不作为 Knowledge Bundle 的组成部分。

## 2.6 自检与 Reviewer 交接

Extractor 完成后只进行产物级自检：入口文件已经生成、Recipe 能解析 Skill 引用、相对资源路径存在、registry 可以定位来源、知识产物中没有实例 hidden answer。文件解析与路径问题属于 materialization failure，可以由 Extractor 当场修复。

科学忠实性和任务生成条件由下一阶段 Knowledge Reviewer 判断。Reviewer 重新读取 Source Bundle 与 Candidate Knowledge Bundle，一次给出 Knowledge Validity 和 Task Generation Suitability 两个独立结论。Extractor 的自检结果不会替代该审核。

通过审核后，Candidate Knowledge Bundle 转为 Accepted Knowledge Bundle 并进入 TaskGen；`revise` 返回 Knowledge Repair；来源可靠但暂时缺少任务化条件的内容可以进入 non-taskable knowledge archive。

## 2.7 正式模板与示例

字段级产物合同、模板和当前 ALE 示例见：

- [Scientific Recipe 与 Scientific Skill 产物合同](../scientific-skill-spec.md)
- [Scientific Skill 模板](../../templates/scientific-skill/SKILL.md)
- [Scientific Recipe 模板](../../templates/scientific-recipe/RECIPE.md)
- [Crop-rotation Knowledge Bundle 示例](../../examples/scientific-knowledge/crop-rotation-audit/)

## 2.8 已确认结论

- Source Bundle 只固定 `SOURCE.md`、entrypoints 和必要上下文，原始材料结构保持开放；
- MVP extraction 由一个 Codex 任务加载 `scientific-knowledge-extractor` Skill 完成；
- Recipe 和 Skill 数量由科学语义与复用边界决定，不设置固定配额；
- 一个 Knowledge Bundle 包含一个 Recipe 和其引用的一个或多个 Skills；
- Recipe 和 Scientific Skills 面向 TaskGen 与 Reviewer，均不挂载给正式 Solver；
- provenance 与审核状态进入 registry；
- Task instruction、具体 runtime、evaluator、reference solution 和 gold values 留在 Task Package；
- Heta extraction 与 Knowledge Review 使用独立 Agent 任务。

## 2.9 待定问题

- Source Bundle 中大型外部数据与软件 locator 的缓存和版本固定方式；
- 一个 Source Bundle 产生多个 Recipe 时的自动拆分与人工确认策略；
- Skill 复用、合并和版本更新时的 catalog 兼容策略；
- 论文 PDF、配套数据与软件仓库组合输入时的首轮实跑表现。

## 2.10 MVP 技术实现

第二章已经实现为一个可单独运行的命令。实现由三个边界清楚的组件组成：

- [`knowledge.py`](../../src/skt_repro/knowledge.py) 解析 Source Bundle、生成逐文件 SHA-256 inventory、构造抽取请求，并对 Candidate Knowledge Bundle 做文件级资格检查；
- [`agent_runtime.py`](../../src/skt_repro/agent_runtime.py) 负责一次 fresh `codex exec`、超时、模型参数、完整 JSONL event trace 和临时认证隔离；
- [`scientific-knowledge-extractor`](../../pipeline-skills/scientific-knowledge-extractor/SKILL.md) 保存跨来源稳定的科学抽取方法、Recipe/Skill 拆分原则和输出合同。

一次正式运行使用显式的模型与 reasoning effort，并通过 `--ignore-user-config` 排除个人 MCP、插件和工作区配置。运行器只把认证文件复制到自动清理的临时 `CODEX_HOME`。Codex 的 workspace 根目录设为本次 `run/`，Source Bundle 与 Extractor Skill 位于 workspace 外部并以只读方式访问。Agent 结束后，程序重新计算两者的完整 inventory；任何输入变化都会使资格检查失败。

程序检查的范围保持在 materialization 与 provenance：

- Source Bundle 的入口存在且不能越过输入根目录；
- 一个 Candidate Knowledge Bundle 包含一份 Recipe 和至少一份 Skill；
- Recipe frontmatter、Skill frontmatter、目录名和引用关系一致；
- 每个 artifact 都有 candidate registry record；
- registry entrypoint hash 与实际文件一致；
- registry source locator 和 hash 可以在运行前 inventory 中解析；
- Source Bundle 与 Extractor Skill 在运行后保持不变。

这组检查不评价科学忠实性，也不判断知识是否适合生成任务。它只确认产物已经可靠落盘，可以交给第三章 Knowledge Reviewer。

## 2.11 运行产物

一次 extraction run 保存完整运行信封和 canonical candidate bundle：

```text
run/
├── request.md
├── source-inventory.json
├── agent/
│   ├── events.jsonl
│   ├── stderr.log
│   └── final-message.md
├── candidate-knowledge-bundle/
│   ├── recipes/<recipe>/RECIPE.md
│   ├── skills/<skill>/SKILL.md
│   └── registry/{recipes,skills}/*.json
├── qualification.json
└── extraction-record.json
```

`candidate-knowledge-bundle/` 是交给下游的知识产物。其余文件属于生产与审计记录，不挂载给 Task Author 或 Solver。`extraction-record.json` 固定模型参数、运行耗时、输入 inventory digest、Extractor Skill digest、Agent 退出状态和资格结论。

## 2.12 首次真实输入输出闭环

首个 Source Bundle 使用 ALE 的 `agriculture_env/ndvi_zonal_statistics_d02`：

- [`SOURCE.md`](../../examples/source-bundles/ale-ndvi-zonal-statistics/SOURCE.md) 解释材料关系和抽取范围；
- `task_card.json`、`main.py` 与 `verify_outputs.py` 是上游提交 `1e615e456de7cef57706680613cb80ee13c7fc76` 的逐字节快照；
- [`qemu-environment.md`](../../examples/source-bundles/ale-ndvi-zonal-statistics/runtime/qemu-environment.md) 记录已知 runtime 能力与证据边界。

正式运行命令为：

```bash
PYTHONPATH=src python3 -m skt_repro extract-knowledge \
  examples/source-bundles/ale-ndvi-zonal-statistics \
  --output runs/chapter-02/ale-ndvi-zonal-statistics-004 \
  --model gpt-5.6-sol \
  --reasoning-effort high
```

[`run-004`](../../runs/chapter-02/ale-ndvi-zonal-statistics-004/) 在 275.832 秒内完成，Agent 返回码为 0，并生成：

- 一份 [`sentinel-2-ndvi-zonal-statistics` Recipe](../../runs/chapter-02/ale-ndvi-zonal-statistics-004/candidate-knowledge-bundle/recipes/sentinel-2-ndvi-zonal-statistics/RECIPE.md)；
- [`compute-ndvi-raster`](../../runs/chapter-02/ale-ndvi-zonal-statistics-004/candidate-knowledge-bundle/skills/compute-ndvi-raster/SKILL.md)；
- [`compute-polygon-ndvi-zonal-statistics`](../../runs/chapter-02/ale-ndvi-zonal-statistics-004/candidate-knowledge-bundle/skills/compute-polygon-ndvi-zonal-statistics/SKILL.md)；
- 三份与上述 artifact 对应的 candidate registry records。

[`qualification.json`](../../runs/chapter-02/ale-ndvi-zonal-statistics-004/qualification.json) 没有 finding，Source Bundle 与 Extractor Skill 的 `unchanged_after_run` 均为 `true`。独立执行 `verify-knowledge` 得到相同结果。该 Knowledge Bundle 当前仍是 candidate；第三章将从原始来源重新审核科学忠实性与任务生成条件。
