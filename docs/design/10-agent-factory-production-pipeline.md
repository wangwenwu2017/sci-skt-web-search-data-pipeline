# Agent Factory 与 GLM-5.3 批量生产管线

## 1. 目标与首版边界

本阶段将已有科学数据链路整理为协议驱动的八阶段批量生产模块。一次 Agent 运行由 `AgentSpec` 绑定 Harness、模型供应商、模型协议、凭据环境变量和采集策略；Pipeline Skills 由独立 Bundle 绑定到语义阶段；确定性代码继续负责来源检索资格检查、来源冻结、目录与哈希、Docker、Evaluator、准入、修复路由、断点续跑和数据集序列化。

首版生产配置使用 Codex Harness 和 GLM-5.3。Codex 官方当前只向自定义 Provider 发送 Responses API，因此 GLM 服务必须提供兼容的 `/responses` 端点。透明 Recording Gateway 已经接入 Codex 的模型边界，会保存经过凭据脱敏的原始请求体、原始响应体、完整 SSE 字节流和解析后的事件投影。Chat Completions 到 Responses 的协议转换留在后续版本，首版遇到协议不匹配会直接拒绝配置。

智谱公开文档当前展示的直接模型接口是 `/chat/completions`。该官方地址不能直接填入首版 Codex AgentSpec；首版需要一个已经暴露 Responses API 的 GLM Gateway。`probe-agent-provider` 会在生产前用真实 Shell tool call 检查协议、流式事件、工具闭环和原始记录，失败的 Provider 不进入批量运行。

Factory 当前注册两个可执行 Adapter：

- `codex`：支持自定义 Responses Provider 和 Recording Gateway；
- `kimi-code`：复用已有隔离 Docker Harness 和 Recording Gateway。

生产 Solver 使用 `codex-interactive-docker/0.1.0`。Agent Factory 的 Provider 合同会传递给 rollout controller；Codex 本身运行在已验证科学任务镜像内，Gateway 仍运行在宿主侧。该分层让上游 TaskGen/Reviewer 和下游 Solver 共用模型配置，同时维持不同的文件与网络权限。

协议预留了 `claude-code`，当前没有注册执行 Adapter。加载该配置会返回明确的 `HarnessUnavailableError`，不会静默退化到其他 Harness。

## 2. 组件关系

```text
ProductionPipelineSpec
├── AgentSpec
│   ├── HarnessSpec
│   ├── ModelProviderSpec
│   └── CaptureSpec
├── SkillBundleSpec
├── CampaignBrief（可选，按阶段投影）
├── Source Discovery Request 或现有 Source Selection
├── Materialization/Controls bindings
└── Execution policy
        ↓
AgentFactory
├── CodexHarnessAdapter
└── KimiCodeHarnessAdapter
        ↓
Recording Gateway
        ↓
GLM-5.3 Provider
```

Campaign Brief 只表达本批次的生产意图。`CampaignPromptCompiler` 根据阶段注入目标、调整项、non-goals、验收意图和 `stage_guidance`；Solver rollout 使用显式零字段投影，不接收 Campaign。完整协议、产物和扩展方法见 `docs/design/11-campaign-brief-prompt-compilation.md`。

`AgentFactory` 只创建并配置 Harness Runner。科学阶段仍由现有类型化函数执行，Runner 通过依赖注入进入这些函数。这样保留了已经验证过的输入隔离、Repair、Docker 和 Evaluator 逻辑，也避免出现一套旧管线与一套 Factory 旁路管线。

## 3. 八个生产阶段

