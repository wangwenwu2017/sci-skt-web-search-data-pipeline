# Data Designer 处理器教学图（修正版）

生成方式：内置 image_gen。日期：2026-09-15。

本图按用户意图将 Codex 作为运行时处理器 f，与静态 Python 函数对照；替代上一张把 Codex 描述为配置编写助手的教学图。

## 最终提示词

Create a new beautiful simplified Chinese educational infographic poster in Chiikawa cute hand-drawn style, portrait high resolution, cream background, pastel sky blue/mint/peach, small white round creature, blue-eared cat and yellow rabbit guiding a classroom, crisp large Chinese typography, lots of whitespace, clean mathematically accurate arrows. Critical conceptual correction: Codex is a RUNTIME PROCESSOR f, never an assistant for writing configuration. Do not depict or say Codex writes workflow.py or helps configure Data Designer. Person configures the pipeline. Codex executes inside a custom processing step called by Data Designer. Two cases are visually analogous and equally emphasized.

Title exact: “Data Designer：输入 → 处理 → 输出”
Subtitle: “处理方式可以是 Python 函数，也可以是 Codex”
Top small equation with three distinctly colored boxes: “原始数据 x” → “处理方式 f” → “结果 y”
under it “Data Designer 按配置组织批量执行；具体怎么处理，由 f 决定。”

Section one spanning width title “人先配置这 4 件事”
Four simple cards: “① 输入是什么” “② 用哪个处理器” “③ 传什么参数” “④ 输出什么”
small line “准备种子数据，选择处理组件，设置参数与输出要求。”

Middle top case A blue rounded large panel title “案例 1：静态代码就是 f”
Horizontal three clear cards:
left input table title “输入 seeds.csv” with columns a,b and rows 2,3 ; 7,4 ; 10,5.
middle processor title “f：Python 加法函数” code exactly “def f(a, b):” newline “    return a + b”
right output table title “输出结果” columns a,b,c rows 2,3,5 ; 7,4,11 ; 10,5,15.
Arrows from left to middle to right.
Under chain rounded controller band “Data Designer：读取每行 → 调用 f(a,b) → 收集 c”
small badge “无需模型 API”
small example equation “f(2,3) = 5”
Four brief human steps at bottom of case: “准备 CSV → 选择加法函数 → 运行 → 检查结果”

Middle lower case B mint rounded large panel title “案例 2：Codex 就是 f”
Left input folder card “输入材料 x” labels “论文内容” “数据文件” “原代码库”.
Center big processor card “f：Codex 运行时处理器”, inside show “读取材料 → 调用工具 → 编写任务”, beneath “Skill / 指令：如何造题”.
Right output folder card “输出 tasks” labels “题目” “输入资产” “环境配置” “参考解与测试”.
Clear arrows source → Codex → tasks. Make processor visibly central, not off to side.
Above processor a small attached configuration plug card “模型 API 配置” with “服务地址 / 模型名 / 密钥环境变量” and arrow into Codex, NOT into generic output. Do not show actual secret.
Below processor small adapter card “自定义适配器” text “启动 Codex、准备工作区、收集任务包与日志”
Below whole chain controller band “Data Designer：读取种子记录 → 经适配器调用 Codex → 收集任务包路径与状态”
small note “Skill 是处理指令；Codex 是真正执行这些指令的工具。”
Small concrete example beneath: “污水处理论文 + 监测数据 + 分析代码 → Codex → 一个水质分析 coding task”
Four human steps: “准备材料 → 选择 Codex 处理器 → 设置 Skill 与 API → 运行并检查”

Bottom final summary big ribbon “Python 是一种 f，Codex 也是一种 f。”
Second line “人配置流程，Data Designer 组织执行，处理器生成结果。”
Small boundary footnote in restrained rounded box “Codex 需通过自定义适配器接入。生成任务包后，还需实际验证，再交给 Gym / Harbor rollout。”
This is a conceptual architecture teaching poster, not a claimed official built-in Codex integration or actual SDK screenshot. No autonomous agent branch, no configuration-writing Codex. All arithmetic and spelling correct. Keep output task packages clearly candidates until validation. Add tiny badge on tasks box “候选，待验证”. Draw adorable mascot handling input cards and inspecting output, but no extra speech bubble claims. Polished shareable teaching figure.
