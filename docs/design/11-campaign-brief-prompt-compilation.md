# Campaign Brief 与阶段化 Prompt 编译

## 1. 设计目标

生产管线需要保持稳定，同时允许使用者针对一个数据生产批次说明目标、目标任务分布、期望调整、明确不做的内容和验收意图。Campaign Brief 是这层用户输入的版本化合同。

Campaign 不替代 Pipeline Skill，也不直接控制 Docker、网络、Skill 挂载或 Evaluator。能由程序确定的行为继续留在 Pipeline、rollout policy 和 runtime 配置中；需要 Agent 理解的批次意图由 Prompt Compiler 投影到相关阶段。

```text
Pipeline Core Contract
        +
Campaign Brief
        +
Stage Skill
        +
Current Stage Input
        ↓
Resolved Stage Prompt
```

对应实现：

- `schemas/campaign-brief.schema.json`：用户配置合同；
- `src/skt_repro/campaign.py`：加载、校验、投影、Prompt 编译与审计记录；
- `examples/production-pipeline/campaigns/tb-science-sft-v1.yaml`：Terminal-Bench-Science 定向示例；
- `ProductionPipelineSpec.campaign_brief`：可选 Campaign 入口。

## 2. Campaign Brief

Campaign 使用少量固定字段表达自由文本：

| 字段 | 含义 |
|---|---|
| `objective` | 本批次为什么生产数据 |
| `target` | 目标系统、执行协议、能力和任务形态 |
| `goals` | 希望产物具备的性质 |
| `adaptations` | 相对默认管线需要调整的方向 |
| `non_goals` | 明确排除的工作和产物 |
| `constraints` | Agent 需要理解的批次约束 |
| `acceptance` | 面向 Agent Reviewer 的验收意图 |
| `stage_guidance` | 只对某个阶段生效的补充说明 |
| `notes` | 仅向 Source Discovery 和 TaskGen 披露的补充背景 |

运行行为不要写进自由文本期待 Agent 自行遵守。例如 `skill_visibility: none`、容器网络、timeout、Verifier 隔离和资源限制应由现有结构化配置控制。

## 3. 阶段投影

Prompt Compiler 不会把完整 Campaign 拼进每个 Prompt。各阶段只接收完成职责所需的字段：

| Agent 阶段 | Campaign 投影 |
|---|---|
| Source Discovery | 目标、来源方向、调整项、排除项、约束、补充背景 |
| Knowledge Extraction | 目标、科学能力重点、调整项、排除项、约束 |
| Knowledge Review | 目标、排除项、约束、验收意图 |
| Task Generation | 完整任务生产意图与该阶段 guidance |
| Task Verification / Repair | 任务目标、调整项、排除项、约束、验收意图 |
| Solver Rollout | 不注入 Campaign |
| Trajectory Verification | 目标、排除项、约束、轨迹验收意图 |

`solver-rollout` 是显式的零字段投影。Campaign schema 也不允许配置 `stage_guidance.solver-rollout`。Solver 只接收公开任务说明、可见输入、执行环境、允许工具和独立 solver policy，防止上游生产意图成为解题提示。

## 4. Prompt 优先级

编译后的文本先呈现受限 Campaign Context，随后呈现原始 Stage Request。Campaign Context 固定声明它不能覆盖 Skill、阶段合同、科学证据、安全边界和输出合同。

```markdown
## Scoped Campaign Context

...本阶段相关的 Campaign 投影...

## Stage Request

...原有阶段请求、输入位置和输出合同...
```

Agent Factory 仍负责挂载 AgentSpec 中声明的 Skills。最终传给 Harness 的 Prompt 会保存为 `agent/resolved-prompt.md`；Campaign 编译层另外保存 Campaign 投影和哈希。

## 5. 运行与审计产物

顶层运行目录新增：

```text
run/
├── input/
│   └── campaign.yaml
├── resolved/
│   ├── campaign.json
│   ├── campaign-prompt-plan.json
│   └── pipeline-plan.json
└── .../agent/
    ├── campaign-prompt-envelope.json
    ├── campaign-context.md
    ├── campaign-resolved-prompt.md
    └── resolved-prompt.md
```

`pipeline-run.json` 绑定完整 compiled plan digest。新运行可以选择不提供 Campaign，以保持旧配置行为；提供 Campaign 的运行在续跑时如果 Agent、Skill、Campaign 或阶段投影发生变化，会拒绝复用原 manifest。

## 6. 新 Campaign 的使用方法

复制示例 Campaign，修改目标和阶段 guidance，然后在 Pipeline 配置中引用：

```yaml
schema_version: 0.1.0
pipeline_id: my-scientific-campaign-v1
agent_spec: glm53-codex-agent.yaml
skill_bundle: ../../pipeline-skills/bundles/scientific-production-v1.yaml
campaign_brief: campaigns/my-campaign.yaml
inputs:
  discovery_request: source-discovery/my-request.yaml
  materialization_policy: ../batch-inputs/scientific-20-v1/materialization-policy.yaml
  controls_root: controls
```

先编译配置，确认阶段投影和 Solver 边界：

```bash
PYTHONPATH=src python -m skt_repro.cli validate-production-pipeline \
  examples/production-pipeline/glm53-tb-science-xrd-source-discovery.yaml
```

再运行小批次：

```bash
set -a; source "$HOME/.config/skt-repro/runtime.env"; set +a
PYTHONPATH=src python -m skt_repro.cli \
  run-production-pipeline \
  examples/production-pipeline/glm53-tb-science-xrd-source-discovery.yaml \
  --output runs/production/tb-science-campaign-smoke \
  --limit 1
```

正式凭据只通过 `AgentSpec.model.api_key_env` 指定的环境变量提供，不能写入 Campaign、AgentSpec、Prompt 或交付包。

## 7. 与 Interactive Solver 的边界

Campaign 编译解决批次意图的可配置、最小披露和可审计问题。GLM/Codex Solver 已使用 `codex-interactive-docker`：Codex 在已验证科学任务镜像内直接运行软件、观察 stdout/stderr、修改并重跑。Campaign 仍只作用于上游生产和 Reviewer 阶段，Solver 保持零字段投影。执行与轨迹合同见 `docs/design/12-interactive-container-rollout.md`。
