# 科学任务与轨迹数据生产管线

把论文、科学软件和数据转成可执行、可评分的科学任务，让 Agent 独立解题，再把通过验证的完整执行轨迹整理为训练与评测数据。

> 下一版技术选型已确认：Data Designer 组织生成，Gym + Harbor 承接 rollout。本文保留阶段职责总览；组件分工及新版整体流程图、rollout 时序图见[第十三章](design/13-data-designer-gym-harbor-architecture.md)。新版尚待集成验证。

## 1. 整体流程

实线表示生产流程，虚线表示审核证据。正式生产共八个阶段；第七阶段在图中拆开显示解题和轨迹验证，方便理解。

```mermaid
flowchart TD
    request["起点 A：Benchmark / Task Card / 任务提案<br/>说明想生产哪类科学任务"]
    provided["起点 B：已有来源清单<br/>论文、代码、数据的地址与版本"]

    discover["① 来源发现<br/>寻找能独立支持新任务的论文、软件和数据"]
    selection["来源清单<br/>地址、固定版本、候选目录与选择结果"]
    materialize["② 来源下载与固化<br/>获取材料，记录版本、文件清单和哈希"]
    source["Source Bundle：原始材料包<br/>原始文件、来源信息与完整性记录"]
    extract["③ 知识抽取<br/>整理科学流程、可复用方法和来源对应关系"]
    knowledge["候选知识包<br/>Recipe：完整科学流程<br/>Scientific Skills：可复用科学方法<br/>Registry：来源与版本记录"]
    review{"④ 知识审核<br/>忠实于来源吗？<br/>能构造可执行、可评分的任务吗？"}
    accepted["通过审核的知识包"]
    author["⑤ 任务与环境生成<br/>绑定数据和参数，编写题目<br/>准备 Docker、参考解和隐藏评分器"]
    candidate["候选任务包<br/>公开题目与输入、运行环境<br/>隐藏参考解与评分器、构造记录"]
    verify{"⑥ 任务验证<br/>环境能运行、参考解能通过吗？<br/>评分器能拒绝错误结果吗？<br/>题目科学有效且没有答案泄露吗？"}
    repair["任务修复<br/>修正题目、环境、参考解或评分器"]
    verified["已验证任务包"]

    subgraph stage7["⑦ 独立解题与轨迹验证"]
        project["准备 Solver 可见材料<br/>只提供公开题目、输入、输出要求和执行设置"]
        solve["Fresh Rollout：全新会话与任务容器<br/>Agent 执行工具 → 观察结果 → 修改并重跑<br/>结束后保存输出文件和完整执行记录"]
        assess{"独立验证<br/>结束后运行隐藏评分器<br/>检查轨迹完整性、科学过程与信息隔离"}
        trajectory["通过验证的轨迹<br/>消息、工具调用、输出文件、评分与审核结论"]
        diagnosis["失败诊断<br/>区分解题失败、任务缺陷和基础设施故障"]
    end

    release["⑧ 数据集发布<br/>筛选合格轨迹，保留原始记录<br/>转换 SFT 格式，生成版本与追溯清单"]
    dataset["交付：Raw 轨迹 + SFT 数据 + 发布清单<br/>用于后续训练、评测与分析"]
    stop["记录拒绝或阻塞原因<br/>不进入正式数据集"]

    request --> discover --> selection
    provided --> selection
    selection --> materialize --> source --> extract --> knowledge --> review
    source -.->|来源证据| review
    review -->|通过| accepted
    review -->|需要修改| extract
    review -->|拒绝| stop
    accepted --> author --> candidate --> verify
    source -.->|具体输入资产| author
    accepted -.->|任务忠实性依据| verify
    verify -->|通过| verified
    verify -->|任务或环境问题| repair
    repair --> candidate
    verify -->|知识层问题| extract
    verify -->|无法修复或预算耗尽| stop
    verified --> project --> solve --> assess
    accepted -.->|仅 Reviewer 读取| assess
    assess -->|通过| trajectory --> release --> dataset
    assess -->|未通过| diagnosis
    diagnosis -->|解题失败或基础设施故障：预算内全新重试| project
    diagnosis -->|任务缺陷：修复后重新验证| repair
    diagnosis -->|预算耗尽或无法恢复| stop

    classDef artifact fill:#eef6ff,stroke:#3973ac,color:#172b4d;
    classDef gate fill:#fff5d6,stroke:#a67c00,color:#493700;
    classDef success fill:#e8f5e9,stroke:#388e3c,color:#173c19;
    classDef blocked fill:#fcebea,stroke:#bb4444,color:#5c2020;
    class selection,source,knowledge,accepted,candidate,verified,trajectory artifact;
    class review,verify,assess gate;
    class dataset success;
    class stop blocked;
```

重试遵守预算，每次重新建立会话和工作区。历史失败轨迹、评分器结果和 Reviewer 反馈不会传给下一次 Solver。任务修复后必须重新验证，才能再次解题。

