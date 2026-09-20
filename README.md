# 科学任务生成流水线

将 **原始资料包 → Data Designer 批量处理 → 出题、构建、审核与有界修订 → Harbor 任务包** 串成可检查的流程。

## 当前完成到哪里

已经跑通真实 Data Designer 的 **mock 管线**：一条资料包记录展开为两个任务，模拟三角色交接，每个任务退回作者修订一次，再归档结果。模型用量为零。

- Data Designer 固定 `0.9.2`，Harbor 固定 `0.23.0`，统一使用 Conda Python 3.12。
- 输入是 `PACKAGE.md + 自由形式资料`；种子表每行只填 `package_uri`。
- 任务数量、并发、修订次数来自运行配置；每次运行保存资料快照、候选版本、报告与汇总。
- mock 模式使用确定性 Python 角色，生成明确标注的加法测试包；harbor 模式运行真实 Codex 三角色。科学资料样例选用 Pywaterflood 的论文、代码与数据，mock 不从中推导科学任务。
- mock 结果为 `mock_completed`、`validated=false`。真实 API 已完成 1 个科学任务的生成、自测与独立审核，结果为 `accepted`。详见[真实运行记录](docs/design/18-live-acceptance.md)。

详细步骤、配置说明、目录结构与 Mermaid 流程图见 [可运行管线说明](docs/design/16-mock-pipeline.md)。

上游“用户需求 → 搜索整理 → source 包”已有独立 `sci-source` 入口，运行方法见 [搜索整理运行指南](docs/design/24-source-pipeline-usage.md)。设计边界见 [搜索整理管线开发方案](docs/design/23-source-discovery-pipeline.md)，包括两阶段 Data Designer 接入、同一需求内完全重复记录合并、断点恢复、输入输出与验收标准；新批次允许再次使用相同资料。

真实调用的标准构建、doctor 检查、网络与资源配置见 [真实运行指南](docs/design/17-live-pipeline.md)。

## 快速开始

```bash
conda env create -f environment.yml
conda activate sci-skt-pipeline
export UV_PROJECT_ENVIRONMENT="$CONDA_PREFIX"
uv sync --locked --inexact
sci-pipeline --config examples/pipeline/mock.json
```

当前机器已另建项目内环境，避免改动已有 Conda 环境，可直接执行：

```bash
runs/conda/sci-skt-pipeline/bin/sci-pipeline --config examples/pipeline/mock.json
```

结果写入新的 `runs/pipeline/<run_id>/`：

- `summary.json`：批次计数。
- `results.jsonl`：每个任务状态、候选哈希和任务包地址。
- `tasks/<task_id>/`：历次作者交付、构建和审核报告，以及修订反馈。

默认输入：[seeds.jsonl](examples/pipeline/seeds.jsonl)，指向 [Pywaterflood 原始包](examples/input-packages/pywaterflood/PACKAGE.md)。原始包地址目前只支持本地目录；远程资料链接放在 PACKAGE.md 中。

## 配置边界

| 文件 | 职责 |
|---|---|
| [.env.example](.env.example) → 本地 `.env` | API key、模型名、可选 API Base URL；mock 不需要也不读取 |
| [mock.json](examples/pipeline/mock.json) | 每包任务数、并发数、修订上限和模拟退回开关 |
| [harbor.json](examples/pipeline/harbor.json) | 真实角色运行参数，包括镜像、builder、资源、超时、交付重试与修订上限 |
| [pyproject.toml](pyproject.toml) | 直接 Python 依赖、命令入口、构建及代码格式设置 |
| [uv.lock](uv.lock) | Python 依赖精确版本与哈希 |
| [environment.yml](environment.yml) | Conda 解释器及安装工具基线，不是精确 Conda 构建锁 |

后续配置 API 时可以运行 `sci-pipeline --check-api-config` 检查必填项。这个检查不发起请求，不验证密钥有效性。真实密钥不要放入源码、输入表或运行 JSON。

添加包时在激活的环境中使用：