| 阶段 | 执行方式 | Pipeline Skill | 主要输入 | 主要输出 |
|---|---|---|---|---|
| Source Discovery | Codex + 合同检查 | `scientific-benchmark-source-scout` | Benchmark、Task Card、数量与配比 | locator Source Bundles、catalog、selection |
| Source Materialization | 确定性代码 | 无 | source selection、固定 commit、materialization policy | Source Bundles 与 inventory |
| Knowledge Extraction | Codex + GLM-5.3 + 代码检查 | `scientific-knowledge-extractor` | Source Bundle | Candidate Recipe、Scientific Skills、registry |
| Knowledge Review | Codex + GLM-5.3 + 合同检查 | `knowledge-reviewer` | Candidate Knowledge 与来源证据 | 双判断 review 与 routing |
| Task Generation | Codex + GLM-5.3 + package qualifier | `scientific-task-author` | Accepted Knowledge、Task request | Candidate Task Package 与 Docker runtime |
| Task Verification / Repair | Docker + Codex Reviewer/Repair | `task-reviewer`、`scientific-task-author` | Candidate Task Package、verification policy | Verified Task 或 copy-on-write repaired candidate |
| Rollout / Trajectory Verification | Codex Solver + Docker + Reviewer | 正式 Solver 不接收 Recipe / Scientific Skills；Reviewer 使用 `trajectory-reviewer` | Verified Task、ALE-like solver view | rollout attempt、Evaluator outcome、verified trajectory |
| Dataset Release | 确定性代码 | 无 | Verified Trajectories | Raw release、SFT records、release manifest |

Source Discovery 是可选执行、固定存在的第零阶段。配置提供 `discovery_request` 时由 Codex + Skill 生成 selection；配置提供已有 `selection` 时，该阶段记录 `provided-selection` 并直接完成。两个入口在 Source Materialization 之前汇合。`run_downstream_batch` 内部继续维护 TaskGen、Task Verification/Repair 和 Trajectory 的 item-level 状态。顶层 `pipeline-run.json` 记录八个逻辑阶段，两个层级的 manifest 共同支持批次恢复和单任务重试。

## 4. 原始模型响应

每次通过配置化 Codex Runner 发起调用，Agent 日志目录增加：

```text
agent/
├── agent-spec.json
├── events.jsonl
├── final-message.md
├── stderr.log
└── gateway/
    ├── manifest.json
    └── completions/
        └── 0001-<request-id>/
            ├── request.body
            ├── request.json
            ├── response.body
            ├── response-events.jsonl
            └── record.json
```

`request.body` 与 `response.body` 是模型边界的事实源。JSON 和 JSONL 文件属于可读投影，便于审查和后续标准化。Gateway 不持久化 Authorization、Cookie 或 API Key；上游 GLM Key 只存在于宿主 Gateway 进程。Codex 子进程只获得一次性的 Gateway Token，环境中会主动移除上游 Key。

Responses API 标准化器当前支持文本增量、reasoning summary、function/custom tool call、工具输出和 usage。它只保存服务实际返回的 reasoning 信息；服务没有返回的内部思考不会被推断或补写。

## 5. Skills 的组织方式

生产 Bundle 位于 `pipeline-skills/bundles/scientific-production-v1.yaml`。每个条目记录 Skill ID、只读路径、`SKILL.md` SHA-256 和使用阶段。加载 Pipeline 时会重新计算 digest，任何未更新 Bundle 的 Skill 修改都会让配置编译失败。

Agent 级 `skills` 字段适合给某个 Harness 固定挂载操作能力。当前生产配置保持该列表为空，因为各阶段已经按职责挂载独立 Pipeline Skill。Scientific Recipe/Skill 仍属于科学知识资产；ALE-like Solver 的 `skill_visibility` 为 `none`，Reviewer 可以读取知识资产进行科学有效性判断。

六个 Pipeline Skills 均通过 `skill-creator` 的 `quick_validate.py` 检查。它们继续采用渐进披露：核心步骤位于 `SKILL.md`，具体合同和判断规则位于一层 `references/`。