## 2. 每个阶段的输入、工作与输出

| 阶段 | 输入是什么 | 做什么 | 输出是什么 |
| --- | --- | --- | --- |
| ① 来源发现 | Benchmark、Task Card 或任务提案；数量和领域要求 | 理解目标能力，寻找独立科学来源，检查来源质量与重复实体；已有合格清单可跳过检索 | 来源地址与固定版本、`selection.yaml`、候选目录与报告 |
| ② 来源下载与固化 | 来源清单、下载策略 | 获取代码、文档和数据，固定版本并记录文件哈希 | Source Bundle、文件清单与来源记录 |
| ③ 知识抽取 | Source Bundle | 提取科学目标、方法、前提、输入输出和验证线索，拆分完整流程与局部能力 | 候选 Recipe、Scientific Skills、references 和 registry |
| ④ 知识审核 | 候选知识包、原始来源证据 | 分别判断知识是否忠实、是否足以生成任务；给出通过、修改或拒绝结论 | 审核报告、通过审核的知识包，或需要修正的问题 |
| ⑤ 任务与环境生成 | 通过审核的知识包、具体数据、任务要求、可用运行环境 | 绑定具体实例，编写自包含题目与输出要求，准备 Docker 环境、参考解和评分器 | 候选 Task Package、环境与构造记录 |
| ⑥ 任务验证与修复 | 候选任务包、知识依据、验证策略 | 检查环境；在全新工作区执行参考解；用错误结果和有效等价结果检查评分器；审核任务语义与信息隔离；必要时修复并重验 | 已验证任务包与验证证据，或阻塞记录 |
| ⑦ 独立解题与轨迹验证 | 已验证任务的公开材料、运行环境、Solver 配置；验证侧另有知识依据和隐藏评分器 | Solver 在容器内交互解题；结束后独立评分，审核科学过程、执行记录与信息边界 | 完整 attempt、输出文件、评分与审核报告；通过后成为 Verified Trajectory |
| ⑧ 数据集发布 | 通过验证的轨迹、数据集配置 | 检查准入与文件完整性，保留原始轨迹，生成训练格式和 loss mask，冻结版本 | Raw 数据集、SFT 记录、发布清单与哈希 |

Benchmark 的公开题目用于指导来源发现，其答案、隐藏测试、参考解和原始评测实例不能作为新任务的来源材料。

## 3. Solver 能看到什么

**正式 Solver 不接收 Campaign、Recipe、Scientific Skills、参考解或评分器。** Recipe 和 Scientific Skills 用于上游出题及审核。题目必须自包含，不能要求 Solver 去读取这些知识资产。

```mermaid
flowchart LR
    package["已验证任务包"]
    public["公开材料<br/>TASK.md、inputs<br/>output-contract、execution-settings"]
    knowledge["上游知识资产<br/>Recipe / Scientific Skills"]
    hidden["隐藏验证资产<br/>参考解 / 评分器 / 预期结果"]

    subgraph runtime["正式 Solver：全新任务容器"]
        agent["Agent 读取题目并编写代码"]
        tools["Shell 与科学软件<br/>执行、观察、修改、重跑"]
        output["提交输出文件<br/>保存完整执行记录"]
        agent --> tools
        tools -->|结果与错误信息| agent
        agent -->|结束执行| output
    end

    judge["Solver 结束后的独立验证<br/>隐藏评分器检查结果<br/>Reviewer 审核科学过程与轨迹"]
    package --> public --> agent
    package --> hidden
    hidden --> judge
    knowledge -->|仅供审核| judge
    output --> judge
```

Solver 可在容器中自行检查结果；隐藏评分器的结果不回传给 Solver，也不会成为下一次尝试的提示。

## 4. 批次配置与全程追溯

- **Campaign Brief：本批次想生产什么。** 描述目标领域、任务分布、调整要求和验收意图，按需传给来源发现、知识抽取、出题及 Reviewer；不传给 Solver。
- **Agent 与运行配置：用什么执行。** 指定各阶段模型、Harness、工具、环境与资源限制。
- **Controller：管理流程。** 负责阶段衔接、准入检查、修复预算、重试和断点续跑。
- **Lineage：记录数据从哪里来。** 串联 Source → Knowledge → Task → Trajectory → Dataset，并保存文件哈希、环境版本、模型配置和审核结论。

数据集发布是这条生产管线的交付终点。SFT 训练、独立评测和收益分析消费这些数据，属于后续工作。

## 5. 详细设计入口

- [完整设计索引](scientific-data-generation-design.md)
- [八阶段生产控制器](design/10-agent-factory-production-pipeline.md)
- [Campaign 与阶段提示词](design/11-campaign-brief-prompt-compilation.md)
- [正式 Solver 容器与执行边界](design/12-interactive-container-rollout.md)
