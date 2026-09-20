# Codex Interactive Container Rollout

## 1. 目标

`codex-interactive-docker/0.1.0` 让 Codex、Shell、科学软件、输入文件、工作代码和输出目录处于同一个已验证的任务镜像中。Agent 可以读取任务，执行科学软件，观察 stdout、stderr 和退出状态，修改代码或参数并重新运行。Solver 会话结束后，Controller 才挂载隐藏 Evaluator 对输出进行独立评分。

这条执行路径用于 ALE-like capability 和 Terminal-Bench-Science 定向数据生产。正式 Solver 不接收 Campaign、Recipe、Scientific Skills、Reference Solution 或 Evaluator。

## 2. 执行边界

```text
Host Controller
├── Upstream model credential
├── Recording Gateway
├── hidden Evaluator
└── verified image binding
          │ Unix socket：仅模型流量
          ▼
Scientific Task Container
├── Codex native binary（只读挂载）
├── TASK.md / inputs / public contracts（只读重挂载）
├── solution/（可写）
├── outputs/（可写）
├── installed scientific software
├── loopback HTTP → Unix socket relay
└── network=none
```

容器使用只读根文件系统、`cap-drop=ALL`、`no-new-privileges`、PID/CPU/内存限制和独立 tmpfs。Codex 使用 `--dangerously-bypass-approvals-and-sandbox`，因为 Docker 已经承担外部安全边界；这不会扩大容器之外的文件或网络权限。

任务镜像需要提供 `python`，用于启动约 70 行的 loopback-to-Unix relay。当前 TaskGen 生成的科学镜像及已有验证任务均满足该要求。Codex 的静态原生二进制从本机已安装 CLI 解析并只读挂载，无需在每个科学镜像中安装 Node.js 或 Codex npm 包。

## 3. 输入合同

主生产管线使用三份结构化输入：

- `AgentSpec.model`：Responses-compatible Provider、模型名、API Key 环境变量和协议；
- `controls/solver-config.yaml`：声明 `codex-interactive-docker/0.1.0`、模型和 Prompt 版本；
- `controls/rollout-policy.yaml`：声明 `skill_visibility: none`、`task_presentation: ale-like`、超时、尝试次数、网络和满分门槛。

Solver-visible workspace 固定为：

```text
/workspace/
├── TASK.md
├── inputs/
├── output-contract.md
├── execution-settings.yaml
├── solution/
└── outputs/
```

`TASK.md`、`inputs/` 和两个公开合同在容器内再次以只读 bind mount 覆盖。即使 Codex 拥有容器内 Shell，也无法改写这些输入。

## 4. 运行产物

每个 attempt 同时保留 Harness、模型边界、结果和验证证据：

```text
attempt/
├── agent/
│   ├── events.jsonl
│   ├── stderr.log
│   ├── final-message.md
│   └── gateway/
│       ├── manifest.json
│       └── completions/*/{request.body,response.body,response-events.jsonl}
├── trajectory/
│   ├── native.jsonl
│   ├── native-facts.json
│   ├── events.jsonl
│   ├── episode.jsonl
│   ├── episode-manifest.json
│   └── episode-qualification.json
├── artifacts/files/
├── outcome/{terminal.json,evaluator.json}
└── attempt.json
```

`request.body` 和 `response.body` 是实际模型调用的脱敏事实源。`episode.jsonl` 按时间顺序投影 initial messages、assistant thinking、assistant content、tool calls、tool results 和最终 reward；每个事件保留回到 Gateway 原始记录的 locator 与 digest。

## 5. 验证逻辑

确定性资格检查要求：

- Codex 正常结束且任务镜像 digest 未漂移；
- 至少存在一次完成的 Shell 调用；
- Gateway capture 完整、请求数量一致、凭据未进入请求或响应正文；
- 容器为 `none-with-unix-model-gateway`；
- 原始 Responses 中存在模型返回的 reasoning，不补写或推断 thinking；
- 公开输入未改变，未访问 Skill 或已知隐藏路径；
- 必需 artifacts 存在、大小合规、Evaluator 满足要求；
- `episode.jsonl` 的顺序、tool call/result 配对、证据 locator 和 digest 全部通过。

确定性检查通过后，原有独立 Trajectory Reviewer 继续判断科学过程与任务结果是否对应。通过的 attempt 才能写入 `verified-trajectory.json` 并进入 Dataset Release。

## 6. Dataset 与 SFT

Raw 层保留 native Codex trace、Gateway episode、原始 Gateway manifest、artifact 和验证 locator。SFT 层从 Gateway-authoritative episode 派生以下监督片段：

- assistant thinking；
- assistant messages；
- assistant tool calls；
- tool results，loss 为 `0`；
- public system/user context，loss 为 `0`。

Interactive 数据不再伪造 `batch_submission`。模型原始请求、流式 response 和 episode 始终保留，具体训练任务可以在发布后转换为 GLM、Kimi 或其他 trainer 所需的 chat template。

## 7. 使用方法

Codex + GLM-5.3 是当前交互式 rollout 的默认 Harness。通用入口也接受
`--harness kimi-code`，但只有在需要复用历史 Kimi 实验时才显式选择它；这不会改变
Codex 路径的采集格式。

单任务运行：

```bash
# The file is user-only (0600); its value is never printed or written to runs.
set -a; source "$HOME/.config/skt-repro/runtime.env"; set +a
PYTHONPATH=src python scripts/run_codex_interactive_scientific_task.py \
  /absolute/path/to/verified-task.json \
  /absolute/path/to/run \
  --agent-spec examples/production-pipeline/glm53-codex-agent-ppapi.yaml
```

也可以使用统一入口：

```bash
PYTHONPATH=src python scripts/run_interactive_scientific_task.py \
  /absolute/path/to/verified-task.json \
  --output /absolute/path/to/run \
  --harness codex \
  --agent-spec examples/production-pipeline/glm53-codex-agent-ppapi.yaml
```

统一批量入口同样默认 Codex，并从 `--agent-spec` 读取模型、Responses 协议和
`GLM_API_KEY` 环境变量名：

```bash
PYTHONPATH=src python scripts/run_interactive_task_batch.py \
  --source-report /absolute/path/to/source-report.json \
  --source-run /absolute/path/to/source-run.json \
  --output /absolute/path/to/batch \
  --agent-spec examples/production-pipeline/glm53-codex-agent-ppapi.yaml \
  --workers 2
```

每个 batch item 的 `agent/session/gateway/completions/` 下都会保存独立的
`request.body`、`request.json`（可解析时）、`response.body` 和
`response-events.jsonl`（流式响应时）。原始 `response.body` 是不可替代的证据；
若上游 GLM 返回 Responses reasoning 事件，聚合后的 `native-facts.json` 和
`episode.jsonl` 会保留/统计它，否则只记录“未返回 reasoning”，不会自行补写。

完整批量管线使用既有入口；`examples/production-pipeline/controls/solver-config.yaml` 已切换到 interactive harness：

```bash
PYTHONPATH=src python -m skt_repro.cli run-production-pipeline \
  examples/production-pipeline/glm53-tb-science-xrd-source-discovery.yaml \
  --output runs/production/tb-science-v1 \
  --limit 1
```

先运行无需凭据的控制实验可以验证本机 Docker、Codex binary、Unix Gateway 和 episode 层：

```bash
PYTHONPATH=src python scripts/smoke_codex_interactive_container.py \
  --image '<verified-scientific-image>' \
  --output /tmp/codex-container-control
```

控制实验使用确定性本地 Responses 服务，只能证明 Harness 和验证链路正确，不能当作模型能力结果或训练样本。