```bash
export UV_PROJECT_ENVIRONMENT="$CONDA_PREFIX"
uv add --no-sync "包名==版本"
uv sync --locked --inexact
```

Conda 管解释器，uv 管应用依赖。`--inexact` 保留 Conda 安装工具。不要不带环境设置直接执行 `uv sync`，以免改动遗留 `.venv`。`requirements.lock.txt` 是早期 Python 3.13 试运行的历史记录，不再作为安装入口。

## 三个角色

| 角色 | 职责 |
|---|---|
| [出题者](skills/scientific-task-author/SKILL.md) | 根据资料编写完整任务包，包括 Dockerfile、参考解和测试；独自负责所有任务文件修订 |
| [构建者](skills/scientific-task-builder/SKILL.md) | 构建和运行验证，只提交证据与问题，不修改任务文件 |
| [Reviewer](skills/scientific-task-reviewer/SKILL.md) | 对照来源、题意与执行证据审核；有问题退回作者 |

这些 skill 是真实角色的指令源，mock 不调用模型，也不执行 skill。真实 harness 使用 Harbor 内置 Codex 适配器，各角色独立容器与上下文。Codex CLI 不属于 Python 包依赖，角色镜像固定 `0.154.0`。

运行配置支持自由文本 `difficulty_guidance`，用于引导出题挑战；留空不指定额外难度偏好。真实示例配置已填入第一版 TB-Science v0.1 引导，依据全部 70 题分析，见[难度设计与全量调研](docs/design/19-difficulty-guidance.md)。可以直接替换该字段，不需要修改 skill 或原始输入包。

不设主观难度配额。参考解、空提交和错误提交的程序化自测已接入；正式 Solver 试做、Gym rollout 和难度校准后置。难度引导不会把未经试做的任务标为已校准。

## 开发与验证

```bash
python -m unittest discover -s tests -v
sci-pipeline --config examples/pipeline/mock.json
```

核心代码在 [src/sci_pipeline](src/sci_pipeline)。入口、配置、Data Designer 接入、状态机、文件管理和 mock 后端分开。每个角色通过小型接口交接文件，不再封装一套通用 Agent 平台。

早期 `workflows/arithmetic.py` 和 `workflows/task_author.py` 保留供参考，不是当前三角色管线入口。

更多背景：[输入包规范](docs/design/15-input-package-contract.md)、[开发方案](docs/design/14-deepseek-data-pipeline-implementation.md)、[Harbor 接入说明](runtimes/harbor/README.md)。

### 批量续跑与失败重跑

```bash
sci-pipeline --resume /绝对路径/运行目录
sci-pipeline --retry-failed /绝对路径/运行目录
```

续跑复用已有结果和已完成角色的检查点；失败重跑只重新执行未通过任务，并归档旧产物。无效原始包记录到 `input-errors.json`，其他输入继续处理。批次并发仍由 `max_concurrency` 控制（1～16）。详见 [批量恢复说明](docs/design/20-batch-recovery.md)。

### 可选：从任务提炼 Skill

运行配置中设置 `"generate_skills": true`，即可在任务验收通过后额外调用 Skill 提炼者和独立 Skill 审核者。默认关闭；Skill 单独保存，不挂载给 Solver，失败不影响任务验收结果。

`--resume <运行目录>` 可继续中断的提炼；`--retry-skills <运行目录>` 只重跑失败或被拒绝的 Skill。详见 [任务 Skill 提炼](docs/design/21-task-skill-extraction.md)。

### 执行取消与孤儿清理

```bash
sci-pipeline --cancel /绝对路径/运行目录
sci-pipeline --cleanup /绝对路径/运行目录
```

取消命令提交停止请求；worker 统一执行停止、容器清理和残留复查。恢复前自动检查未结束执行，清理无法确认时不启动新的 worker。配置 `worker_stop_grace_sec` 控制强制终止前的等待时间（默认 30 秒）。详见 [执行生命周期](docs/design/22-execution-lifecycle.md)。
