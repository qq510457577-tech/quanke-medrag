# 全科医生辅助诊断系统 - 使用指南

## 系统概述

本系统基于 **DeepSeek-V3.2-Speciale API** 实现真正的LLM临床思维链辅助诊断，支持：

- ✅ 多症状综合分析
- ✅ LLM驱动的动态临床思维链追问
- ✅ 诊断置信度实时更新
- ✅ 详细的医学推理过程展示
- ✅ 参考文献/指南引用

## API配置

- **API端点**: `https://api.deepseek.com/v3.2_speciale_expires_on_20251215`
- **模型**: `deepseek-chat`
- **API密钥**: 已配置（可通过环境变量覆盖）

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    前端 (Vue.js)                        │
│   llm_index.html ←→ API调用                            │
└─────────────────────┬───────────────────────────────────┘
                      │ HTTP REST API
┌─────────────────────▼───────────────────────────────────┐
│               后端 (Python FastAPI)                     │
│   llm_diagnosis.py                                      │
│   ├── /api/diagnosis/start    - 启动诊断               │
│   ├── /api/diagnosis/follow-up - 追问轮次              │
│   └── /api/diagnosis/final    - 获取最终诊断           │
└─────────────────────┬───────────────────────────────────┘
                      │ DeepSeek-V3.2 API
┌─────────────────────▼───────────────────────────────────┐
│               DeepSeek Cloud                           │
│   deepseek-chat 模型                                    │
└─────────────────────────────────────────────────────────┘
```

## 快速启动

### 1. 安装依赖

```bash
cd medrag_backend
pip install -r requirements.txt
```

### 2. 启动后端服务

```bash
cd medrag_backend
python start_llm.py
```

服务启动后访问：
- API地址：http://localhost:8000
- API文档：http://localhost:8000/docs

### 3. 打开前端页面

在浏览器中打开：`medrag_frontend/llm_index.html`

## 使用流程

### 第一步：输入患者信息

1. 填写基本信息（年龄、性别、既往病史）
2. 描述症状（可添加多个症状）
3. 可使用快速选择添加常见症状
4. 点击"开始LLM临床思维分析"

### 第二步：LLM临床思维追问

系统会：
1. 使用DeepSeek分析症状特征
2. 生成初始诊断假设（3-6个）
3. 设计第一轮追问问题
4. 根据回答动态调整置信度
5. 智能决定是否需要继续追问

**用户操作**：
- 回答每个问题
- 可选择：是/否、单选、多选、严重程度
- 点击"继续追问"进入下一轮
- 或点击"结束追问并获取结果"

### 第三步：查看诊断结果

系统展示：
- 诊断列表（按置信度排序）
- 每个诊断的详细推理过程
- 诊断依据
- 参考文献（可展开详情）
- 进一步检查/治疗建议

## API接口说明

### 1. 启动诊断
```
POST /api/diagnosis/start

请求体：
{
  "patient": {
    "age": 78,
    "gender": "male",
    "history": "高血压8年"
  },
  "symptoms": [
    {
      "description": "头晕3个月",
      "duration_years": 0,
      "duration_months": 3,
      "severity": 2
    }
  ]
}

响应：
{
  "session_id": "uuid",
  "symptom_analysis": "症状分析",
  "differential_diagnoses": [...],
  "current_questions": [...],
  "reasoning_chain": "推理过程",
  "is_diagnosis_clear": false
}
```

### 2. 追问
```
POST /api/diagnosis/follow-up

请求体：
{
  "session_id": "uuid",
  "answers": [
    {
      "question_id": "q1",
      "question": "头晕是否与体位变化有关？",
      "answer": "是",
      "answer_type": "yesno"
    }
  ]
}
```

### 3. 获取最终诊断
```
POST /api/diagnosis/final

请求体：
{
  "session_id": "uuid",
  "answers": [...]
}

响应：
{
  "diagnoses": [
    {
      "disease": "疾病名称",
      "confidence": 85,
      "diagnosis_type": "主要诊断",
      "reasoning": "详细推理过程",
      "evidence": ["证据1", "证据2"],
      "references": [{"title": "指南", "content": "..."}],
      "suggestions": ["建议1", "建议2"]
    }
  ],
  "clinical_reasoning": "整体临床思维链"
}
```

## LLM临床思维链设计

### 诊断流程

```
1. 症状收集
   ↓
2. 鉴别诊断（生成3-6个可能的诊断）
   ↓
3. 置信度评估（初始20-40%）
   ↓
4. 追问设计（LLM根据当前状态智能生成问题）
   ↓
5. 回答处理（更新各诊断置信度）
   ↓
6. 判断是否明确（置信度≥70%或差距≥40%）
   ↓
   ├─ 明确 → 生成最终报告
   └─ 不明确 → 返回步骤4
```

### 追问策略

- **优先级**：优先澄清最需要鉴别的诊断
- **动态调整**：根据回答实时更新置信度
- **医学逻辑**：问题设计遵循临床思维
- **循证依据**：参考相关指南和文献

## 文件说明

```
medrag_backend/
├── llm_diagnosis.py    # 主后端服务（DeepSeek集成）
├── start_llm.py        # 启动脚本
└── requirements.txt    # Python依赖

medrag_frontend/
└── llm_index.html      # LLM诊断前端页面
```

## 注意事项

1. **API密钥**：已配置DeepSeek API密钥，如有需要可修改 `llm_diagnosis.py` 中的配置
2. **网络连接**：需要能访问 `api.deepseek.com`
3. **诊断局限性**：本系统仅供辅助参考，不能替代执业医师诊断
4. **数据安全**：对话数据存储在内存中，重启服务会清除

## 故障排除

### 前端无法连接后端
- 确保后端服务正在运行：`python start_llm.py`
- 检查端口8000是否被占用

### DeepSeek API调用失败
- 检查网络连接
- 确认API密钥有效
- 查看后端控制台错误信息
- 确认API端点是否正确

### 诊断结果不理想
- 尝试提供更更详细的症状描述
- 增加追问轮次获取更多信息
- 补充既往病史等关键信息

---

**版本**：2.0.0  
**模型**：DeepSeek-V3.2-Speciale (deepseek-chat)  
**API端点**：https://api.deepseek.com/v3.2_speciale_expires_on_20251215  
**更新日期**：2026-03-05
