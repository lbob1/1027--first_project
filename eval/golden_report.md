# M-S3-T06 黄金测试集 QA 评测报告（端到端引用正确性）

- 对象：agent_graph.stream_answer（Router→hybrid_search→流式生成）
- 用例：12 条（literal 4 / semantic 4 / both 4），语料 4 份（复用 T05 三份 + doc_sec）

| 用例类 | 条数 | recall@5 | 引用正确率 | 关键词全命中(参考) |
|---|---|---|---|---|
| literal | 4 | 1.000 | 1.000 | 0.750 |
| semantic | 4 | 1.000 | 1.000 | 0.750 |
| both | 4 | 1.000 | 0.750 | 0.750 |
| **overall** | 12 | **1.000** | **0.917** | 0.750 |

## 逐条明细

| case | mode | query | 期望 | recall | 引用判定 | 解析来源 | kw 命中 | 答案末尾 |
|---|---|---|---|---|---|---|---|---|
| L1 | literal | 弹性伸缩是怎么计费的 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 出，而竞价实例则适合可中断的批处理任务。

【来源：doc_cloud.txt】 |
| L2 | literal | 共识机制有哪些方案 | doc_chain.txt | 1 | √ | ['doc_chain.txt'] | 2/2 | 机制的常见方案包括工作量证明与权益证明。

【来源：doc_chain.txt】 |
| L3 | literal | 什么是过拟合 | doc_ml.txt | 1 | √ | ['doc_ml.txt'] | 0/2 | 调优与效果评估等流程，但并未说明什么是过拟合。

【来源：doc_ml.txt】 |
| L4 | literal | 可用区与容灾怎么规划 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 地域备份则为极端灾难提供了最后一道保险。

【来源：doc_cloud.txt】 |
| S1 | semantic | AI 模型训练方法 | doc_ml.txt | 1 | √ | ['doc_ml.txt'] | 2/2 | 括召回率与 F1 值，应结合业务目标综合选择。

【来源：doc_ml.txt】 |
| S2 | semantic | 去中心化的电子记账方案 | doc_chain.txt | 1 | √ | ['doc_chain.txt'] | 2/2 | 与验证，仅需区块头即可确认交易的存在性。

【来源：doc_chain.txt】 |
| S3 | semantic | 流量高峰时如何应对服务器压力 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 个机房故障时保持服务连续，增强容灾能力。

【来源：doc_cloud.txt】 |
| S4 | semantic | 如何防止模型在新数据上表现变差 | doc_ml.txt | 1 | √ | ['doc_ml.txt'] | 0/2 | 后持续监控线上表现，并定期使用新数据重新训练。

【来源：doc_ml.txt】 |
| B1 | both | 区块链智能合约如何运行 | doc_chain.txt | 1 | √ | ['doc_chain.txt'] | 2/2 | 件时自动执行约定的逻辑，无需第三方介入。

【来源：doc_chain.txt】 |
| B2 | both | 对象存储和内容分发网络 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 。关于内容分发网络，资料中未涉及相关信息。
【来源：doc_cloud.txt】 |
| B3 | both | 检索增强生成如何降低模型编造 | doc_ml.txt | 1 | × | ['无'] | 1/2 | 供的资料中未涉及“检索增强生成”及其如何降低模型编造的相关内容。

【来源：无】 |
| B4 | both | 网络隔离与加密存储 | doc_sec.txt | 1 | √ | ['doc_cloud.txt', 'doc_sec.txt'] | 2/2 | 信息。

【来源：doc_cloud.txt】
【来源：doc_sec.txt】 |

结论：recall@5=1.000、引用正确率=0.917，均达 ≥0.8 验收线；失败用例 ['B3'] 已逐条分析（见 STATUS 事件记录）。
