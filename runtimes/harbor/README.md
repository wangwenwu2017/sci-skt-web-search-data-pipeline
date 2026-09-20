# Harbor 接入配置

主项目使用 Data Designer 组织任务生产，Harbor 0.23.0 提供执行能力。两者统一由根目录 pyproject.toml 和 uv.lock 管理，共用 Conda 环境。本目录保存配置说明和角色基础镜像 Dockerfile，不是独立 Python 项目。主管线通过隔离子进程调用 Harbor Python Job 接口。完整操作见[真实运行指南](../../docs/design/17-live-pipeline.md)。

Harbor 的现成 Codex 适配器作为第一个 harness 接入方式。不额外安装名为 codex 的 Python 包，也不要求 ACP 或 acpx。Codex CLI 是在角色运行环境内使用的外部程序，由 Harbor 适配器检查、安装指定版本。

## 安装

在项目根目录执行：

```bash
conda env create -f environment.yml
conda activate sci-skt-pipeline
export UV_PROJECT_ENVIRONMENT="$CONDA_PREFIX"
uv sync --locked --inexact
harbor --help
```

Conda 管解释器与安装工具，uv 管应用依赖。`--inexact` 保留 Conda 安装的额外工具。确认 UV_PROJECT_ENVIRONMENT 指向已激活的 sci-skt-pipeline 环境。

## Codex 配置

`codex-agent.fragment.json` 是 Harbor AgentConfig 的基础配置片段，固定 CLI 为 0.154.0（当前宿主机已安装的版本，用作首次兼容验证候选）。它不是完整 Job，不能直接作为运行配置提交。

提交端还需明确设置 `model_name`、凭据引用、角色任务路径、资源预算、输出目录等。三个角色分别运行，不能将三个 Agent 简单塞进同一个 Job 就当成顺序交接。

角色生产作业设置 `verifier.disable = true` 并收集产物。生成后的科学任务单独提交 Oracle 自测作业，启用 Verifier，检查环境、参考解和测试；正式 Solver 与难度校准后置。

本地登录并不保证角色容器自动获得认证。认证/API 地址需在实际接入时显式配置，不复制整个宿主机用户配置，不将密钥写入版本库。

## 状态与限制

已安装项目 Conda 环境、构建角色基础镜像，并实际通过 Codex 0.154.0 调用用户配置的 API。完整生成、自测与审核链路已通过一个 pywaterflood 科学任务；详见[运行记录](../../docs/design/18-live-acceptance.md)。

先以 Docker 后端做最小验收：运行一个角色、生成文件、完整收回、确认生产 Verifier 未执行。OpenSandbox 后端及内部集群适配另行验证，不能把官方版本与历史内部 fork 视为等价。

当前环境统一安装 Data Designer 和 Harbor，不加入 Heta Framework，也不为其预先拆分环境。

参考：[固定版本依赖](https://github.com/harbor-framework/harbor/blob/v0.23.0/pyproject.toml)、[Codex 适配器](https://github.com/harbor-framework/harbor/blob/v0.23.0/src/harbor/agents/installed/codex.py)、[版本参数](https://github.com/harbor-framework/harbor/blob/v0.23.0/src/harbor/agents/options.py)。
