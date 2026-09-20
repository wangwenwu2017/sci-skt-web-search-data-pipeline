# TB-Science v0.1 全量题目分析与第一版难度引导

## 结论

第一版出题目标是：**从来源中提取需要领域判断的研究级计算工作，在清晰、可解、可验收的前提下保留实质性技术挑战。** 任务可以聚焦一个深入的难点，也可以是一条相互依赖的科学流程。不要把整篇论文复现、更多文件、更长题面或更大计算量当作难度的替代指标。

这是对任务设计特征的对齐，不是经实验确认的等难度。当前未运行这 70 题的 Solver，也未逐个审计隐藏测试或参考解；不能据此生成逐题成功率或宣称新任务已达到同等难度。

## 调研范围与版本

- 日期：2026-09-17。
- 固定版本：[v0.1.0](https://github.com/harbor-framework/terminal-bench-science/tree/v0.1.0)，commit `f81afac4f11048e77a15dfc8fb1dbfb897fea0ce`。
- 本地已有仓库：`/home/qinqinyuan/pjlab_project/tb_sci/terminal-bench-science`。工作树 HEAD 是另一提交，因此用 `git show v0.1.0:<path>` 读取固定版本；70 份题目正文与固定提交下载副本逐字节相同。没有修改该仓库。
- 通读全部 70 份 instruction.md，解析全部 70 份 task.toml，并补读部分 README 的难度、来源和验收解释。题目引用的附属 SPEC、数据、服务协议没有全部展开；下面的逐题表是任务要求层面的分析，不是解答或完整质量审计。
- [版本发布清单](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/release-notes-v0.1.0.md)、[固定版本审核规范](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/rubrics/task-proposal.md)、[发布时测评说明](https://www.terminal-bench-science.ai/announcement)。
- [核对清单](../research/tb-science-v0.1-inventory.json)记录每题路径、正文 SHA256、作者专家工时估计及资源声明，可追溯覆盖范围。调研正文保留在临时目录，未作为运行种子或角色输入。

## 全量统计

以下为固定版本文件直接统计，不是主观评分。

| 领域 | 题数 |
|---|---:|
| 地球科学 | 8 |
| 工程科学 | 9 |
| 生命科学 | 19 |
| 数学科学 | 17 |
| 物理科学 | 17 |
| 合计 | 70 |

- 70/70 题的 agent.timeout_sec 是 28,800 秒，即 8 小时。它是允许的解题预算，不是测得的平均用时，也不是作者生成一个任务的预算。
- 70/70 题声明 gpus=0；CPU 分别为 1 核 6 题、2 核 23 题、4 核 41 题。内存声明范围 2,048–16,384 MiB。这说明任务设计的挑战不能简单等同于大 GPU 训练。
- metadata.expert_time_estimate_hours 全部有值：最小 1.6 小时、中位数 12 小时、最大 600 小时。32/70 题估计不超过 8 小时，34/70 题不超过 10 小时。这些是不同作者的估计，标准未必一致；600 小时的 Onsager 形式化证明是明显离群值，不能把它当作每道生成任务的目标。
- 70 份 metadata 中均未发现统一的 difficulty 字段，不能直接读取一个官方简单/中等/困难分布。

官方审核规范强调专业研究工作和实质难点，其开头提出前沿模型 10–20% 成功率的目标；发布说明报告最高整体解决率为 30%，每模型每题三次试验。审核目标、总体测评结果、逐题难度是三个不同概念，不能把某个百分比直接写成作者 Agent 已保证的输出属性。

## 从 70 题归纳出的难点

以下是我们的设计归纳，不是官方难度分级；同一道题可以同时涉及多项。

| 难点 | 实际要求 | 典型任务 |
|---|---|---|
| 科学模型与数值实现 | 知道公式仍要处理离散化、稳定性、边界及计算误差 | AMR Poisson、球面重映射、波导反演 |
| 隐变量和机制辨识 | 多种原因可产生类似观测，需要区分而非只拟合表面曲线 | 含水层治理、非弹性本构、传感器校准 |
| 真实测量条件 | 噪声、伪影、观测空档、批次差异会改变科学结论 | EEG、MRI、压痕、冰川影像 |
| 泛化与实验设计 | 提交方法必须在未见数据或有限新测量下有效 | 导波定位、蛋白主动学习、光刻校准 |
| 多个科学要求同时成立 | 一个高分不能掩盖物理违规、错误校准或某类群体失败 | 反应器控制、RNA 校正、光栅设计 |
| 高质量解与效率/证书 | 找到可行解还不够，需达到可靠精度、低成本或提供证明 | 稀疏回归证书、黑盒优化、局部线性求解 |
| 数学推理到形式化 | 现成结论仍需补足引理、定义与内核可检查证明 | Stam、Turán、Onsager、正则化博弈 |

这些类别不会成为作者必须凑齐的清单。一个难点已经足够深入时，不额外堆叠无关要求。

### 对“放在一篇论文里”的判断

合适的类比是“独立完成一个关键实验、方法模块或研究级数据分析交付”。有些题覆盖完整科学链，有些只交付一个函数、构象或证明。没有充分理由把全部题排列为“公式复现 < 核心算法 < 完整论文 < 新科学发现”。论文覆盖面是范围，解决问题所需的判断和方法深度才是挑战来源。

当前 pywaterflood 成功样例主要是给定公式与参数的前向计算，设计上更直接。要提高挑战，可在来源支持时考察参数识别、预测泛化、物理约束或数值稳定性；不自动认为这些词一出现就达到 TB-Science 水平。

### 不机械继承的特征

- 8 小时是 benchmark 的 Solver 预算。本项目仍受运行配置的角色预算、单次自测预算和 CPU/内存限制约束。
- 个别题面存在隐藏数值门槛、大量格式/流程要求或不直接服务科学目标的附加工作；它们出现在数据集中，不等于应该成为我们的出题规范。
- 部分任务依赖测定服务、图操作服务或交互客户端；当前单容器 CPU 管线不能通过 prompt 自动获得这些能力。
- 例如 QSM 题面列出多项指标，但 README 明确解释部分钙化指标仅用于诊断。不能根据指标列表长度推断硬性通过条件数量。
- 不统一要求禁用成熟库、不统一要求完全从零实现。是否允许工具应由待测能力和科学目标决定。
- 高难任务也需要明确、可辨识的问题。数据不足、验证器错误和环境损坏造成的失败不是有价值的难度。

## 第一版配置与角色行为

新增运行配置字段 `difficulty_guidance`，类型为自由文本字符串：

```json
{
  "difficulty_guidance": "在资料与资源支持的前提下，设计需要领域判断的研究级反演任务，优先检验噪声鲁棒性与物理一致性。"
}
```

它与 `generation_guidance` 分开：前者描述希望考察的挑战，后者描述其他生成范围或业务要求。默认空字符串，旧配置继续可用；空值表示不指定额外难度偏好，不隐式选择 TB-Science。

[harbor.json](../../examples/pipeline/harbor.json)已填入第一版 TB-Science v0.1 引导全文，可以直接编辑该字段。generation_guidance 选择目标明确、资料依据充分、交付结果可验证的科学或工程任务；CPU、内存和时限由资源配置与后端能力约束。字段是运行级配置，同批任务共用；原始输入表仍只需要 package_uri，不新增逐行必填字段。不放入 .env。

调用链是 `RunConfig → Data Designer GeneratorParams → HarborBackend.author → 作者容器指令`。运行目录保存完整 run-config.json，包含本次实际引导；作者的生产作业 instruction.md 也保留实际注入文本。它不是 Harbor task.toml 的难度字段，不传给正式 Solver。

作者在 authoring/DESIGN.md 记录：目标、来源定位、实际核心难点、朴素方法可能失败的原因、验收映射，以及与目标的差距。差距本身不触发主观难度淘汰；构建和审核的正确性条件保持不变。没有 Solver 回流时 difficulty_calibrated 仍为 false。

### 引导全文的要点

1. 优先提取有来源的研究级核心问题，保留领域判断空间。
2. 选择适合来源的实质难点，不要求全流程或多难点叠加。
3. 解释为什么直接代入、默认拟合或通用整理不足；未经比较，不声称已测得基线失败。
4. 从公开目标建立精度、物理约束、一致性、泛化或效率验收，允许替代方法和等价解。
5. 遵守实际资源，材料不足时说明目标差距，不伪造挑战或随意收紧容差。
6. 只对齐设计特征，不宣称实测难度或成功率。

## 70 题逐项记录

每行说明任务交付与主要挑战，均基于固定版本题面；不是逐题通过率，也不意味着已确认每个验收器正确。点击任务名可查看原文。

### 地球科学

| # | 任务 | 交付 | 主要挑战 |
|---|---|---|---|
| 1 | [sparse-network-assimilation](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/atmospheric-sciences/sparse-network-assimilation/instruction.md) | 恢复混沌系统状态、空间驱动和时钟偏差 | 稀疏异步观测下联合反演；拟合、动力学一致性与预测须同时成立 |
| 2 | [hysteretic-aquifer-control](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/environmental-sciences/hysteretic-aquifer-control/instruction.md) | 学习交换闭合、校准含水层并设计治理控制 | 闭合学习、传感器偏差、PDE 反演与稳健控制相互耦合 |
| 3 | [duan-thesis](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/geosciences/duan-thesis/instruction.md) | 阅读学位论文、翻译 Fortran 模型并复现实验 | 跨 PDF、数据转录和语言迁移；也混有校对文字的额外负担，不作为新任务通用模板 |
| 4 | [hbv-calibration-1](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/geosciences/hbv-calibration-1/instruction.md) | 实现可复用的 15 参数水文校准器 | 多局部极值、优化策略及暖启动/测试协议；不能以一次默认拟合代替 |
| 5 | [mendota-ice-phenology](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/geosciences/mendota-ice-phenology/instruction.md) | 从多源影像恢复十个冬季的冻融日期 | 裸冰与水混淆、云与时间缺口、空间尺度及观测协议共同影响日期 |
| 6 | [stereo-dem-icesat2](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/geosciences/stereo-dem-icesat2/instruction.md) | 从双时相立体影像计算冰川质量平衡 | 立体匹配、测高校准、共配准与物理合理性共同约束结果 |
| 7 | [supraglacial-lake-classification](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/geosciences/supraglacial-lake-classification/instruction.md) | 给湖泊排水事件分类 | 从定性领域规则提取时空证据，区分稀有机制；不是普通有标签分类 |
| 8 | [masked-spherical-remap](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/earth-sciences/ocean-sciences/masked-spherical-remap/instruction.md) | 修复保守球面网格重映射算子 | 复杂球面几何、守恒约束、非线性平衡及一二阶导数一致性 |

### 工程科学

| # | 任务 | 交付 | 主要挑战 |
|---|---|---|---|
| 9 | [reactor-safety-control](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/chemical-engineering/reactor-safety-control/instruction.md) | 设计安全且快速的半批反应器控制器 | 部分观测、扰动和不确定性下兼顾温度硬约束与完成速度 |
| 10 | [rolling-shutter-oma](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/civil-engineering/rolling-shutter-oma/instruction.md) | 从视频识别模态、损伤和测量链参数 | 滚动快门、混叠和非结构振动会混淆物理模态，需联合辨别 |
| 11 | [microarch-modeling](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/electrical-engineering/microarch-modeling/instruction.md) | 构建可部署的 CPU IPC 代理模型 | 极少标签下推断新策略/新硬件组合，兼顾预测、排序和设计选择 |
| 12 | [navigation-sensor-calibration](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/electrical-engineering/navigation-sensor-calibration/instruction.md) | 校准 GNSS/IMU/LiDAR 并重建轨迹 | 时空参数耦合、异常剔除、噪声与长观测空档中的位姿估计 |
| 13 | [baseline-free-localization](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/mechanical-engineering/baseline-free-localization/instruction.md) | 无健康基线地定位板件损伤 | 缺少标注和标定传播模型，需从波形与几何提取跨场景证据 |
| 14 | [guided-wave-localization](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/mechanical-engineering/guided-wave-localization/instruction.md) | 利用健康参考定位不同板件上的损伤 | 跨传感器布局与运行条件迁移，不能按波形列直接相减 |
| 15 | [inelastic-constitutive-discovery](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/mechanical-engineering/inelastic-constitutive-discovery/instruction.md) | 识别非弹性机制并预测新加载历史 | 多机制区分、历史依赖和热力学一致性同时约束预测 |
| 16 | [tamp-skill-planning](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/mechanical-engineering/tamp-skill-planning/instruction.md) | 实现操作技能并为机器人规划动作 | 几何、技能代码和物理执行耦合，探测次数受限；服务架构不在当前管线范围 |
| 17 | [virtual-baseline-localization](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/engineering-sciences/mechanical-engineering/virtual-baseline-localization/instruction.md) | 借助仿真基线定位实验裂纹 | 仿真到实测及不同几何间迁移，波形不能直接比较 |

### 生命科学

| # | 任务 | 交付 | 主要挑战 |
|---|---|---|---|
| 18 | [ambient-rna-correction](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/ambient-rna-correction/instruction.md) | 校正环境 RNA 并保留生物学状态 | 污染与批次/谱系差异混淆；不能以去除稀有状态换取整体指标 |
| 19 | [betalactam-multimodal-transfer](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/betalactam-multimodal-transfer/instruction.md) | 预测未见药物耐药性并筛选决定基因 | 跨药物迁移，区分耐药决定因素与共现/许可背景 |
| 20 | [cell-lineage-reconstruction](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/cell-lineage-reconstruction/instruction.md) | 从视频重建细胞分裂与谱系 | 长时追踪、事件时点、母女关系与世代统计相互依赖 |
| 21 | [cilia-segmentation](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/cilia-segmentation/instruction.md) | 分割细胞与纤毛并区分基部和尖端 | 多通道成像证据、细长结构与生物学端点判别 |
| 22 | [diag-chipseq](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/diag-chipseq/instruction.md) | 校正 ChIP-seq 外参并恢复差异信号 | 辨别受损参照，保留全局生物学变化，兼顾配对设计与多重检验 |
| 23 | [genomic-model-ranking](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/genomic-model-ranking/instruction.md) | 评估基因组模型的迁移性并校准预测 | 同源/位点依赖、细胞背景偏移和排名不确定性；随机拆分可能误导 |
| 24 | [ont-tn-qc](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/ont-tn-qc/instruction.md) | 从肿瘤-正常测序数据产生 QC 发现 | 区分错配、污染、组成、拷贝数与信号问题，并给分子证据 |
| 25 | [protein-active-learning](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/biology/protein-active-learning/instruction.md) | 三轮实验选择后提交蛋白活性排序模型 | 受限测量预算、不同测定尺度和多突变泛化；需要交互测定服务 |
| 26 | [animal-reid](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/ecology/animal-reid/instruction.md) | 跨图像识别动物个体并发现新个体 | 开放集身份聚类，兼顾个体匹配与种群数量误差 |
| 27 | [ankle-mri-findings](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/medicine/ankle-mri-findings/instruction.md) | 从 MRI 提交有影像依据的结构化发现 | 专业影像判断、测量和多序列证据；不是论文公式实现型任务 |
| 28 | [clinical-metadata-recovery](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/medicine/clinical-metadata-recovery/instruction.md) | 从表达谱恢复缺失临床标注 | 多平台、多队列、部分标签与批次异质性下迁移 |
| 29 | [dapi-he-alignment](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/medicine/dapi-he-alignment/instruction.md) | 匹配两种染色图像中的同一细胞 | 跨模态、形变、部分重叠和一对一对应的精度/召回权衡 |
| 30 | [longitudinal-clinical-agent](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/medicine/longitudinal-clinical-agent/instruction.md) | 按阶段重建已发生的临床决策并做回顾审计 | 时间可见证据、本体、不可重复承诺与安全证据；依赖交互客户端 |
| 31 | [spatial-cell-annotation](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/medicine/spatial-cell-annotation/instruction.md) | 根据蛋白标记给细胞簇注释 | 跨成像平台的标记组合解释，标签粒度必须匹配证据 |
| 32 | [tumor-immune-interface](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/medicine/tumor-immune-interface/instruction.md) | 细胞注释后测量肿瘤免疫界面与组间差异 | 生物身份影响空间几何，再影响患者级统计；多个环节必须一致 |
| 33 | [eeg-erp-recovery](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/neuroscience/eeg-erp-recovery/instruction.md) | 恢复 P300 波形、特征与质量报告 | 真实触发时点、通道故障、极性及 epoch 处理不能相互混淆 |
| 34 | [foraging-cognitive-model](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/neuroscience/foraging-cognitive-model/instruction.md) | 建立紧凑的动物选择预测模型 | 非平稳行为、逐步因果预测和最多四维动态状态约束 |
| 35 | [mri-harmonization](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/neuroscience/mri-harmonization/instruction.md) | 去除 MRI 扫描仪效应并保留个体信号 | 重复测量、阶段混杂、未知扫描仪回退和稳健特征资格 |
| 36 | [qsm-reconstruction](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/life-sciences/neuroscience/qsm-reconstruction/instruction.md) | 从多回波 MRI 重建磁化率图 | 掩膜、背景场和病态反演耦合；README 说明部分伪影指标只作诊断 |

### 数学科学

| # | 任务 | 交付 | 主要挑战 |
|---|---|---|---|
| 37 | [amr-poisson-optimize](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/applied-mathematics/amr-poisson-optimize/instruction.md) | 补齐并加速自适应网格 Poisson 求解器 | 高系数反差、粗细网格通量守恒、真实残差和内存/速度共同约束 |
| 38 | [dna-storage-codec](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/applied-mathematics/dna-storage-codec/instruction.md) | 实现抗删除、抗乱序的 DNA 编解码 | 编码率、同步/纠错、随机信道可靠性与运行预算 |
| 39 | [koopman-mfg-id](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/applied-mathematics/koopman-mfg-id/instruction.md) | 识别平均场博弈并预测新条件下的均衡 | 参数与残差场分解、生成元、PDE 一致性与密度守恒 |
| 40 | [localized-sspd-solver](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/applied-mathematics/localized-sspd-solver/instruction.md) | 实现按局部行操作访问的稀疏线性求解器 | 看不到完整图，在受计费操作预算下达到残差要求；依赖服务 |
| 41 | [ode-law-discovery](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/applied-mathematics/ode-law-discovery/instruction.md) | 从噪声轨迹发现紧凑 ODE 并预测 | 表达式搜索、噪声处理、复杂度与离轨迹向量场泛化 |
| 42 | [traffic-flux-inversion](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/applied-mathematics/traffic-flux-inversion/instruction.md) | 从稀疏观测识别交通流及混合边界控制器 | 连续通量与离散切换机制联合识别，需跨网格和命令泛化 |
| 43 | [finite-free-stam](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/formal-mathematics/finite-free-stam/instruction.md) | 在 Lean 中证明有限自由 Stam 不等式 | 研究级定理、辅助引理与完整内核检查；给定结论不等于容易 |
| 44 | [gen-turan-paths](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/formal-mathematics/gen-turan-paths/instruction.md) | 在 Lean 中证明广义 Turán 计数结论 | 组合极值推理与形式化，允许给定背景定理但需补齐核心证明 |
| 45 | [onsager-ising-lean](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/formal-mathematics/onsager-ising-lean/instruction.md) | 形式化证明 Onsager 自由能定理 | 理论推导和证明基础设施很重；专家工时估计是明显高端离群值 |
| 46 | [certified-sparse-regression](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/operations-research/certified-sparse-regression/instruction.md) | 求稀疏回归解并提交全局最优性证书 | 不仅解要好，还需少节点覆盖与可验证下界 |
| 47 | [energy-routing](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/operations-research/energy-routing/instruction.md) | 求能耗车辆路径并连续细化速度 | 路线、时间窗、能量、充电和驾驶模式的混合优化 |
| 48 | [linked-cell-suppression](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/operations-research/linked-cell-suppression/instruction.md) | 生成满足隐私与成本约束的表格抑制方案 | 跨表线性泄露、多阶段不可逆公开与双侧保护约束 |
| 49 | [noisy-blackbox-optimization](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/operations-research/noisy-blackbox-optimization/instruction.md) | 实现受查询预算约束的抗噪优化器 | 不能委托现成优化器；需在多个函数上兼顾收敛速度与噪声鲁棒性 |
| 50 | [regularized-game-proof](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/operations-research/regularized-game-proof/instruction.md) | 在 Lean 中证明正则化博弈主结论 | 存在唯一性、变分刻画和收敛递推的完整证明链 |
| 51 | [highdim-mediation-debiasing](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/statistics/highdim-mediation-debiasing/instruction.md) | 修复跨研究的高维因果中介估计 | 分块迁移、偏差修正与标准误校准，正确点估计不足以通过 |
| 52 | [small-area-equivalence](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/statistics/small-area-equivalence/instruction.md) | 重建调查估计并输出联合预测分布 | 复杂抽样协方差、无样本区域预测与跨时间联合校准 |
| 53 | [symbolic-regression](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/mathematical-sciences/statistics/symbolic-regression/instruction.md) | 从高维少样本中恢复可泛化预测规则 | 稀疏高阶相互作用和未知函数形式；题目未公开具体分数门槛 |

### 物理科学

| # | 任务 | 交付 | 主要挑战 |
|---|---|---|---|
| 54 | [3x2pt-inference](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/astronomy/3x2pt-inference/instruction.md) | 完成宇宙学相关函数的贝叶斯推断 | 理论积分、尺度切割、快速预测和后验收敛共同控制参数偏差 |
| 55 | [cmb-cross-inference](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/astronomy/cmb-cross-inference/instruction.md) | 从偏振图到宇宙学后验并扩展受压模型 | 跨谱校正、似然、采样和物理模型失配诊断组成长科学链 |
| 56 | [neo-orbit-determination](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/astronomy/neo-orbit-determination/instruction.md) | 从混杂观测恢复小行星轨道状态 | 观测关联与轨道拟合联合求解，时空坐标和精度敏感 |
| 57 | [rv-astrometry-fitting](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/astronomy/rv-astrometry-fitting/instruction.md) | 联合径向速度与天体测量推断伴星后验 | 多仪器噪声、模型选择、几何约定和多参数后验匹配 |
| 58 | [tess-transit-vetting](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/astronomy/tess-transit-vetting/instruction.md) | 实现跨目标可复用的凌日筛查程序 | 去趋势、混叠、假阳性甄别与参数恢复须跨数据包成立 |
| 59 | [variable-star-vetting](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/astronomy/variable-star-vetting/instruction.md) | 对光变曲线分类并提取物理周期 | 不规则采样、谐波/混叠与恒星类型决定正确周期 |
| 60 | [geometric-pharmacophore-alignment](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/chemistry/geometric-pharmacophore-alignment/instruction.md) | 产生合理且满足作用位点的分子构象 | 无序特征匹配、大环构象、空间排斥和应变能共同优化 |
| 61 | [rdkit-ic-constraints](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/chemistry/rdkit-ic-constraints/instruction.md) | 实现分子几何约束扩展 | 距离、角度、带符号扭转与立体化学同时成立 |
| 62 | [nanoindentation-property-extraction](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/materials-science/nanoindentation-property-extraction/instruction.md) | 从压痕曲线恢复适用的材料属性 | 仪器/接触校准、漂移和不同本构效应混淆，简单拟合会偏置 |
| 63 | [si-fracture-fbc](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/materials-science/si-fracture-fbc/instruction.md) | 实现硅裂纹耦合模型并计算晶格俘获区间 | 原子-连续体耦合、校正导数、鬼力与分支稳定性联合验证 |
| 64 | [stacking-disorder-diffraction](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/materials-science/stacking-disorder-diffraction/instruction.md) | 从散射计数恢复堆垛无序时间轨迹 | 物理前向模型与反演、未见数据、精度和相对速度门槛 |
| 65 | [xrd-multiphase-qpa](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/materials-science/xrd-multiphase-qpa/instruction.md) | 从衍射和辅助测量定量分析物相 | 未知晶相、非晶、重叠峰与仪器/样品效应的联合区分 |
| 66 | [frustrated-heisenberg-nqs](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/physics/frustrated-heisenberg-nqs/instruction.md) | 优化固定神经量子态的变分能量 | 复杂符号结构、受限表示与非凸优化；不能只提交自报能量 |
| 67 | [inverse-lithography](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/physics/inverse-lithography/instruction.md) | 用两次校准测量设计可制造的光刻掩模 | 实验设计、隐过程辨识与二值逆设计，制造约束影响最终成像 |
| 68 | [inverse-waveguide-shape](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/physics/inverse-waveguide-shape/instruction.md) | 构建跨参数的波导折射率反演程序 | 稳定 Helmholtz 前向求解、约束优化、未见实例和速度 |
| 69 | [leaky-bloch-meep](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/physics/leaky-bloch-meep/instruction.md) | 设计并验证光栅耦合器 | 制造几何、方向性、相位和能量指标需在独立全波仿真中同时成立 |
| 70 | [spin-glass-groundstate](https://github.com/harbor-framework/terminal-bench-science/blob/v0.1.0/tasks/physical-sciences/physics/spin-glass-groundstate/instruction.md) | 寻找六个自旋玻璃实例的精确基态 | 组合全局优化与多实例可靠性；任何一个未到真最小值均失败 |

## 本轮验证与用时

- 29 项单元测试通过，包括自定义多行难度文字在运行配置序列化后进入作者调用，以及旧配置/空字段兼容。
- 作者 skill 通过 skill-creator 的 quick_validate；Ruff 检查与格式检查通过。
- 真实 Data Designer 的 mock 回归：`runs/pipeline/20260917T082658Z-3465475d/`，两条任务均完成一次审核退回修订，状态 mock_completed，validated=false；运行归档中的 difficulty_guidance 与真实示例全文一致。
- 以上证明配置和调用接入，不证明模型遵循效果或新生成任务的实际难度。本轮没有调用付费 API 或执行 benchmark 任务。
- 调研、实现及验证从 16:17:32（北京时间）开始，约 10 分钟完成；mock 作业自身用时另见该目录 timing.json。
