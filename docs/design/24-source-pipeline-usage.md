# 搜索整理管线：运行与恢复

本管线将自然语言需求转成原始资料包。它复用 Data Designer、Harbor/Codex 和现有生命周期管理，输出能直接传入任务生成管线的 seeds.jsonl。

## 1. 环境与命令

激活项目 Conda 环境后安装项目入口：

```bash
conda activate sci-skt-pipeline
export UV_PROJECT_ENVIRONMENT="$CONDA_PREFIX"
uv sync --locked --inexact
```

本机已有环境也可以直接使用 `runs/conda/sci-skt-pipeline/bin/sci-source`。Tavily 工具使用 Python 标准库调用官方 Search/Extract API，不新增 SDK 依赖，角色镜像已包含 python3。

## 2. 输入

JSONL 每行一个需求：

```json
{"request_id":"paper-001","mode":"domain","request":"寻找地下水污染模拟研究，优先包含论文、代码和数据。","entrypoints":[],"max_candidates":5}
```

- request_id：本批唯一，字母或数字开头，只使用字母、数字、下划线、短横线，最长 64 字符。
- mode：bench 或 domain；两种模式共用一个角色。
- request：自然语言需求。
- entrypoints：可选 HTTP(S) 起点链接。
- max_candidates：默认 10，允许 1～100；是上限，不要求凑够。

每个候选包括范围、来源 URL 和版本、相关性、关联依据与缺失信息。范围相同、来源 URL/版本集合完全相同的记录，只在当前需求内部合并；保留原始候选证据。不同需求、不同批次不合并。

## 3. Mock 验证

```bash
sci-source --config examples/source/mock.json --requests examples/source/requests.jsonl
```

mock 仍使用真实 Data Designer 两阶段调度，但角色是确定性 Python 实现。每个样例需求返回 A/B/A，合并后整理两个包；两个需求共四个包。example.org 是测试材料，不能当作真实科学资料。mock 不加载 .env，不启动 Docker，不调用 API。

## 4. 真实搜索整理

本地 `.env`：

```dotenv
OPENAI_API_KEY=填写模型服务密钥
SCI_PIPELINE_MODEL=填写模型名
OPENAI_BASE_URL=填写可选模型接口地址
TAVILY_API_KEY=填写Tavily密钥
```

模型和 Tavily 密钥只传给搜索整理角色。保存的 Harbor 作业配置使用环境变量引用，不包含明文密钥；执行日志和回收产物使用注入密钥进行脱敏。容器联网代理沿用 SCI_PIPELINE_CONTAINER_PROXY 和 SCI_PIPELINE_CONTAINER_NO_PROXY。

```bash
# 只检查配置，不调用接口
sci-source --check-api-config

# 检查 Docker、Compose、builder、角色镜像和 Codex 版本，不调用付费模型
sci-source --doctor --config examples/source/harbor.json

# 一个真实资料包的小样本
sci-source --config examples/source/harbor.json --requests examples/source/smoke.jsonl
```

角色镜像沿用现有 sci-pipeline 构建方式。配置中的 execution 使用现有 RunConfig，包括镜像、并发、超时、CPU/内存、交付重试参数；任务生成字段在搜索管线中不起作用。source 层另外提供 search_timeout_sec、search_provider 和 policy_version。

默认并发 1，mock 示例并发 2，允许上限 16。发现和整理阶段顺序运行，各阶段内部按行并发。Tavily 工具每次调用只有一次有时限的 HTTP 请求，不内置额外重试；角色格式交付重试受 max_role_attempts 约束。一次 tool call 失败会保存事件，搜索服务全面失败不能冒充 no_results。

## 5. 输出与下游

命令打印运行目录；主要文件：

| 文件 | 内容 |
|---|---|
| requests.jsonl | 从本批原始输入恢复的有效需求 |
| discovery-results.jsonl | 每个需求的搜索状态 |
| package-plan.jsonl | 展开并合并后的整理计划 |
| items/<item_id>/delivery/package/ | PACKAGE.md 和可选材料，即 source 包 |
| results.jsonl | 每个整理项的状态、需求/候选标识、包地址 |
| seeds.jsonl | 所有成功包地址；每次从当前结果重建，不重复追加 |
| summary.json | 状态、输入错误数、包数、无结果需求数 |
| timing.json | 本次及累计运行耗时、各角色累计执行秒数 |
| usage.json | Harbor 模型用量、Tavily 调用事件和已报告 credits |

示例：

```bash
sci-pipeline --config examples/pipeline/mock.json --seeds /绝对路径/source运行目录/seeds.jsonl
```

