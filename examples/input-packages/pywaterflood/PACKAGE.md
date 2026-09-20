# 原始包说明：Pywaterflood 井间连通性分析

这组资料涉及利用注入井与生产井的时间序列做 capacitance-resistance modeling（CRM）。论文介绍软件，代码库提供实现，仓库自带 CSV 与使用示例。可以从已有方法和代码中提取科学 coding 任务；具体问题和数量由出题者与运行配置决定，不预设难度。

## 资料入口

- 论文：Frank Male (2024), *Pywaterflood: Well connectivity analysis through capacitance-resistance modeling*, JOSS 9(95), 6191。https://joss.theoj.org/papers/10.21105/joss.06191
- 论文 PDF：https://www.theoj.org/joss-papers/joss.06191/10.21105.joss.06191.pdf
- 官方代码库：https://github.com/frank1010111/pywaterflood
- 软件文档：https://pywaterflood.readthedocs.io/en/stable/
- 数据入口：https://github.com/frank1010111/pywaterflood/tree/master/testing/data
- 注入序列：https://raw.githubusercontent.com/frank1010111/pywaterflood/master/testing/data/injection.csv
- 产出序列：https://raw.githubusercontent.com/frank1010111/pywaterflood/master/testing/data/production.csv
- 时间序列：https://raw.githubusercontent.com/frank1010111/pywaterflood/master/testing/data/time.csv

## 资料之间的关系与已知情况

仓库 README 的示例将以上三个 CSV 交给 CRM.fit，随后预测产出并计算残差。这是仓库提供的示例数据入口，不能未经核实就称其为真实油田观测。数据单位、生成背景和模型前提需继续核对论文、文档和源码。

2026-09-17 已检查论文页面、代码库介绍及三个 CSV 链接可读。当前仅提供链接，没有下载论文全文或冻结整个仓库。master/stable 是可变入口，出题者使用时记录实际 commit、版本、访问时间和必要快照。论文发表版与当前代码版本不应被默认视为相同。

软件包含 Python 和 Rust 实现，环境依赖与可用 wheel 需要构建验证。论文页面标注 CC BY 4.0，代码库标注 BSD-2-Clause；使用时核对实际文件及数据说明，保留相应来源信息。

来源内容已有明确方法与示例，但具体科学含义仍需角色阅读原文确认。发现示例公式、注释或代码不一致时记录问题，不直接把 README 的每个表达当成科学真值。
