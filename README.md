# MedRAG — 全科医生辅助诊断系统

> 基于 MedRAG 思想 + DeepSeek LLM 的未分化疾病辅助诊断平台

[![Python](https://img.shields.io/badge/Python-3.9+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-green.svg)](https://fastapi.tiangolo.com)
[![Vue.js](https://img.shields.io/badge/Vue.js-3.x-brightgreen.svg)](https://vuejs.org)
[![DeepSeek](https://img.shields.io/badge/LLM-DeepSeek--chat-orange.svg)](https://platform.deepseek.com)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](LICENSE)

---

## 功能亮点

| 能力 | 说明 |
|------|------|
| 🔍 多症状分析 | 输入自然语言症状，自动提取关键词并匹配疾病库 |
| 🤖 LLM 临床思维链 | 调用 DeepSeek-chat，生成专业的逐步追问与推理 |
| 💬 动态智能追问 | 根据诊断明确度动态追问，最多 6 轮 |
| 📊 诊断支持度更新 | 每轮追问后更新诊断支持度，仅用于排序，不代表患病概率 |
| 📋 结构化诊断报告 | 输出初步诊断、鉴别诊断、建议检查、治疗方案 |
| 🌐 Web 界面 | 基于 Vue 3 的响应式前端，支持 PC 和移动端 |
| 🐳 Docker 支持 | 一键 docker-compose 启动，生产环境就绪 |

---

## 系统架构

```
浏览器 (Vue 3 前端)
     │
     │  HTTP REST API
     ▼
FastAPI 后端 (Python)
  ├── /api/diagnosis/start      — 症状收集、红旗分流与首轮问题
  ├── /api/diagnosis/follow-up  — 动态结构化追问
  └── /api/diagnosis/final      — 最终辅助诊断报告
     │
     │  HTTPS
     ▼
DeepSeek Cloud (deepseek-chat)
```

---

## 快速开始

### 方式一：本地运行

```bash
# 1. 克隆仓库
git clone https://github.com/qq510457577-tech/quanke-medrag.git
cd quanke-medrag

# 2. 配置环境变量
cp medrag_backend/.env.example medrag_backend/.env
# 编辑 .env，填入您的 DeepSeek API Key

# 3. 安装依赖
pip install -r medrag_backend/requirements.txt

# 4. 启动后端
cd medrag_backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000

# 5. 浏览器打开前端
# 直接用浏览器打开 medrag_frontend/llm_index.html
```

### 方式二：Docker Compose（推荐）

```bash
cp .env.example .env
# 填写 .env 中的 DEEPSEEK_API_KEY

docker-compose up -d
```

访问地址：
- **前端**：http://localhost
- **后端 API 文档**：http://localhost:8000/docs

---

## 目录结构

```
medrag/
├── medrag_backend/          # FastAPI 后端
│   ├── app/                 # 生产模块化服务
│   │   ├── main.py          # FastAPI 路由
│   │   ├── services/        # 分诊、知识图谱、RAG、会话与 LLM 服务
│   │   └── data/            # 本地知识图谱、参考资料与 TF-IDF 索引
│   ├── llm_diagnosis.py     # 旧版兼容实现
│   ├── clinical_prompts.py  # 旧版英文提示词契约
│   └── requirements.txt     # Python 依赖
├── medrag_frontend/         # 前端页面
│   ├── index.html           # 主界面（临床思维链版）
│   └── llm_index.html       # LLM 深度版界面
├── MedRAG-main/             # 原始 MedRAG 研究代码
├── docs/                    # 研究文档
│   ├── medrag_research/     # MedRAG 项目研究报告
│   └── undifferentiated_disease/  # 未分化疾病研究
├── docker/                  # Docker 相关配置
├── docker-compose.yml       # Docker Compose 配置
├── Dockerfile               # 主 Dockerfile
├── .env.example             # 环境变量模板
└── README.md
```

---

## 医学知识库覆盖

系统内置以下系统疾病知识，并可通过 LLM 动态扩展：

- 🫁 **呼吸系统**：上呼吸道感染、流感
- 🫀 **心血管系统**：心绞痛、原发性高血压
- 🍽️ **消化系统**：急性胃炎、功能性消化不良
- 🧠 **神经系统**：偏头痛、紧张性头痛
- 🦴 **肌肉骨骼系统**：腰椎间盘突出、骨关节炎

---

## API 接口说明

### POST `/api/diagnosis/start` — 开始辅助诊断

```json
{
  "symptoms": [{"description": "发热、咳嗽两天，伴全身酸痛"}],
  "age": 35,
  "gender": "男"
}
```

### POST `/api/diagnosis/follow-up` — 提交本轮回答

根据本轮结构化回答，更新诊断支持度，并按需要返回下一轮问题。最多 6 轮；出现红旗征时停止常规追问。

### POST `/api/diagnosis/final` — 最终报告

输出结构化辅助诊断、需排除疾病、检查建议、风险分层和就医建议。

---

## 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 平台 API Key | ✅ |
| `DEEPSEEK_MODEL` | DeepSeek 模型名，默认 `deepseek-chat` | 否 |
| `DEEPSEEK_BASE_URL` | DeepSeek API 地址 | 否 |
| `CORS_ORIGINS` | 允许的跨域来源，以逗号分隔 | 否 |

申请地址：https://platform.deepseek.com

---

## 免责声明

> 本次辅助诊断仅用于参考，不能替代临床判断；具体诊疗方案请结合患者实际临床情况、体格检查、辅助检查结果及医生意见确定。如出现胸痛、呼吸困难、意识异常、严重出血、持续高热等急危重症请立即就医。

---

## License

MIT License — 自由使用，欢迎贡献。