真实出题使用 examples/pipeline/harbor.json，会进一步产生模型与环境运行费用。两条管线入口独立；当前没有自动串联开关。需要先检查搜索 summary 和包内容，再选择下游配置。

包存在运行目录内，清理该目录会一起删除包。长期交付时复制完整 package 目录，并更新种子地址；下游现有准备步骤会为自己的运行复制输入快照。

## 6. 恢复和失败重跑

```bash
sci-source --resume /绝对路径/source运行目录
sci-source --retry-failed /绝对路径/source运行目录
sci-source --cancel /绝对路径/source运行目录
sci-source --cleanup /绝对路径/source运行目录
```

- resume：复用完整的已完成结果，继续尚未完成的项。CLI 对原配置和 Skill 做指纹检查；要改变它们或更新搜索结果，应创建新批次。
- retry-failed：只归档和重跑失败的搜索或整理项。失败搜索恢复后产生的候选追加到整理计划，不改变成功包；批次尚有未完成项时先 resume。
- cancel：写入停止请求，命令返回不等于 worker 已退出。运行过程收到 SIGINT/SIGTERM 也会请求停止。
- cleanup：原运行已退出时，主动清理有归属记录的孤儿执行。与已有任务管线一样，只支持当前同机 Docker 恢复范围。

框架检查点加业务结果共同支持恢复：重新派发已经完成的行，会检查产物而不调用 Agent。交付目录已经发布但 result.json 未落盘时，可以校验后补写结果。如果 API 已调用、结果还未保存便崩溃，则可能重试，不能承诺付费调用恰好一次。

输入错误按行隔离；不可写磁盘等无法保存状态的问题中止批次。成功批次退出 0，有错误或部分完成退出 1，协作取消退出 130。no_results 表示搜索完成但没有相关候选，可能得到空 seeds；下游不会自动凑包。

## 7. 验证边界

单元与集成测试覆盖需求内精确合并、跨需求保留、两阶段真实 DD mock、续跑跳过已完成角色、失败项重跑、发布窗口恢复、坏包检查、取消拒绝新调用、凭据引用与脱敏、下游种子兼容。

结构检查只核对包格式、来源记录、普通 Markdown 本地链接和文件哈希，不证明科学内容正确。真实任务的环境和解答审核仍由下游负责。工具调用事件由角色容器写出，用于运行诊断，不作为不可篡改审计账本。

跨批次去重、相似任务分析、轨迹采集、全局 API 限速、费用硬上限和多机调度不在本版范围内。真实联调记录另见本文件末尾验收记录。


## 8. 2026-09-18 验收记录

- 74 项测试通过；Ruff 检查和 source-curator Skill 格式检查通过。
- 真实输入：examples/source/smoke.jsonl，Pywaterflood 单需求、最多一个候选。
- 实际执行链：Data Designer → Harbor/Codex discover → Tavily → Data Designer → Harbor/Codex package → source 包。
- 运行目录：`runs/source/20260918T074616Z-581d60a0/`，最终 completed、1 个包、0 个输入错误。
- 首次管线执行耗时 668.79 秒，约 11 分 9 秒；发现 433.70 秒，整理 234.97 秒。该计时从 CLI 准备/环境检查结束后开始，不含人工等待。
- Tavily 工具记录 7 次调用，全部成功，累计已报告 5 credits。模型输入 669,573 tokens（其中缓存 615,936），输出 23,694 tokens；接口没有报告美元费用，未按猜测价格估算账单。
- 真实续跑仍为 1 个包、2 次角色执行，模型和工具调用量没有增加。
- 同一 seeds.jsonl 已接入现有 mock 任务管线，生成两个 mock_completed 测试任务，运行目录 `runs/pipeline/20260918T075905Z-94216fbf/`；这验证文件交接，不是科学任务质量验收。
- 两个真实角色的生命周期登记均为 finished/completed；运行文件扫描没有发现注入密钥明文。
- 真实包包含论文、官方代码、论文归档版本、示例数据和文档的来源说明，采用链接形式。源包结构检查通过；summary.validated=false 表示没有在本阶段验证科学任务。

实际包：`runs/source/20260918T074616Z-581d60a0/items/pywaterflood-source-c000/delivery/package/PACKAGE.md`。

本次没有执行 benchmark 模式的真实质量验收，也没有对真实 Harbor 进行强制中断测试或从这个新包生成真实科学 task；相应能力不据此宣称完成实测。单个小样本的耗时和成功不能代表大批量吞吐。
