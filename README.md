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
| 💬 动态智能追问 | 最多 3 轮结构化追问，逐步缩小诊断范围 |
| 📊 置信度更新 | 每轮追问后实时更新各疾病的匹配置信度 |
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
  ├── /api/analyze        — 症状分析 + 初步诊断
  ├── /api/diagnose       — 最终诊断报告
  ├── /api/chat           — 对话式问诊
  └── /api/knowledge      — 医学知识库概览
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
git clone https://github.com/qq510457577-tech/medrag.git
cd medrag

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，填入您的 DeepSeek API Key

# 3. 安装依赖
pip install -r medrag_backend/requirements.txt

# 4. 启动后端
cd medrag_backend
python main.py

# 5. 浏览器打开前端
# 直接用浏览器打开 medrag_frontend/index.html
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
│   ├── main.py              # 主服务（规则引擎 + LLM）
│   ├── llm_diagnosis.py     # LLM 临床思维链模块
│   ├── server.py            # 轻量版服务
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

### POST `/api/analyze` — 症状分析

```json
{
  "symptoms": [{"description": "发热、咳嗽两天，伴全身酸痛"}],
  "age": 35,
  "gender": "男"
}
```

### POST `/api/diagnose` — 最终诊断

根据追问回答生成结构化诊断报告，包含：初步诊断、诊断依据、鉴别诊断、建议检查、治疗建议、注意事项。

### POST `/api/chat` — 对话问诊

支持多轮自由对话，由 LLM 主导追问流程。

---

## 环境变量

| 变量名 | 说明 | 必填 |
|--------|------|------|
| `DEEPSEEK_API_KEY` | DeepSeek 平台 API Key | ✅ |

申请地址：https://platform.deepseek.com

---

## 免责声明

> ⚠️ **本系统仅供辅助参考，不构成正式医疗诊断建议。**  
> 实际临床诊断必须由具有执业资格的医师面诊确定。  
> 如出现紧急症状，请立即拨打 120 或前往最近医院急诊。

---

## License

MIT License — 自由使用，欢迎贡献。
