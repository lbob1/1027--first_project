# M-S3-T05 检索评测基线报告

- 语料：3 份主题互不重叠文档（doc_ml.txt/机器学习, doc_cloud.txt/云计算弹性伸缩, doc_chain.txt/区块链），均 500+ 字
- 用例：6 条（literal/semantic/both 各 2）
- 检索参数：top_k=5，三路为 search_fts / search_vec / search_hybrid（RRF_K=60）

| 用例类 | 指标 | fts | vec | hybrid |
|---|---|---|---|---|
| literal | recall@5 | 1.000 | 1.000 | 1.000 |
| literal | mrr@5 | 1.000 | 1.000 | 1.000 |
| semantic | recall@5 | 0.000 | 1.000 | 1.000 |
| semantic | mrr@5 | 0.000 | 1.000 | 1.000 |
| both | recall@5 | 1.000 | 1.000 | 1.000 |
| both | mrr@5 | 1.000 | 1.000 | 1.000 |
| overall | recall@5 | 0.667 | 1.000 | 1.000 |
| overall | mrr@5 | 0.667 | 1.000 | 1.000 |

结论：semantic 类用例上 vec（稠密路）recall 优于 fts（稀疏路），混合对中文语义查询必要；both 类用例上 hybrid MRR 不差于任一单路（双路贡献相加的 RRF 生效）；literal 类用例上 fts（稀疏路）字面命中不弱于 vec；整体 recall@5：hybrid 不低于任一单路（融合去重不误删）。
