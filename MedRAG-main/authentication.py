"""
MedRAG authentication settings.
Keep local credentials in environment variables only.
"""

import os


dataset_path = "./dataset/df/train"
test_folder_path = "./dataset/df/test"
ground_truth_file_path = "./dataset/AI Data Set with Categories.csv"
augmented_features_path = "./dataset/knowledge graph of chronic pain.xlsx"

api_key = os.getenv("DEEPSEEK_API_KEY", "")
hf_token = ""

DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_EMBEDDING_MODEL = "deepseek-embedding"
DEEPSEEK_CHAT_MODEL = "deepseek-chat"
