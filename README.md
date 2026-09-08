# Cross-Attention 困境预测重建项目

本项目是本次从公开披露重建的数据库与代码，**不是找回的原始数据、原始程序或论文结果**。当前版本可核验数据来源、计算年度/季度特征、运行模型测试，并为完整研究数据准备训练入口。

目前数据库含 2 家核验公司、26 份来源文件、142 条财务原值、45 条派生值及 74 条计算依赖。4 条公司—预测年份记录中，传智教育的 2024、2025 记录因预测前已经困境而排除；美的的两条记录仍缺完整证据。**正式分析样本为 0，未重新训练困境预测模型，也未复现原稿 F1/AUC。** 两家公司不是推定的原稿成员。

详细判断、已确认规则和待补内容见 [重建核验报告](docs/Reconstruction_Review.md)。

## 本地运行

克隆仓库或解压交付包后进入本目录。验证环境为 Python 3.12、PyTorch 2.8.0 CPU、Transformers 4.55.4。不要把这些新环境信息写成原实验环境。

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu
python -m pip install -r requirements-lock.txt
python -m pip install -e . --no-deps
python -m distress audit
python scripts/validate.py
```

Windows 使用 `.venv\Scripts\activate` 激活环境。网络只用于安装依赖、另行下载公开披露和模型权重；数据库检查及 35 项单元测试可离线运行，测试不下载预训练权重。

现成数据库是 `data/reconstruction.sqlite`，可用 SQLite 工具直接打开。数据库来源单元测试和 26 份 PDF 的 SHA-256 核对已经执行。SQL 示例：

```sql
SELECT sample_id, baseline_status, outcome, analytical_eligible
FROM sample_register ORDER BY sample_id;

SELECT f.metric, f.period_end, f.raw_value, f.source_unit,
       f.value_normalized, d.disclosed_date, f.page, d.url
