# 人工操作 NeMo Data Designer 教学图

生成方式：内置 image_gen。日期：2026-09-15。

## 最终提示词

Create one beautiful simplified Chinese educational poster, portrait high resolution, matching previous Chiikawa-style soft hand-drawn classroom infographic: tiny white round creature, blue cat, yellow bunny as human learner mascots, creamy white background, pastel mint blue peach, thin brown outlines, exceptionally clear Chinese typography, generous whitespace, restrained decoration. Two equally clear case-study lanes stacked vertically. NO autonomous Agent explanation. Codex is only a human-operated coding assistant that writes configuration, not a runtime component. Explain human steps and distinguish model API case from deterministic static case. Exact title “人怎么用 NeMo Data Designer？”
Subtitle “先准备种子，再写生成配置，最后运行并检查”
Small definition ribbon “种子 = 已有数据 ｜ 配置 = 处理步骤 ｜ 模型 API = 可选能力”
TOP CASE mint/blue card title “案例 1：种子 + Codex 写配置 + 模型 API → 任务题目”
Six clearly numbered human-action panels arranged 2 rows of 3 with unambiguous arrows:
1 “准备种子文件” show small seeds.csv table:
“topic | level”
“列表求和 | 入门”
“字符串反转 | 入门”
2 “让 Codex 帮忙写配置” show speech bubble “读取每条种子，生成一道 Python 编程题。” and file icon “workflow.py”
3 “配置模型连接” show labeled tags “服务地址 / 模型名 / API Key” and note “密钥放环境变量”
4 “检查生成规则” show schema fields “instruction：题目” “examples：输入输出示例” “output_format：输出要求” and short prompt “根据 topic 和 level 生成题目”
5 “运行 Data Designer” show simple flow “读取种子 → 调模型 API → 校验结构” and badge “先预览 2 条”
6 “查看并保存结果” show concrete output card:
“题目：实现 sum_list(nums)”
“输入：[2, 3, 4]”
“输出：9”
caption “得到结构化任务记录”
Below case1 a very clear small boundary box “这里生成的是题目数据；可执行任务包还需环境、测试和打包。”
MIDDLE separate simple architecture arrow with label “Codex 写完配置后，实际批量生成由 Data Designer 执行。”
BOTTOM CASE peach/yellow card title “案例 2：纯静态规则 a + b → c”
subtitle “不调用模型 API，也不需要 API Key”
Four horizontal or 2x2 numbered panels:
1 “准备 seeds.csv” show a real 2-column table headers a,b and rows 2,3 ; 7,4 ; 10,5.
2 “写表达式配置” show exact readable text “c = a + b” and underneath “表达式列：{{ a + b }}”
3 “运行 Data Designer” caption “逐行读取 a、b，计算 c”
4 “检查输出表” show actual 3-column table a,b,c rows 2,3,5 ; 7,4,11 ; 10,5,15. All arithmetic exact.
Below small note “简单相加用 Python 也能完成；放进 Data Designer，可与后续生成步骤统一编排。”
BOTTOM summary with three tiny labeled cards:
“人：准备与检查”
“Codex：辅助写配置，可选”
“Data Designer：按配置批量执行”
Small footnote “示意流程，具体配置接口以安装版本为准。”
Do not invent a full SDK code sample, CLI command, API placeholder secrets or official UI. Files and tables should be real illustrative content. Do not imply Codex API required in case2. Avoid dense text, avoid repeated paragraphs. Educational clarity highest priority. Use cute characters holding CSV cards, pointing at arrows, inspecting results; no robot autonomous workers. Render exact Chinese and math crisply.
