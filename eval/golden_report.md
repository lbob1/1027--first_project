# M-S3-T06 黄金测试集 QA 评测报告（端到端引用正确性）

- 对象：agent_graph.stream_answer（Router→hybrid_search→流式生成）
- 用例：12 条（literal 4 / semantic 4 / both 4），语料 4 份（复用 T05 三份 + doc_sec）

| 用例类 | 条数 | recall@5 | 引用正确率 | 关键词全命中(参考) |
|---|---|---|---|---|
| literal | 4 | 1.000 | 1.000 | 0.750 |
| semantic | 4 | 1.000 | 1.000 | 0.750 |
| both | 4 | 1.000 | 0.500 | 0.500 |
| **overall** | 12 | **1.000** | **0.833** | 0.667 |

## 逐条明细

| case | mode | query | 期望 | recall | 引用判定 | 解析来源 | kw 命中 | 答案末尾 |
|---|---|---|---|---|---|---|---|---|
| L1 | literal | 弹性伸缩是怎么计费的 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 明显的负载，包年包月适合长期稳定的负载。

【来源：doc_cloud.txt】 |
| L2 | literal | 共识机制有哪些方案 | doc_chain.txt | 1 | √ | ['doc_chain.txt'] | 2/2 | 问题，常见方案包括工作量证明与权益证明。

【来源：doc_chain.txt】 |
| L3 | literal | 什么是过拟合 | doc_ml.txt | 1 | √ | ['doc_ml.txt'] | 0/2 | 换拟合复杂函数等内容，但并未说明什么是过拟合。

【来源：doc_ml.txt】 |
| L4 | literal | 可用区与容灾怎么规划 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 跨地域备份为极端灾难提供了最后一道保险。

【来源：doc_cloud.txt】 |
| S1 | semantic | AI 模型训练方法 | doc_ml.txt | 1 | √ | ['doc_ml.txt'] | 2/2 | 衰减，定期使用新数据重新训练是必要的运维动作。

【来源：doc_ml.txt】 |
| S2 | semantic | 去中心化的电子记账方案 | doc_chain.txt | 1 | √ | ['doc_chain.txt'] | 2/2 | 公钥派生，私钥的保管责任完全在用户一方。

【来源：doc_chain.txt】 |
| S3 | semantic | 流量高峰时如何应对服务器压力 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 采用按量计费模式，配合弹性伸缩策略使用。

【来源：doc_cloud.txt】 |
| S4 | semantic | 如何防止模型在新数据上表现变差 | doc_ml.txt | 1 | √ | ['doc_ml.txt'] | 0/2 | 践中常用网格搜索或贝叶斯优化来寻找合适的组合。

【来源：doc_ml.txt】 |
| B1 | both | 区块链智能合约如何运行 | doc_chain.txt | 1 | √ | ['doc_chain.txt'] | 2/2 | 件时自动执行约定的逻辑，无需第三方介入。

【来源：doc_chain.txt】 |
| B2 | both | 对象存储和内容分发网络 | doc_cloud.txt | 1 | √ | ['doc_cloud.txt'] | 2/2 | 涉及相关信息，无法基于现有资料进行回答。

【来源：doc_cloud.txt】 |
| B3 | both | 检索增强生成如何降低模型编造 | doc_ml.txt | 1 | × | ['doc_ml.txt, doc_sec.txt, doc_cloud.txt, doc_chain.txt'] | 1/2 | c_sec.txt, doc_cloud.txt, doc_chain.txt】 |
| B4 | both | 网络隔离与加密存储 | doc_sec.txt | 1 | × | ['doc_sec.txt, doc_cloud.txt'] | 1/2 | 以回答该问题。

【来源：doc_sec.txt, doc_cloud.txt】 |

结论：recall@5=1.000、引用正确率=0.833，均达 ≥0.8 验收线；失败用例 ['B3', 'B4'] 已逐条分析（见 STATUS 事件记录）。
