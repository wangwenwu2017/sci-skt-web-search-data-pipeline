# 第五章 Task Package 与 Verify/Repair

> 状态：MVP 已实现并完成一次 Verify → Repair → Re-verify  
> 上级索引：[科学任务与轨迹数据生成设计](../scientific-data-generation-design.md)

## 5.1 章节目标

本章定义 Candidate Task Package 如何被证明为可运行、可求解、可评价且语义有效，并规定失败后的诊断、修复和重新验证流程。通过本章的任务才能进入 fresh Solver rollout。

主流程直接借鉴 SKT Stage II 的 rule-based verification、Agent-based semantic verification 和 feedback-guided repair。SKT 会先检查 package 与 reference execution，再由 LLM 检查任务语义，失败后把结构化反馈交给 TaskRepair，并在修复后从第一项检查重新开始。[SKT Stage II: Task Synthesis](https://arxiv.org/html/2608.02287v1#S3.SS2)

本项目保留这条控制流，并根据科学任务生产目标作出三项调整：加入 Accepted Recipe 与 Skills 的任务化忠实性审核；把 runtime clean qualification 和 evaluator 反例测试纳入可执行检查；把 paired skill dependence 与固定 Solver difficulty rollout 移出核心准入流程。

## 5.2 阶段合同

```text
Candidate Task Package@digest-N
Accepted Knowledge Bundle
Verification Policy
        ↓
Executable Qualification
├── package loading
├── clean runtime
├── workspace isolation
├── reference full credit
└── evaluator sanity
        ↓ pass
Codex + task-reviewer Skill
└── Task Semantic Validity
        ↓
   accept ───────────────→ Verified Task Package@digest-N
   revise/reject
        ↓
Structured Diagnosis
        ↓
Codex TaskRepair
        ↓
Candidate Task Package@digest-N+1
        └───────────────→ restart full verification
```

正常候选只经历一次 Executable Qualification 和一次 Agent semantic review。Executable Qualification 失败时不继续调用 semantic Reviewer，因为缺失文件、无法启动的环境或无效 evaluator 会使语义审核缺少可靠对象。

Task Package 内容在一次验证过程中保持只读。Repair 产生新的 package version 和 content digest，原候选及其验证证据继续保留，避免原地修改使旧结论失去对应对象。

## 5.3 Verifier 输入与信息面

### 5.3.1 输入

```text
Task Verification Input
├── candidate-task-package/
│   ├── task.json
│   ├── visible/
│   ├── skills/
│   ├── environment/
│   ├── hidden/
│   └── authoring/
├── accepted-knowledge-bundle/
├── source locators                 # optional：出现歧义时按需读取
└── verification-policy.md
```

`verification-policy.md` 提供 builder、网络、资源、超时、evaluator protocol 和允许的安全能力。Accepted Knowledge Bundle 是语义审核的主要依据；Knowledge Review 已经确认其来源忠实性，因此 Task Reviewer 只在 Recipe、Task 与 source evidence 出现冲突时回查 Source Bundle。

每次验证先计算完整 Task Package digest。后续日志、报告、repair feedback 和 registry 状态都引用该 digest，保证每个结论对应唯一内容版本。

### 5.3.2 可见性合同

| Surface | Solver | Reference runner | Evaluator | Task Reviewer |
| --- | --- | --- | --- | --- |
| `visible/TASK.md`、inputs、output contract | 可见 | 可见 | 可见 | 可见 |
| Recipe / selected `skills/` | 不可见 | 不可见 | 按需 | 可见 |
| `environment/` | 使用已构建 runtime | 使用同一基础 runtime | 使用 verifier runtime | 可见 |
| `hidden/reference-solution/` | 不可见 | 仅执行 reference 时可见 | 不需要 | 可见 |
| `hidden/evaluator/`、expected artifacts | 不可见 | 不可见 | 可见 | 可见 |
| `authoring/` | 不可见 | 不可见 | 不可见 | 可见 |

Reference solution 的代码本身属于 hidden asset，但执行时只能读取 Solver 可获得的 inputs 和公开任务合同。它不能通过读取 expected artifacts 或 evaluator internals 直接复制答案。

## 5.4 两层验证模型

### 5.4.1 Executable Qualification

Executable Qualification 使用确定性 loader、builder、runner 和 evaluator test harness，回答：

> 当前 package 能否从干净状态启动，并由 reference solution 产生 evaluator 认可的正确结果？

这一层包含必要的路径和格式检查，也包含真实 runtime build/start、reference execution 与 evaluator negative tests。它们统一形成一次 package qualification，不拆成多个语义评分维度。程序只对能够确定的事实做判断。

### 5.4.2 Task Semantic Validity

Task Semantic Validity 使用一个只读 Codex Reviewer，回答：

> 当前 package 是否把 Accepted Recipe 与 Skills 忠实地实例化成了清楚、合理且评价目标一致的具体科学任务？

Reviewer 综合查看 Task Card、input binding、selected Skills、runtime、reference、evaluator 和 executable evidence。它做一次整体语义判断，只报告会影响科学正确性、任务成立、评价有效性或信息隔离的实质问题。

两个层次都通过后，controller 才能将该 package digest 标记为 verified。

## 5.5 Executable Qualification

### 5.5.1 Package loading

Loader 读取 `task.json` 并解析各 surface 入口，确认：

- manifest、`visible/TASK.md`、inputs、selected Skills、runtime、reference 与 evaluator 均可定位；
- Recipe、Skill、input asset 和 runtime digest 与 lineage 一致；
- evaluator 与 reference 命令满足受支持的进程接口；
- relative paths 留在 package 或声明的受控 workspace 中；
- output paths 不覆盖 inputs、Skills、environment 或 hidden assets。

这些检查保障执行对象完整，不评价 Markdown 写作风格，也不限制领域内容的自由表达。

### 5.5.2 Runtime qualification

Runtime qualification 根据 `environment/runtime.yaml` 执行：

1. 对 `built` 或 `extended` runtime 从声明的 build context clean build；
2. 对 `reused` runtime 按不可变 digest 拉取或定位镜像；
3. 在不挂载 authoring residue 的新容器中运行 healthcheck；
4. 检查 architecture、working directory、关键软件与输入格式支持；
5. 确认 network、resource、timeout 和 mount policy 生效；
6. 保存最终 image digest、build log locator 和 healthcheck report。

输入以只读方式挂载，output workspace 可写，Recipe 与 Scientific Skills 不挂载给 Solver 或 reference runner。Solver runtime 中不出现 reference、evaluator、expected artifacts、authoring trace、builder credentials 和历史运行结果。

### 5.5.3 Reference execution

Reference runner 创建 fresh workspace，只放入本任务的 visible inputs、Task Card、output contract 和 selected Skills。随后在已 qualification 的 runtime 中执行 hidden reference command。

Reference execution 必须满足：

- 进程正常结束；
- 只在允许的 output workspace 写入最终 artifacts；
- 所有 required outputs 均产生且可读取；
- evaluator 正常完成并返回最高可得分数；
- reference 没有读取 expected artifacts、evaluator internals 或 authoring-only 文件；
- 输出和运行证据与当前 package digest 绑定。

Reference 满分证明任务至少存在一个可执行正确解。它不证明 Task Card 对普通 Solver 足够清楚，因此仍需后续 semantic review。

### 5.5.4 Evaluator process contract

MVP evaluator 使用统一命令接口，由 `task.json` 给出 command 和参数。Evaluator 在任务结束后获得 Solver output、公开 output contract 和 verifier-only assets，并向 stdout 返回一份 JSON report：

```json
{
  "score": 1.0,
  "checks": {
    "artifacts_readable": true,
    "schema_valid": true,
    "scientific_values_valid": true
  },
  "details": []
}
```

- `score` 归一化到 `[0, 1]`；
- `checks` 提供可聚合的判定项；
- `details` 只保存简洁诊断，不输出 hidden gold values；
- 退出码 `0` 表示 evaluator 正常完成，任务得分由 `score` 表示；
- 非零退出码、无 JSON 或越界分数属于 evaluator infrastructure failure。

任务可以使用部分分数。Reference 必须达到 `1.0`；后续 Solver trajectory 是否进入训练集由第六章根据 evaluator outcome 与 trajectory quality 决定。

### 5.5.5 Evaluator sanity tests

Evaluator 需要证明自己能区分正确结果和明显无效结果。Test harness 至少覆盖以下行为类型：

- empty workspace 或完全缺失 required outputs；
- 无法读取、格式错误或关键 schema 缺失的 artifact；
- 一个来自 output contract 或 Recipe 的代表性科学错误，例如反向差值、错误单位、错误 CRS、丢失行、错误 flagged subset 或阶段关系断裂。

反例数量根据任务性质决定，不设统一配额。关键要求是 evaluator 不能只检查文件存在，也不能让一个与科学目标明显冲突的结果获得通过分数。反例可以由 Task Author 提供，也可以由 qualification harness 根据 reference artifact 生成受控 mutation；所有 mutation 及其期望判定都进入验证记录。

### 5.5.6 Information isolation

Qualification 对实际 Solver workspace 做最终快照，确认 visible surface 之外没有：

- Campaign、Recipe、Scientific Skills 及其 references/scripts/assets；
- reference solution、gold values 和 expected artifacts；
- evaluator code、阈值实现或 hidden fixtures；
- authoring trace、repair feedback 和验证报告；
- source 中直接给出当前任务答案的残留文件；
- runtime layer、缓存、shell history 或环境变量中的任务答案。

文本级 hash 或路径扫描可以发现直接复制；复杂语义泄露交给 Task Reviewer 判断。

## 5.6 Codex Task Reviewer

### 5.6.1 运行方式

Executable Qualification 通过后，controller 启动一个 fresh Codex 任务并加载 `task-reviewer` Skill。Reviewer 对 Candidate Task Package、Accepted Knowledge Bundle 和 verification evidence 只读，唯一正式产物为 `semantic-review.json`。

建议使用轻量 Skill 结构：

```text
task-reviewer/
├── SKILL.md
└── references/
    └── review-output.md
```

`SKILL.md` 直接保存稳定审核逻辑；`review-output.md` 保存 verdict 与 blocking issue 合同。Reviewer 先读取 Recipe、Task Card、output contract 和 selected Skill metadata，再按需查看 inputs、reference、evaluator、runtime evidence 和 source locators。

### 5.6.2 审核内容

Reviewer 综合判断以下关系：

**忠实任务化**

- task mode、具体目标、参数变化和故障设计受到 Recipe 支持；
- input binding 满足 Skill 前提、单位、schema 和科学条件；
- Task Author 没有为制造难度加入新的科学规则；
- selected Skills 与任务阶段具有明确关系，数量由任务本身决定。

**任务成立**

- `TASK.md` 清楚表达目标、可用输入、required outputs 和约束；
- Solver 能在本地环境中获得完成任务所需的信息和软件；
- output contract 允许合理的多种实现，同时能排除无效结果；
- reproduction、controlled variable、multi-stage 或 diagnostic recovery 的实例关系成立。

**评价一致性**

- evaluator 衡量的内容与公开任务目标一致；
- reference solution 实际解决的是同一个任务；
- 评分权重、容差和 hard failures 符合 Recipe 的科学不变量；
- evaluator 不依赖 Solver 无法知道的未声明要求；
- partial score 不会让关键科学错误获得等同通过的结果。

**信息边界**

- visible files 没有泄露当前实例的 gold values、hidden answer 或 evaluator implementation；
- Task Card 可以陈述必要科学条件，但不复制本应由 mounted Skill 提供的完整操作答案；
- hidden assets 与 authoring information 保持 verifier-only。

### 5.6.3 Verdict 与输出

Reviewer 输出一个 Task Semantic Validity verdict：

| Verdict | 含义 |
| --- | --- |
| `accept` | 没有发现影响任务忠实性、成立性、评价一致性或信息边界的问题 |
| `revise` | 任务整体成立，但存在清楚且可以修复的阻塞问题 |
| `reject` | 当前任务目标、输入或验证逻辑无法在合理 repair 内成立 |

```json
{
  "verdict": "revise",
  "summary": "The task is executable, but the evaluator rewards a proxy that does not establish the Recipe's scientific result.",
  "blocking_issues": [
    {
      "target": "hidden/evaluator",
      "issue": "The evaluator checks only output row count and omits the declared derived values.",
      "impact": "Scientifically incorrect results can receive a passing score.",
      "suggested_action": "Add source-supported value checks keyed by the stable identifier."
    }
  ]
}
```

Reviewer 最多报告三个实质 blocking issues，不提供综合数字分数，不重写 package，也不调用 TaskRepair。

## 5.7 Verification Record 与 Promotion

验证证据保存在 Task Package 之外，并按 package digest 组织：

```text
task-verification/<task-id>/<package-digest>/
├── report.json
├── executable/
│   ├── package-load.json
│   ├── runtime-report.json
│   ├── reference-run.json
│   ├── evaluator-tests.json
│   └── workspace-isolation.json
└── semantic-review.json
```

顶层 `report.json` 汇总：

```json
{
  "task_id": "crop-rotation-reproduction-001",
  "package_digest": "sha256:<digest>",
  "executable_qualification": "pass",
  "semantic_validity": "accept",
  "verified": true
}
```

`verified` 由 controller 根据两项结果确定，不由 LLM 自行决定。通过后，Registry 把同一个 immutable package digest 标记为 verified；Task Package 内容不因 promotion 被修改。这样验证前后使用相同 digest，后续 rollout 可以准确绑定已验证对象。

## 5.8 Feedback-guided TaskRepair

### 5.8.1 Repair 输入与运行方式

Repair 使用一个新的 Codex 任务加载 `scientific-task-author` Skill 的 repair mode，接收：

```text
TaskRepair Input
├── failed Candidate Task Package@digest-N
├── Accepted Knowledge Bundle
├── executable diagnosis 或 semantic blocking issues
├── verification evidence locators
└── repair context and budget
```

复用 Task Author Skill 可以保持 TaskGen 与 repair 的产物合同一致。Repair Agent 只修改诊断涉及的 surface，并检查相关引用；如果修改 output contract，就同时检查 Task Card、reference 和 evaluator；如果修改 runtime，就重新确认 reference 与 evaluator 的执行依赖。

### 5.8.2 Repair 分类

| Failure owner | 典型问题 | 处理方式 |
| --- | --- | --- |
| Task Card / binding | 任务描述歧义、错误路径、无效参数绑定 | 修订 visible task 与关联 metadata |
| Environment | build 失败、缺失依赖、mount 或权限错误 | 修订 runtime artifacts |
| Reference | 无法执行、写错路径、未解决完整任务 | 修订 reference solution |
| Evaluator | 崩溃、漏检、代理指标、容差错误 | 修订 evaluator 与 tests |
| Knowledge | Recipe/Skill 缺少规则或内部冲突 | 停止 TaskRepair，返回 Knowledge Repair |
| Source asset | 数据缺失、损坏或不满足前提 | 返回 Asset Resolution 或重新绑定输入 |

Repair 不改变科学目标来绕过 verifier，也不通过放宽关键检查让错误结果通过。需要改变 task mode、科学规则或任务族时，controller 创建新的 Task Author Request，并保留当前候选的失败记录。

### 5.8.3 新版本与重新验证

Repair 以 copy-on-write 方式产生 `Candidate Task Package@digest-N+1`，记录 parent digest、修改文件、对应 blocking issue 和 repair run ID。任何 repair 完成后都从 Executable Qualification 第一项重新开始，因为 package 中一个局部变化可能影响 runtime、reference、evaluator 或信息边界。

Controller 为每个 request 配置有限 repair budget。预算属于运行策略，不写入 Recipe、Skill 或 Task Package 语义合同。预算耗尽后候选进入 `repair_exhausted`，保留失败证据供统计和人工分析。

Reviewer 调用本身出现 API、超时或结构化输出合同错误时，controller 使用 `retry_semantic_reviewer`。该路径只复用已经通过且仍绑定同一 immutable package digest 的 executable evidence；它不属于 TaskRepair，也不会修改 Candidate。每次重试保存独立目录和旧报告历史。

## 5.9 明确排除的检查

第五章不执行：

- paired with-Skill / without-Skill rollout；
- leave-one-Skill-out necessity 判断；
- 固定 Solver 的经验 pass-rate difficulty Gate；
- teacher Solver 的正式 trajectory collection；
- trajectory 中 Skill 使用质量判断；
- SFT 序列化与 loss masking；
- 对 Task Card 非阻塞写作风格的评分。

Skill dependence 和 difficulty calibration 可以作为独立研究实验附加到 verified task，不影响核心生产链准入。Fresh rollout 与 trajectory validation 进入第六章。

## 5.10 与 SKT 的继承和调整

| SKT Stage II | 本项目第五章 |
| --- | --- |
| Rule-based package check | Executable Qualification，增加 clean Docker 与 evaluator mutations |
| Reference solution full evaluator credit | 完整保留，并限制 reference 只读取 Solver 可得材料 |
| Agent semantic validity | Codex Task Reviewer，增加 Recipe/Skill 忠实任务化 |
| Visible/hidden leakage check | 完整保留，并检查 runtime layer、缓存和 authoring residue |
| Paired skill dependence | 移出核心流程 |
| Fixed-solver difficulty control | 改为可选 task calibration |
| First blocking feedback to TaskRepair | 保留两层顺序，单层最多三个实质问题 |
| Repair 后从 rule gate 重启 | 保留，且每次 repair 产生新 package digest |

SKT 论文公开了 verifier 接口、通过条件和控制流，没有公开完整 prompt 与实现源码。本章据此定义可独立实现、能够审计且适用于 Scientific Recipe/Skill 的 verification contract。[SKT Detailed Qualification Criteria](https://arxiv.org/html/2608.02287v1#Sx2)

## 5.11 已确认结论

- 第五章采用 SKT 的 executable verification、Agent semantic verification 和 feedback-guided repair 主链；
- 正常候选只运行一次 Executable Qualification 和一次 Codex semantic review；
- reference solution 必须在 fresh workspace 中获得 evaluator `1.0`；
- evaluator 必须拒绝 empty output、结构错误和至少一种代表性科学错误；
- Task Reviewer 判断忠实任务化、任务成立、评价一致性和信息边界；
- paired skill dependence 与 pass-rate difficulty Gate 不进入核心流程；
- Reviewer 只诊断，TaskRepair 在新的 Codex run 中修改；
- Repair 产生新的 immutable package version，并从完整 qualification 重新开始；
- verification evidence 按 package digest 外置保存；
- 只有 executable `pass` 且 semantic `accept` 的 digest 才能进入 fresh rollout。

## 5.12 当前合同决策与后续问题

MVP 沿用第四章的 `task.json` 与 `runtime.yaml`。Evaluator stdout 固定包含 `score`、`passed`、布尔 `checks` 和字符串 `diagnostics`。Reference 需要 `passed=true` 且达到 policy 指定分数；负例需要 `passed=false` 且分数不超过各自上限。具体 mutation 位于外部 Verification Policy，避免进入 Solver-visible Task Package。

`built` 与 `extended` runtime 从 Dockerfile 和 locks clean build，并记录本次 OCI image digest。Authoring smoke 的 image digest 作为历史构建证据保存，无缓存重建可以产生新的 OCI manifest；实际依赖能力继续由 healthcheck、reference 和 evaluator 验证。`reused` runtime 直接定位声明镜像，并要求 observed digest 与声明值一致。

大型 external assets 的 manifest-of-digests、默认 repair budget、builder 并发与远端缓存仍留到多任务运行时确定。当前 prototype 对一个小型 Task Package 做完整字节快照。

## 5.13 MVP 实现与真实运行

实现入口为 `skt-repro verify-task-package`。Controller 将 Candidate、Accepted Knowledge、Verification Policy、Task Reviewer Skill 和可选 Source evidence 复制到独立 input snapshot，随后按角色启动 Docker：Solver view 只挂载 visible、inputs 和空 outputs；reference 额外挂载 reference solution；evaluator 只挂载 evaluator。容器统一关闭网络、丢弃 capabilities、启用只读 root filesystem，并保存完整 argv、stdout、stderr、时间和输出 inventory。

首轮有效验证对象是第四章的 `task:ndvi-zonal-statistics-reproduction-001` version 1，digest 为 `sha256:3bebe31b…b363f9a`。Executable Qualification 通过 clean build、healthcheck、workspace isolation、reference `1.0`、空输出、不可读产物和 NDVI 符号反转负例。Fresh Task Reviewer 随后给出 `revise`：公开合同要求 GeoTIFF，evaluator 没有检查 raster driver，内容正确的 VRT 可能通过。该结果保存在 [`ale-ndvi-task-verification-002`](../../runs/chapter-05/ale-ndvi-task-verification-002)。

`skt-repro repair-task-package` 使用 fresh Codex 与 `scientific-task-author` repair mode 生成 version 2。Repair 保留父包，新增 `output_dataset.driver == "GTiff"` 检查，将 candidate version 增加一次，并记录五个实际 changed files。新 digest 为 `sha256:b1dad93e…c35595`，repair 证据见 [`ale-ndvi-task-repair-001`](../../runs/chapter-05/ale-ndvi-task-repair-001)。

Version 2 从 package loading 完整重验。Reference 仍获 `1.0`；四个负例分别得到 `0.0`、`0.0`、`0.75` 和 `0.875` 且全部 `passed=false`。新增的 readable non-GeoTIFF VRT 只触发 raster structure failure，直接证明 repair 覆盖原 blocker。Fresh Reviewer 给出 `accept`，controller 对同一 digest 写入外置 promotion record，并路由到 fresh rollout。Canonical 结果见 [`report.json`](../../runs/chapter-05/ale-ndvi-task-verification-003/report.json)、[`semantic-review.json`](../../runs/chapter-05/ale-ndvi-task-verification-003/semantic/semantic-review.json) 和 [`verified-task.json`](../../runs/chapter-05/ale-ndvi-task-verification-003/verified-task.json)。

实现过程中还保留两类 controller 自身失败证据。第一次将 `built` 镜像重建 digest 当成强一致条件，实际比较确认依赖版本相同而 OCI 构建层元数据变化，因此该规则只对 `reused` 镜像强制。Structured Outputs Schema 的两次 API 拒绝分别暴露了不受支持的 `allOf` 和缺失显式 `type`；修正后通过 semantic-only retry 完成内容审核。这些记录使 verifier 错误与 Task blocker 能够分开追踪。
