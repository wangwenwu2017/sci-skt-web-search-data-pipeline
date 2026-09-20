# 第六章 Rollout 与 Trajectory Verification

> 状态：MVP 已实现并完成首条 Verified Trajectory 实跑  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 6.1 章节目标

本章定义 Verified Task Package 如何通过 fresh Solver rollout 形成完整执行轨迹，以及轨迹如何经过结果与过程验证后进入 Verified Trajectory Store。第五章证明任务包本身成立；第六章判断某一次具体 Solver execution 是否正确完成该任务，并形成可以用于训练或评测的可信记录。

主流程借鉴 SKT Stage III：teacher model 在全新 session 和 workspace 中执行已验证任务；deterministic validator 检查 evaluator outcome、终止状态和 trace 完整性；LLM validator 检查实现过程；失败尝试被丢弃，下一次尝试不接收上一轮的轨迹、得分或 verifier feedback。[SKT Stage III: Trajectory Synthesis](https://arxiv.org/html/2608.02287v1#S3.SS3)

本项目保留 fresh rollout、两层 trajectory qualification 和无反馈重采样，同时把 LLM validator 的核心目标调整为科学过程一致性。正式 Solver 不接收 Recipe 或 Scientific Skills；Skill access 仅适用于独立知识增强实验，正式轨迹需要验证知识隔离；轨迹是否合格取决于任务结果、执行完整性、科学过程和信息面隔离。

## 6.2 阶段合同

```text
Verified Task Package@digest
Solver Configuration
Rollout Policy
        ↓
Fresh Rollout
├── fresh model session
├── fresh isolated workspace
├── solver-visible Task Package
└── harness-native interaction
        ↓
Immutable Rollout Attempt
├── complete trajectory
├── output artifacts
├── terminal outcome
└── evaluator outcome
        ↓
Deterministic Trajectory Qualification
        ↓ pass
Codex + trajectory-reviewer Skill
└── Scientific Process Validity
        ↓
   accept ───────────────→ Verified Trajectory
   reject
        ↓
Fresh Retry from the same Verified Task Package
```

Task Package、model、harness 和 rollout policy 的一个固定组合称为一个 rollout pairing。Controller 可以为同一 pairing 配置有限 attempt budget；默认保留第一个通过两层验证的轨迹作为训练候选，其余尝试保留最小审计记录，不进入 SFT 数据。

## 6.3 Rollout 输入与 Solver 信息面

### 6.3.1 输入

```text
Rollout Input
├── verified-task-package@digest
├── solver-configuration
│   ├── model and revision
│   ├── harness and version
│   ├── system prompt reference
│   ├── tool definitions
│   └── sampling parameters
└── rollout-policy
    ├── timeout and resource limits
    ├── network policy
    ├── attempt budget
    └── evaluator pass condition
```

Controller 只接受第五章已标记为 verified 的 immutable package digest。Rollout 时固定最终 image digest、model revision、harness version、system prompt digest、tool-definition digest 和知识可见性策略；使用 Skill 的 pairing 还会固定 Skill digests，使一次 execution 可以被准确重放和比较。

MVP 的统一准入目标是 `scientific-correctness`：任务结果正确、轨迹完整、科学过程无实质错误。Evaluator pass condition 来自已经通过第五章审核的 Task Package；rollout policy 只在其允许范围内选择满分或声明的通过阈值。

### 6.3.2 Solver 可见内容

正式 Solver workspace 只包含：

- `visible/TASK.md`、inputs、output contract 和 execution settings；
- 第五章通过 qualification 的 runtime；
- 一个全新的可写 output workspace。

Campaign、Recipe、Scientific Skills、reference solution、evaluator implementation、expected artifacts、authoring trace、task verification record、历史 rollout 和 reviewer feedback 都不进入 Solver session。Solver 在已验证任务容器中执行科学软件，观察 stdout/stderr 和退出状态，修改代码或参数并重新运行。Evaluator 由 harness 在 Solver 停止后以 verifier 权限运行，其详细结果也不会回注当前或下一次 Solver attempt。

### 6.3.3 知识可见性与 ALE-like capability profile

正式生产固定使用 `skill_visibility: none`。兼容的 `mounted` policy 仅用于独立知识增强实验，不属于正式 Solver 合同：

| Profile | `skill_visibility` | Solver 可见知识 | 用途 |
| --- | --- | --- | --- |
| skill-assisted | `mounted` | Task、inputs、runtime、output contract、selected Skills | 独立知识增强实验，非正式生产 |
| ALE-like capability | `none` | 自包含 Task Card、inputs、runtime、output contract | 观察完整 Agent system 在无额外领域手册时能否完成任务 |

`none` 不是在提示词里要求 Solver 忽略 Skill。Controller 不创建 `skills/`，执行容器也不挂载 Skill；Solver workspace inventory、policy digest 和 native trace 会共同证明零 Skill 暴露与零 Skill 访问。原 Task Card 中指向 Skill mount 的文字会被确定性地移除，公开科学目标、输入规则、产物合同和数值容差保持不变。若转换后仍存在 Skill 指针，rollout 在模型调用前失败，避免产生带悬空依赖的伪 no-skill 任务。

ALE-like task projection 使用 ALE 常见的 `taskPrompt`、`agentMustDo`、`inputFiles`、`software`、`vm` 和 required outputs 信息面，并排除 Recipe、Skills、reference 与 evaluator。它对齐 ALE 的核心测量边界：Agent 获得任务、输入和环境，完成后由隐藏 evaluator 评价 artifacts。历史 `kimi-code-batch-docker` 是“先编写 submission、再在任务 Docker 中单次执行”的 batch adapter，没有提供 ALE 正式 runner 的交互式 VM、CLI/CUA 工具面，当前正式 Solver 使用第十二章的容器内交互式执行合同。上述历史 batch 实验结果称为 **ALE-like capability**，不能标记成 ALE 官方 benchmark score。

两种 profile 使用同一 model、harness、输入、verified image、Evaluator、资源与时间限制时，可以按任务计算：

```text
Knowledge Lift = Score(skill_visibility=mounted)
               - Score(skill_visibility=none)
```

正式生产数据固定采用 `none`；`mounted` 作为独立的知识增强实验线保留。两条轨迹不能混在同一个未标注的数据分区中。

## 6.4 Fresh Rollout

### 6.4.1 Freshness 合同

每次 attempt 都重新创建：

- model conversation/session；
- runtime container 或等价的隔离执行实例；
- 基于原始 task inputs 初始化的 workspace；
- output directory、临时目录和进程环境；
- harness-side event stream 与 attempt ID。

新的 attempt 不继承上一轮的消息、tool state、生成文件、shell history、缓存、evaluator outcome、failure category 或 reviewer diagnosis。允许复用已经冻结的只读 image layer 和依赖缓存，但这些缓存不得包含任务实例产生的状态或答案。

### 6.4.2 执行生命周期

```text
prepare verified runtime
        ↓
materialize solver-visible workspace
        ↓
start fresh model + harness session
        ↓
stream messages, tool calls and tool results
        ↓
normal completion | timeout | execution failure
        ↓
freeze trace and output workspace
        ↓
run evaluator with verifier privileges
        ↓
write immutable attempt record
```

Harness 在 rollout 期间只负责呈现任务、执行工具、记录事件和执行已声明的资源限制。它不向 Solver 提供 reference hints、动态评分或修复建议。Solver 可以在公开环境内自行检查输出，但不能调用 hidden evaluator。

### 6.4.3 完成状态

Attempt 需要保留明确的 terminal status：

| Status | 含义 |
| --- | --- |
| `completed` | Solver 正常结束并提交当前结果 |
| `timeout` | 超过 wall-clock 或 harness turn limit |
| `tool_failure` | 关键工具或执行环境发生不可恢复错误 |
| `model_failure` | 模型请求失败、输出不可解析或 session 异常中断 |
| `policy_violation` | 触发网络、权限、mount 或安全限制 |
| `infrastructure_failure` | evaluator、runtime 或存储等生产基础设施失败 |

`infrastructure_failure` 不计入 Solver 成败统计，并触发受控重跑或人工处理。其余状态属于真实 attempt outcome，是否继续重试由 rollout policy 决定。

## 6.5 Harness Adapter 与完整轨迹

### 6.5.1 Harness-native 记录

不同 harness 的消息结构、tool-call schema 和终止信号可能不同。原始轨迹以 harness-native protocol 保存，避免为了统一格式丢失并行工具调用、思考与行动边界、tool call ID、错误结果或 harness 特有状态。

Adapter 只提供一个最小公共索引：

```text
sequence
event type
actor
native event locator
timestamp or logical order
tool-call linkage
artifact linkage
```

公共索引用于验证、检索和统计，native trace 仍是权威执行记录。第七章负责把 verified native trajectory 渲染成目标模型需要的 SFT 格式。

### 6.5.2 Rollout Attempt 逻辑产物

```text
rollout-attempt/<attempt-id>/
├── attempt.json
├── trajectory/
│   ├── native.jsonl
│   └── events.jsonl
├── artifacts/
│   └── manifest.json
└── outcome/
    ├── terminal.json
    └── evaluator.json

trajectory-verification/<attempt-id>/
├── deterministic.json
├── semantic-review.json
└── report.json
```

`attempt.json` 记录 task digest、environment digest、model、harness、system prompt、tools、sampling、attempt number 和 fresh-context 标识。`artifacts/manifest.json` 记录输出文件的路径、类型、大小、content digest 和受控 storage locator。大型 artifacts 可以保存在 content-addressed object store 中，attempt 目录只保存 manifest。

Rollout Attempt 在验证前冻结。Trajectory Verifier 产生独立验证记录，不修改 native trace、artifacts 或 evaluator outcome。

## 6.6 Deterministic Trajectory Qualification

Deterministic qualification 回答：

> 这次执行是否完整结束、产生了 evaluator 认可的结果，并留下可用且未受污染的轨迹证据？

MVP 要求：

1. `terminal.status == completed`；
2. evaluator 正常运行并返回受支持的 JSON report；
3. evaluator score 达到 Task Package 声明的通过条件，默认要求 `1.0`；
4. required output artifacts 存在、可读取且 digest 已固定；
5. native trace 可以按顺序解析，所有 tool calls 都能关联到结果或明确的终止事件；
6. trace 中不存在 verifier feedback、hidden evaluator output 或 reference asset access；
7. attempt metadata 能完整解析到 verified task、runtime、model、harness 和 policy。

Deterministic validator 不评价自然语言推理风格，也不要求 Solver 重复 reference solution 的路径。它只对可由事件、进程状态、文件和 evaluator outcome 确认的事实作判断。

对于允许部分分数的 evaluator，原始 score 完整保留。进入核心 SFT store 的 pass policy 由 `task.json` 和 rollout profile 共同确定，并必须已经在第五章审核；MVP 优先保留满分轨迹。

## 6.7 Codex Trajectory Reviewer

### 6.7.1 运行方式

Deterministic qualification 通过后，Controller 启动一个 fresh Codex 任务并加载 `trajectory-reviewer` Skill。Reviewer 只读以下内容：

```text
Trajectory Review Input
├── visible Task Card and output contract
├── Accepted Recipe and Scientific Skills (Reviewer-only)
├── complete native trajectory
├── artifact manifest and inspectable outputs
├── terminal and evaluator outcome
└── rollout metadata
```

建议使用轻量 Skill：

```text
trajectory-reviewer/
├── SKILL.md
└── references/
    └── review-output.md
```

Reviewer 唯一正式产物为 `semantic-review.json`。它不修改轨迹、不补写缺失步骤、不调用 TaskRepair，也不把 diagnosis 发送给下一次 Solver。

### 6.7.2 Scientific Process Validity

Reviewer 综合判断：

**任务与结果对应**

- 轨迹执行的目标与 `TASK.md` 一致；
- 最终 artifacts 来自本次任务输入和可见环境；
- Solver 没有通过硬编码、读取历史状态或越权路径获得当前实例答案；
- 最终说明没有对 artifacts 作出与实际内容冲突的关键声明。

**科学过程一致性**

- 对结果有实质影响的数据选择、单位、参数、公式、schema 和阶段关系符合 Recipe；
- 关键转换满足 Recipe 声明的前提与不变量；
- diagnostic recovery 确实识别并处理了目标故障，受影响结果已经重新验证；
- controlled-variable 与 multi-stage 任务保留了公开要求的比较关系或阶段依赖。

**轨迹可信度**

- 可观察的 tool calls 和 artifacts 足以支持任务确实被执行；
- 关键错误被识别并恢复时，恢复后的结果重新进入完整流程；
- 轨迹没有伪造工具结果、声称不存在的文件或跳过决定最终科学结论的必要计算；
- harness 或环境错误没有被误判为成功完成。

Reviewer 允许与 reference solution 不同但科学上有效的实现，也不因非阻塞的探索、冗余命令或表达偏好拒绝轨迹。只有能够影响结果正确性、科学含义、执行真实性或数据可用性的实质问题才构成 rejection。

### 6.7.3 Skill access 记录

正式生产通过 workspace inventory、挂载记录和 native trace 核对 Recipe / Scientific Skills 未暴露；发现读取这些资产属于信息面违规。以下 access 字段仅供独立知识增强实验记录：

- 哪些 Skill files 被发现或打开；
- Skill access 发生在什么 action 之前；
- Skill 文件读取事件对应的原始 event references。

在独立知识增强实验中，这些字段只用于 lineage、行为分析和后续实验。实验 Solver 没有显式打开 Skill、只使用部分 Skills，或者采用其他科学上有效的方法，都不会因此被拒绝。若轨迹中的实际操作违反 Recipe、Task 或科学约束，Reviewer 依据 Scientific Process Validity 拒绝该轨迹，无需判断错误是否由 Skill 使用造成。

### 6.7.4 Verdict

```json
{
  "verdict": "accept",
  "summary": "The trajectory completes the declared analysis and its observable operations support the evaluated artifacts.",
  "failure_category": null,
  "blocking_issues": []
}
```

正式 verdict 只有 `accept` 或 `reject`。Reject 时最多报告三个实质问题，并使用稳定的 `failure_category`，例如 `scientific_process_error`、`unsupported_claim`、`hidden_information_access`、`incomplete_recovery` 或 `trace_artifact_mismatch`。Reviewer 可以标记 `suspected_task_issue`，该标记只触发后续诊断，不直接修改 Task Package。

## 6.8 Qualification 与保留规则

Controller 根据两层结果生成最终报告：

```json
{
  "trajectory_id": "traj-<id>",
  "attempt_id": "attempt-<id>",
  "task_id": "crop-rotation-reproduction-001",
  "task_digest": "sha256:<digest>",
  "deterministic_qualification": "pass",
  "scientific_process_validity": "accept",
  "verified": true
}
```

`verified` 由 Controller 计算。只有 deterministic `pass` 且 semantic `accept` 的 attempt 才进入 Verified Trajectory Store。验证报告引用原始 attempt digest、artifact digests 和 evaluator report digest，使后续数据转换能够证明自己使用了同一份已验证执行记录。

通过轨迹完整保留 uninterrupted Solver interaction。Hidden reference、evaluator implementation、Reviewer prompt、analysis 和 failure feedback 留在训练轨迹之外。

## 6.9 Fresh Retry 与异常升级

普通 Solver failure 触发新的 attempt：

```text
attempt-N rejected
        ↓
record concise failure category
        ↓
destroy session and workspace
        ↓
attempt-N+1 from original verified package
```

下一次尝试只知道原始 policy 所定义的 Solver-visible Task Package，不接收上一轮执行、得分或诊断。轨迹不会被局部修补，也不会把失败步骤删除后拼接为成功轨迹。达到 attempt budget 后，该 task–model–harness–visibility pairing 记为 `rollout_exhausted`，不产生 verified trajectory。

单次 Solver 失败不改变 Verified Task Package。以下情况可以暂停该任务的后续 rollout，并将证据提交第五章重新 qualification：

- evaluator 或 runtime 在多个 fresh attempts 中出现相同 infrastructure failure；
- 多个独立 Solver 暴露相同的 Task Card、输入或环境矛盾；
- Trajectory Reviewer 发现 reference qualification 未覆盖的 evaluator loophole；
- Solver-visible workspace 与第五章记录的隔离结果不一致。

这些信号只形成 `suspected_task_issue`。Task Package 是否需要降级、repair 和新 digest，由第五章的 Task Verifier 决定。

## 6.10 与 SKT 的继承和调整

| SKT Stage III | 本项目第六章 |
| --- | --- |
| fresh task–teacher–harness rollout | 完整保留，并固定 task、runtime、model、harness 与 prompt digests |
| full evaluator credit | MVP 默认完整保留 |
| normal termination and well-formed trace | 完整保留 |
| explicit required Skill access | 正式生产检查零暴露；独立实验仅记录 access event |
| LLM 检查每个 Skill 的实质且正确使用 | 调整为检查任务执行与科学过程一致性 |
| rejected rollout receives no feedback | 完整保留 |
| first passing attempt retained per pairing | 作为默认保留策略 |
| hidden verifier material excluded from trajectory | 完整保留 |

SKT 的 trajectory validator 要求每个 designated Skill 在相关 action 前被访问、影响具体决策并被正确应用；只打开或复述 Skill 不足以通过。本项目不继承这项准入要求，因为核心目标是采集正确完成科学任务的轨迹。Skill 使用研究可以在 Verified Trajectory Store 上另外分析，不改变第六章的合格定义。[SKT Trajectory-Side Qualification](https://arxiv.org/html/2608.02287v1#Sx2.SS4)

## 6.11 明确排除的操作

第六章不执行：

- 修改 Task Package、Recipe 或 Skills；
- 使用 verifier feedback 指导下一次 Solver；
- 编辑、拼接或补全失败轨迹；
- 把 paired with-Skill / without-Skill 结果作为 Task Package 的核心准入门槛；
- task difficulty calibration；
- 将 reference solution execution 当作 teacher trajectory；
- SFT chat-template 渲染、loss masking 和 train/eval split。

SFT 渲染、loss masking 和 train/evaluation split 进入第七章。Task、环境或 evaluator 缺陷回到第五章；知识缺陷继续回到第三章。

## 6.12 当前设计基线

- rollout 只消费 immutable Verified Task Package；
- 每个 attempt 使用新的 session、workspace 和 output state；
- 失败重试不接收历史 trajectory、evaluator outcome 或 verifier feedback；
- 原始轨迹保留 harness-native messages、tool calls、tool results 和终止信息；
- output artifacts 与轨迹分别计算 digest，并绑定同一 attempt ID；
- trajectory qualification 先运行 deterministic validator，再运行 Codex semantic Reviewer；
- 默认语义审核关注任务对应、科学过程和轨迹可信度；
- 正式生产检查 Recipe / Scientific Skills 零暴露；Skill access 仅用于独立实验观测；
- trajectory 不执行 repair，失败只触发 fresh retry；
- 只有两层验证都通过的 attempt 才进入 Verified Trajectory Store。

## 6.13 MVP Harness Adapter

以下为历史 batch adapter 实现记录，不代表当前正式 Solver 信息面；当前容器内交互执行以[第十二章](12-interactive-container-rollout.md)为准。

首个可运行 adapter 命名为 `codex-batch-docker/0.1.0`。它将模型推理与科学程序执行分成两个连续的受控步骤：fresh Codex Solver 在只包含 Task Card、公开 inputs、output contract、execution settings 和选定 Skills 的临时 workspace 中编写 `solution/`，并返回一个结构化 argv submission；Controller 冻结 Codex 原生事件和提交源码后，把该 submission 挂载进第五章验证过的 Docker image，只执行一次。模型在这一版中不会收到 Docker stdout、evaluator score 或修复反馈。

这种 batch 形态适合先验证 Recipe/Skill 到真实结果轨迹的完整数据合同。它保留了模型阅读知识、检查公开输入、形成实现和提交程序的原生过程，也保留了容器执行与 evaluator 的客观 lineage。它还不等同于带交互终端工具的 Agent harness；以后可以新增 `codex-interactive-docker` adapter，并继续复用相同的 Attempt、Artifact 和 Verification 合同。

隔离边界分成两层。提交程序在 Docker 中使用无网络、只读根文件系统、capability 全部移除以及 role-specific mounts，reference 和 evaluator 不会进入 Solver container。Codex 编写 submission 的会话当前运行于 host `workspace-write` sandbox：Controller 只主动呈现 Solver-visible snapshot，比较受保护文件前后 digest，并从完整 native trace 拒绝已知 hidden/reference/evaluator 路径访问。这个边界足以审计当前诚实数据生成实验，但还不是针对恶意 Solver 的内核级读取隔离；后续 interactive adapter 应通过独立 tool proxy 或 containerized harness 收紧 host read namespace。

对应实现位于：

- `src/skt_repro/scientific_rollout.py`：input binding、fresh attempt、Docker execution、attempt freeze、deterministic qualification、fresh retry 和 Reviewer orchestration；
- `schemas/solver-submission.schema.json`：batch submission 的最小 argv 合同；
- `schemas/trajectory-semantic-review.schema.json`：Trajectory Reviewer 输出合同；
- `pipeline-skills/trajectory-reviewer/`：科学过程与轨迹可信度审核 Skill；
- `examples/rollout-inputs/ndvi-reproduction-001/`：首个 Solver Configuration 与 Rollout Policy。

CLI 提供完整采集与独立复核两个入口：

```bash
PYTHONPATH=src python -m skt_repro collect-trajectory \
  runs/chapter-05/ale-ndvi-task-verification-003/verified-task.json \
  --accepted-knowledge runs/chapter-02/ale-ndvi-zonal-statistics-004/candidate-knowledge-bundle \
  --solver-config examples/rollout-inputs/ndvi-reproduction-001/solver-config.yaml \
  --policy examples/rollout-inputs/ndvi-reproduction-001/rollout-policy.yaml \
  --output runs/chapter-06/my-ndvi-trajectory

PYTHONPATH=src python -m skt_repro verify-rollout-attempt \
  runs/chapter-06/my-ndvi-trajectory/rollout-attempts/attempt-001
```

## 6.14 首次端到端结果

Canonical run 位于 `runs/chapter-06/ale-ndvi-trajectory-001`。输入是第五章冻结的 Task Package digest `sha256:b1dad93e…c35595` 和 clean-build image digest `sha256:1092d660…6619d`。Policy 允许两个 fresh attempts；第一个 attempt 已通过两层验证，因此 Controller 没有启动第二个会话。

| 项目 | 结果 |
| --- | --- |
| Solver | `gpt-5.6-sol`，reasoning effort `high` |
| Harness | `codex-batch-docker/0.1.0` |
| Solver model session | 267.276 秒，正常结束 |
| Native / public events | 39 / 42 |
| Tool-call completeness | 14 个 started calls 全部获得 completed result |
| Docker submission | 0.875 秒，return code `0` |
| Artifacts | `ndvi.tif` 与 `polygon_ndvi_stats.csv`，共 1200 bytes |
| Evaluator | score `1.0`，八项 checks 全部通过 |
| Deterministic qualification | 12 个 components 全部 `pass` |
| Trajectory Reviewer | 115.827 秒，qualified `accept` |
| Verified Trajectory digest | `sha256:0582b2a6…b81325b` |

该历史 skill-assisted 实验中，Solver 读取了 Task Card、公开 contract、fixture manifest 和两个 Scientific Skills，检查公开 raster/vector 元数据，随后独立编写了 `solution/solve.py`。该程序在最终 float32 raster 上执行 polygon statistics，使用 CRS reprojection 和 pixel-center inclusion，并在写表时处理六位小数与空区 `NA`。Docker evaluator 对 raster 结构、invalid mask、finite values、CSV schema、identifier coverage、属性与 counts、statistics 等八类事实全部确认通过。

Deterministic verifier 重新确认 terminal、evaluator contract、满分结果、required artifacts、artifact digest、size policy、native trace、information boundary、protected inputs、runtime digest、metadata binding 和 attempt digest。Fresh Trajectory Reviewer 随后判断任务—结果对应、科学过程和执行记录可信，输出 `accept`、`failure_category: none` 与空 blocking issues。最终 promotion record 为 `verified-trajectory.json`，它只引用冻结 attempt 和独立 verification record，不改写任何轨迹内容。

## 6.15 后续工程问题

第六章 MVP 已经冻结轻量产物和准入语义。后续扩展集中在 adapter 与规模化能力：增加具备受控交互式 Docker tool 的 Solver harness；把 Codex 编写会话也放入强读取隔离；为大型 artifacts 接入 content-addressed object store；为不同 task profile 审核部分分数 policy；在多个任务和模型上测量 Reviewer 对有效替代实现的误拒绝率。OpenCode、DeepAgents 等 harness 只需实现 native event 与 terminal status adapter，无需改变本章的两层验证边界。