FROM facts f JOIN documents d USING(document_id)
WHERE f.firm_id = '003032.SZ' AND f.metric = 'net_profit';
```

`value_normalized` 的货币金额统一为人民币元；`shares` 保留股数。原始单位、原值和精确十进制字符串仍保留，避免千元/元混用和浮点舍入。费用或资本支出在原表以括号负数列示时，`raw_value` 保留负号，`sign_adjustment=-1` 将计算所需的支出幅度转为正值。归一化公式是 `raw_value × multiplier × sign_adjustment`。数据库页码均为 PDF 从 1 开始的物理页码。

## 可复现的数据构建

```bash
python -m distress.build --database data/rebuilt.sqlite --report reports/rebuilt_audit.json
python -m distress features --firm 000333.SZ --year 2025
python -m distress download-sources
```

构建命令拒绝覆盖已有文件。原值的权威输入是 `data/verified_seed.json`；所有来源 URL 和 SHA-256 都在其中。PDF 不随项目分发，下载后存入忽略的 `data/raw/`。如果远端文件改变，下载器会停止，不会悄悄替换原版本。

`build.py` 目前建立的是已核实案例，不是全 A 股自动贴标器。新增公司需要历史样本框、披露版本和逐项审阅的事实记录；不要用今天仍上市的公司名单替代历史总体。

公开公告查询示例：

```bash
python -m distress collect --stock 003032 --org gfbj0839976 --start 2023-01-01 --end 2025-04-30 --output data/query_cache
```

查询会缓存完整响应并处理分页，结果只是待审阅的公告目录。无搜索命中不等于没有 ST；“可能被实施风险警示”的公告也不等于实际实施。审阅新 PDF 后，将来源及原值按种子文件的字段格式追加，再构建新版本。当前没有把通用 PDF 正则抽取结果自动认定为已验证事实。

年度 MD&A 的边界抽取示例：

```bash
python -m distress extract-section --document 1222951181 --name 'MD&A' --start-page 12 --end-page 68
```

输出是 **candidate**；仍需检查表格、页眉页脚和语义段落后才能设为 verified，并更新文本 SHA-256。种子数据库尚无经完整清洗的文本章节。真实模型检查仅使用该年报 PDF 第 12 页的 MD&A 文本，不冒充完整样本语料。

## 模型和训练

`src/distress/model.py` 实现年度 Transformer、季度 LSTM、中文 FinBERT、三条交叉注意力路径、门控和分类器：

| 模式 | 用途 |
|---|---|
| `manuscript_singleton` | 按原稿单 Key/Value 和全局 softmax 权重解释实现，用于复查退化问题 |
| `sequence_cross_attention` | 保留多个文本 token / 季度状态作为 Key/Value，门控随样本变化 |
| `mean_fusion` | 同样六路特征，改为均匀融合 |
| `gating_only`、`concat` | 相同三种模态的门控/拼接对照 |
| `long_only`、`short_only`、`text_only` | 单模态对照 |
| `numerical_only` | 同样 90+32 个财务输入，去掉文本 |

修正版保留原稿三条方向和六个融合向量。Query 仍用末时点汇总向量；文本 Key/Value 为全部非 padding token，季度 Key/Value 为 4 个 LSTM 状态。源码显式区分这些修改，不把它们当作原始代码的事实。

`configs/model.json` 固定超参数、随机种子和中文模型版本。中文模型是 `yiyanghkust/finbert-tone-chinese`，revision 为 `e91b1a3af10e1e8c9c03429d3cd7d5e9a1c8000d`。权重不打包；模型卡及历史可用性限制见核验报告。正式训练时文本编码器参与微调；`AutoModel` 只取隐藏状态，原情感分类头不作为困境分类器。

缺失率口径已由用户确认：每条公司—预测日期记录，年度分支以 90 个值、季度分支以 32 个值为固定分母，分别执行“超过 30%”剔除。年度最多缺失 27 个、季度最多缺失 9 个；年度达到 28 个或季度达到 10 个即排除整条记录。缺失率在来源核实、特征构建后且插补前计算，不能先填补再筛选。

尚未采集或审阅的资料记为 pending_collection，不能直接当作公司真实缺失并形成剔除结论。当前四条核验记录仍处于资料未齐状态。完成两条分支的来源审阅后，在 sample_evidence 中分别记录 feature_collection / annual、quarterly 的 verified_complete 证据及说明，导出程序才执行正式缺失率筛选。

完整训练还需核实后的历史研究总体、合格基线、完整结局、经审核文本和冻结的数据版本。当前导出仍因历史总体与事件证据不完整而停止；缺失率分母已不再是待确认问题。

```bash
# 仅在数据完善、研究口径冻结后使用；当前版本会因尚未满足条件而停止。
python -m distress export --dataset-id incident-v1 --output data/incident-v1.json
python -m distress.train --database data/reconstruction.sqlite --manifest data/incident-v1.json --output runs/sequence_seed42 --seed 42 --variant sequence_cross_attention
```

训练入口保存配置、环境、训练集拟合的预处理参数、逐轮损失、最佳权重、优化器/学习率状态、随机状态和逐样本测试预测；恢复最佳验证损失对应的权重后才评估测试集。输出目录拒绝覆盖。批次尾部只有 1 条记录时与前一批合并，防止 BatchNorm 出错且不丢样本。这里实现了保存状态，尚未提供断点续训命令。

预处理对训练集估计截尾点、行业中位数和标准化参数；验证/测试不参与估计。缺失标签永远不填补。模型输入仍保持 18/8 维；缺失掩码作为审计资料保留，不额外改变模型通道。

独立运行真实预训练权重检查时，先按固定 revision 下载模型，再运行：

```bash
hf download yiyanghkust/finbert-tone-chinese --revision e91b1a3af10e1e8c9c03429d3cd7d5e9a1c8000d --local-dir checkpoints/chinese_finbert
python scripts/verify_pretrained.py --model-path checkpoints/chinese_finbert --pdf data/raw/1222951181.pdf --report reports/pretrained_smoke.json
```

该检查使用真实年报文本、随机生成的财务输入和测试标签，验证梯度与张量形状。它不进行训练更新、不生成金融预测成绩。

## 文件与 GitHub

| 位置 | 内容 |
|---|---|
| `data/reconstruction.sqlite` | 可直接打开的底层数据库 |
| `data/verified_seed.json` | 可重建的原值、来源、事件与审计记录 |
| `configs/` | 已确认时间线、会计口径、剩余问题和新实现默认值 |
| `src/distress/` | 数据库、特征、采集、模型、预处理、训练与统计代码 |
| `tests/` | 35 项离线测试 |
| `reports/` | 来源核对、数据库核对、软件测试及真实权重检查记录 |
| `docs/` | 中文核验报告与英文方法草稿 |
| `.github/workflows/tests.yml` | 推送和拉取请求触发的测试流程；远端运行状态见仓库 Actions 页面 |

项目仓库为 [janesjw/cross-attention-distress](https://github.com/janesjw/cross-attention-distress)，首次上传时设为 Private。当前阶段用于研究重建，待数据和论文完善后再另行决定公开。PDF、模型权重、运行输出和环境文件已加入忽略规则。SQLite 适合本地核验和版本快照，GitHub 只托管文件与代码，不提供在线可写数据库服务；以后需要网站/API 时可迁移至 PostgreSQL 或独立数据库服务。

尚未替研究作者选择代码的公开授权许可证。第三方模型和来源文件遵循各自条款。不要把遗失原实验中未核实的 5,142 条记录及旧成绩加入本数据库。
