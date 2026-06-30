# 全科医生辅助诊断系统软件工程设计

## 设计目标

- 保持主入口稳定：`启动服务.bat` 启动后端，`medrag_frontend/llm_index.html` 作为主要前端页面。
- 将后端从单文件拆解为 AI 友好的模块，便于后续让模型只读取必要文件。
- 保留 `MedRAG-main` 原始项目，当前以“方法学参考”和“本地可追溯代码资产”身份存在，不直接作为生产入口。
- 将知识层拆成图谱、参考文献、方法学三类结构化数据，降低 prompt 和 token 开销。

## 新结构

```text
medrag_backend/
  app/
    config.py
    models.py
    main.py
    data/
      graphs/
        undifferentiated_symptom_graph.json
      references/
        local_consensus.json
        web_guidelines.json
        chronic_guideline_catalog.json
    services/
      diagnosis_service.py
      knowledge_service.py
      llm_service.py
      reference_service.py
      session_store.py
  tools/
    extract_local_references.py
    build_vector_store.py
  llm_diagnosis.py
  start_llm.py
tests/
  test_diagnosis_flow.py
  test_retrieval_service.py
```

## MedRAG 的实际应用方式

当前不是把官方 MedRAG 原样塞进生产流程，而是把它的核心方法落到了本地项目：

- 图谱引导检索：先从未分化症状图谱定位候选疾病，而不是直接把所有信息交给大模型。
- 分层追问：按 `症状特征 -> 阳性/阴性症状 -> 红旗征 -> 体征 -> 检查 -> 处置` 六轮推进。
- 证据回填：候选诊断绑定本地 PDF 共识和公开指南，最终报告输出依据、概率与证据段落。

这种接法更适合基层全科场景，也更节约 token。

## 本地文献扩展

- `files/` 继续放入 PDF 后，可以运行 `python medrag_backend/tools/extract_local_references.py`
- 脚本会把前几页预览抽到 `extract/local_reference_drafts.json`
- 再将人工确认过的标题、摘要和证据段落整理进 `app/data/references/*.json`
- Windows 环境下也可以直接运行 `更新知识库.bat`

## 本地 RAG 向量层

- 运行 `python medrag_backend/tools/build_vector_store.py`
- 脚本会把 `references/*.json` 和 `files/*.pdf` 一起切块
- 生成本地 TF-IDF 向量索引到 `app/data/vector_store/`
- 后端最终报告会自动检索最相关的本地指南片段并并入参考文献展示

## 本地模型密钥

- 不要把真实 API Key 写进仓库文件或前端页面
- 推荐在 `medrag_backend/.env.local` 中保存本机私有配置
- 可参考 `medrag_backend/.env.local.example`
- `.env.local` 已加入 `.gitignore`
