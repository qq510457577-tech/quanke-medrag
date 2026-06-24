"""
MedRAG 认证配置 - 使用 DeepSeek API 替代 OpenAI
"""
import os

# 路径配置
dataset_path = './dataset/df/train'
test_folder_path = "./dataset/df/test"
ground_truth_file_path = './dataset/AI Data Set with Categories.csv'
augmented_features_path = './dataset/knowledge graph of chronic pain.xlsx'

# DeepSeek API 配置
# DeepSeek API 与 OpenAI 格式兼容
api_key = os.getenv("DEEPSEEK_API_KEY", "your-deepseek-api-key-here")
hf_token = ""  # Hugging Face token (可选)

# DeepSeek 配置
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_EMBEDDING_MODEL = "deepseek-embedding"  # DeepSeek 嵌入模型
DEEPSEEK_CHAT_MODEL = "deepseek-chat"  # DeepSeek 对话模型
