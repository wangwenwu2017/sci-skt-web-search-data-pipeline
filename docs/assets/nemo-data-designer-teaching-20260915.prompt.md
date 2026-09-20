# NeMo Data Designer 教学图生成记录

生成方式：内置 image_gen；日期：2026-09-15。

图片：`nemo-data-designer-teaching-20260915.png`。

## 最终生成提示词

Use case: scientific-educational.
Create one polished Chinese educational infographic for colleagues explaining NeMo Data Designer and how to use it for our scientific coding task generation pipeline. Portrait poster, high resolution, generous whitespace and very legible simplified Chinese. Chiikawa / 吉伊卡哇 style: tiny round cute white creature, blue-eared cat and yellow rabbit as friendly classroom guides, soft cream paper background, pale pink mint and sky blue rounded cards, thin warm brown hand-drawn lines, small blush cheeks, playful but professionally clear information hierarchy. Illustrations support learning; no crowded decoration. Title large: “NeMo Data Designer 是怎么工作的？”
Subtitle: “把来源与生成逻辑配好，批量产出任务候选”
Organize in 5 clearly numbered sections with thick directional arrows, top to bottom. Use exact concise Chinese text below. Treat all source fields and workflow as our project example, not built-in schema.
1 “准备两样东西” show two adjacent cards:
left “种子数据：根据什么生成？” with icons and labels “论文内容 / 数据源 / 代码库” and “任务要求与约束”.
right “生成配置：具体怎么做？” labels “采样规则 / Prompt / 字段依赖” and “自定义函数 / Agent + Skill”.
small role tag “人先填写，后续可由 Agent 整理”.
2 “Data Designer 按配置组织生成” show a mini left-to-right dependency chain:
“选择输入与参数” → “生成任务定义” → “生成题目与代码” → “检查输出”.
caption “每一步读取前面需要的字段，再产生新的字段”.
3 “需要工具操作？接入 Agent” draw a visibly separate plug-in box linked from step 2, not claim built-in agent support:
“自定义适配器 → Agent + Skill”
below “读论文 · 看代码 · 运行工具 · 编写任务包”.
small boundary note “适配器负责工作区、工具权限、超时与产物保存”.
4 “批量输出：一行一个任务候选” show clean small table only 3 columns header “任务 ID | 任务包路径 | 验证状态”; rows “task-001 | tasks/001 | 待验证” and “task-002 | tasks/002 | 待验证”.
caption “大文件存目录，表里保存路径与记录”.
5 “实际验证后，再去 rollout” show chain
“任务打包” → “环境＋参考解＋评分器验证” → “Gym + Harbor” → “轨迹与评分”.
Important clearly readable bottom note in highlighted ribbon “生成成功 ≠ 任务可跑；Data Designer 不负责 Solver 的逐轮工具循环”.
Final small takeaway box “第一次怎么用：人工准备少量种子 → 写一套配置 → 生成 3 个候选 → 验证跑通 → 再扩大批量”.
Small example badge near input: “例：从污水处理资料生成 Python 数据分析任务”.
No extra invented claims, no promises every task succeeds, no official endorsement or logos, no code walls. Keep Chinese accurate, no repeated paragraphs. Emphasize input+workflow freedom and custom agent integration boundaries. Make overall diagram self-contained and easy to share.