`scientific-benchmark-source-scout` 只负责从 Benchmark 到 locator Source Selection。它执行第一方入口核验、实体去重、数量与配比控制、Benchmark 资产隔离，并为每个来源提出 task opportunity 和 verifier 形态。Recipe/Skill 抽取仍由 `scientific-knowledge-extractor` 完成。

## 6. 配置与运行

模板配置：

- `examples/production-pipeline/glm53-codex-agent.yaml`
- `examples/production-pipeline/glm53-scientific-production.yaml`
- `examples/production-pipeline/glm53-tb-science-xrd-source-discovery.yaml`
- `examples/production-pipeline/campaigns/tb-science-sft-v1.yaml`
- `examples/production-pipeline/controls/`

已有 selection 的批次继续使用：

先确认 AgentSpec 使用真实 GLM Responses 地址，并通过用户自己的 0600 环境文件提供 Key：

```bash
set -a; source "$HOME/.config/skt-repro/runtime.env"; set +a

PYTHONPATH=src python -m skt_repro.cli probe-agent-provider \
  examples/production-pipeline/glm53-codex-agent.yaml \
  --output runs/provider-probes/glm53-codex-001

PYTHONPATH=src python -m skt_repro.cli validate-production-pipeline \
  examples/production-pipeline/glm53-scientific-production.yaml

PYTHONPATH=src python -m skt_repro.cli run-production-pipeline \
  examples/production-pipeline/glm53-scientific-production.yaml \
  --output runs/production/glm53-scientific-production-v1 \
  --limit 1
```

从 Benchmark 自动发现来源时使用：

```bash
PYTHONPATH=src python -m skt_repro.cli validate-production-pipeline \
  examples/production-pipeline/glm53-tb-science-xrd-source-discovery.yaml

PYTHONPATH=src python -m skt_repro.cli run-production-pipeline \
  examples/production-pipeline/glm53-tb-science-xrd-source-discovery.yaml \
  --output runs/production/glm53-tb-science-xrd-v1
```

Discovery Request 可以指定 `target_count`、direct/variant/frontier 配比、领域和来源偏好。缺省配比和 Source Bundle 合同由 Source Scout Skill 决定。只有完成数量、去重、去污染和 materialization handoff qualification 的 selection 才能进入下一阶段。

正式批量运行移除 `--limit 1`。中断后使用相同配置和输出目录重新执行即可恢复；需要重试已标记失败的 item 时增加 `--retry-failed`。

`--limit` 会同时约束来源物化、知识处理和下游任务，单条试跑不会预先下载整批仓库。`inputs.repository_cache` 是可选的预置只读 Git 缓存，目录中需要按 bundle ID 保存已经克隆的仓库；默认模板省略该字段，因此在缺少缓存时会按 selection 中锁定的 commit 获取官方来源。

## 7. 产物布局

```text
runs/production/<pipeline-id>/
├── pipeline-run.json
├── pipeline-report.json
├── source-discovery/
│   └── candidate-source-selection/
│       ├── REPORT.md
│       ├── catalog.jsonl
│       ├── selection.yaml
│       └── source-bundles/
├── materialized-source-bundles/
├── knowledge/
│   ├── batch-run.json
│   └── items/<source-id>/...
├── downstream/
│   ├── downstream-batch-run.json
│   └── items/<source-id>/...
└── dataset/<release-name>/
```

每个 Agent attempt 内部拥有独立 Gateway capture。批次级 manifest 只保存路径、状态和稳定绑定，不复制原始响应内容。

## 8. 后续工程项

首版可以验证 Factory、GLM Responses 兼容性、阶段 Skills、原始响应采集和完整批次恢复。正式生产前还需要完成两项实跑工作：

1. 使用选定 GLM 服务完成 Responses、SSE、tool call、tool output、usage 和 reasoning 字段的 capability probe；
2. 对接 Harbor/Terminal-Bench-Science 的任务导入导出层，在不改变 `codex-interactive-docker`、Gateway episode 和 Verifier 合同的前提下适配其 registry 与提交格式。
