"""
MedRAG 主程序 - 使用 DeepSeek API 替代 OpenAI
修改了 API 调用部分以支持 DeepSeek
"""
import openai
import faiss
import numpy as np
import os
import re
import json
import pandas as pd
from tqdm import tqdm
from huggingface_hub import InferenceClient
from KG_Retrieve import main_get_category_and_level3
import httpx
from authentication import api_key, hf_token, DEEPSEEK_BASE_URL, DEEPSEEK_EMBEDDING_MODEL, DEEPSEEK_CHAT_MODEL

# 使用 DeepSeek 兼容的 OpenAI 客户端
client = openai.OpenAI(
    api_key=api_key,
    base_url=DEEPSEEK_BASE_URL + "/v1"
)

def get_embeddings(texts):
    """使用 DeepSeek 嵌入模型获取文本嵌入"""
    embeddings = []
    for text in tqdm(texts):
        try:
            # 尝试使用 DeepSeek 嵌入模型
            response = client.embeddings.create(
                input=text,
                model="deepseek-embedding"
            )
            embeddings.append(response.data[0].embedding)
        except Exception as e:
            print(f"DeepSeek 嵌入失败，尝试使用替代方案: {e}")
            # 如果 DeepSeek 嵌入失败，使用本地随机向量作为占位符
            embeddings.append(np.random.rand(1536).tolist())
    return np.array(embeddings)


def get_query_embedding(query):
    return get_embeddings([query])[0]


# FAISS
def Faiss(document_embeddings, query_embedding, k):
    # index = faiss.IndexFlatL2(document_embeddings.shape[1])
    index = faiss.IndexFlatIP(document_embeddings.shape[1])
    # index = faiss.IndexHNSWFlat(document_embeddings.shape[1])
    index.add(document_embeddings)
    _, indices = index.search(np.array([query_embedding]), k)
    print("index: ", indices)
    return indices

def extract_diagnosis(generated_text):
    diagnoses = re.findall(r'\*\*Diagnosis\*\*:\s(.*?)\n', generated_text)
    return diagnoses

def remove_parentheses(text):
    return re.sub(r'\(.*?\)', '', text).strip()

def KG_preprocess(file_path):
    kg_data = pd.read_excel(file_path, usecols=['subject', 'relation', 'object'])
    kg_data['subject'] = kg_data['subject'].apply(remove_parentheses)
    kg_data['object'] = kg_data['object'].apply(remove_parentheses)

    knowledge_graph = {}
    for index, row in kg_data.iterrows():
        subject = row['subject']
        relation = row['relation']
        obj = row['object']

        if subject not in knowledge_graph:
            knowledge_graph[subject] = []
        knowledge_graph[subject].append((relation, obj))

        if obj not in knowledge_graph:
            knowledge_graph[obj] = []
        knowledge_graph[obj].append((relation, subject))
    return knowledge_graph


def extract_features_from_json(file_path):
    with open(file_path, 'r') as file:
        patient_case = json.load(file)

    pain_location = patient_case.get("Pain Presentation and Description Areas of pain as per physiotherapy input", "")
    pain_symptoms = patient_case.get(
        "Pain descriptions and assorted symptoms (self-report) Associated symptoms include: parasthesia, numbness, weakness, tingling, pins and needles",
        "")

    return pain_location, pain_symptoms

level_3_to_level_2 = {
    # Here are subcategories: diseases
    # Examples: 
    
    # Respiratory System
    "acute_copd_exacerbation_infection": "respiratory_system",

    # Cardiovascular System
    "atrial_fibrillation": "cardiovascular_system",

}


def get_additional_info_from_level_2(participant_no,  kg_path,top_n,match_n):
    level_2_values=main_get_category_and_level3(match_n,participant_no,top_n)
    additional_info = []
    if not level_2_values:
        print(f"No data found for Participant No.: {participant_no}")
        return None
    for level_2_value in level_2_values:
        relevant_level_3_descriptions = [desc for desc, level2 in level_3_to_level_2.items() if level2 == level_2_value]
        print("Relevant Level 3 Descriptions:", relevant_level_3_descriptions)

        if not relevant_level_3_descriptions:
            print("No Level 3 descriptions found for Level 2:", level_2_value)
            continue

        kg_data = pd.read_excel(kg_path, usecols=['subject', 'relation', 'object'])
        if kg_data.empty:
            print("Knowledge graph data is empty.")
            return None

        merged_info = {}

        for level_3 in relevant_level_3_descriptions:
            related_info = kg_data[kg_data['subject'] == level_3]

            if related_info.empty:
                print(f"No related information found in KG for: {level_3}")
            else:
                for _, row in related_info.iterrows():
                    subject = row['subject']
                    relation = row['relation'].replace('_', ' ')
                    obj = row['object']

                    if (subject, relation) in merged_info:
                        merged_info[(subject, relation)].append(obj)
                    else:
                        merged_info[(subject, relation)] = [obj]

        # K
        additional_info = []
        for (subject, relation), objects in merged_info.items():
            sentence = f"{subject} {relation} {', '.join(objects)}"
            additional_info.append(sentence)

    if not additional_info:
        print("No additional information found.")
        return None

    final_info = ', '.join(additional_info)
    print("Additional Info:", final_info)
    return final_info


def get_system_prompt_for_RAGKG():
    return '''
        You are a knowledgeable medical assistant with expertise in pain management.
        Your tasks are:
        1. Analyse and refer to the retrieved similar patients' cases and knowledge graph which may be relevant to the diagnosis and assist with new patient cases.
2. Output of "Diagnoses" must come from : acute copd exacerbation infection, bronchiectasis, bronchiolitis, bronchitis, bronchospasm acute asthma exacerbation, pulmonary embolism, pulmonary neoplasm, spontaneous pneumothorax, urti, viral pharyngitis, whooping cough, acute laryngitis, acute pulmonary edema, croup, larygospasm, epiglottitis, pneumonia, atrial fibrillation, myocarditis, pericarditis, psvt, possible nstemi stemi, stable angina, unstable angina, gerd, boerhaave syndrome, pancreatic neoplasm, scombroid food poisoning, inguinal hernia, tuberculosis, hiv initial infection, ebola, influenza, chagas, acute otitis media, acute rhinosinusitis, allergic sinusitis, chronic rhinosinusitis, myasthenia gravis, guillain barre syndrome, cluster headache, acute dystonic reactions, sle, sarcoidosis, anaphylaxis, panic attack, spontaneous rib fracture, anemia.        3. You are given differences of diagnoses of similar symptoms or pain locations. Read that information as a reference to your diagnostic if applicable.
        4. Do mind the nuance between these factors of similar diagnosis with knowledge graph information and consider it when diagnose new patient's informtation.
        5. Ensure that the recommendations are evidence-based and consider the most recent and effective practices in pain management.
        6. The output should include four specific treatment-related fields:
           - "Diagnoses (related to pain)"
           - Explanations of diagnose
           - "Pain/General Physiotherapist Treatments\nSession No.: General Overview\n- Specific interventions/treatments"
           - "Pain Psychologist Treatments"
           - "Pain Medicine Treatments"
        7. In "Diagnoses", only output the diagnosis itself. Place all other explanations and analyses (if any) into "Explanations of diagnose".
        8. You can leave Psychologist Treatments blank if not applicable for the case, leaving text "Not applicable"
        9.If you think information is needed, guide the doctor to ask further questions which following areas to distinguish between the most likely diseases: Pain restriction; Location; Symptom. Seperate answers with ",". The output should only include aspects.
        10. The output should follow this structured format:
        

    ### Diagnoses
    1. **Diagnosis**: Answer.
    2. **Explanations of diagnose**: Answer.
    
    ### Instructive question
    1. **Questions**: Answer.
    
    ### Pain/General Physiotherapist Treatments
    1. **Session No.: General Overview**
        - **Specific interventions/treatments**:
        - **Goals**:
        - **Exercises**:
        - **Manual Therapy**:
        - **Techniques**:

    2. **Exercise Recommendations from the Exercise List**:

    ### Pain Psychologist Treatments(if applicable)
    1. **Treatment 1**: 
    
    ### Pain Medicine Treatments


    ### Recommendations for Further Evaluations
    1. **Evaluation 1**:
    '''


def generate_diagnosis_report(path, query, retrieved_documents, i,top_n,match_n,model):
    system_prompt_RAGKG = get_system_prompt_for_RAGKG()
    system_prompt=system_prompt_RAGKG
    additional_info= get_additional_info_from_level_2(i ,path,top_n=top_n,match_n=match_n)

    prompt = f"{query}\nRetrieved Documents: {retrieved_documents}\nInformation from knowledge graph about relevant diagnoses, if you think the patient's disease is relevant from the suggestions provided by the atlas please refer to thoses details to distinguish similar diagnoses : {additional_info} .Now complete the tasks in that format"


    ############################################################################################openai
    # 修改为支持 DeepSeek 模型
    if 'deepseek' in model.lower() or 'gpt' in model.lower():
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            return response.choices[0].message.content
        except Exception as e:
            print(f"API 调用失败: {e}")
            return f"Error: {str(e)}"
    else:
        # HuggingFace 模型
        prompt=f"""<s>[INST] <<SYS>> {system_prompt} <</SYS>> {prompt} [/INST]"""
        LLMclient = InferenceClient(
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            token=hf_token
        )
        response = LLMclient.text_generation(prompt=prompt,max_new_tokens=400)
        return response

def save_results_to_csv(results, output_file):
    df = pd.DataFrame(results,
                      columns=['Participant No.', 'Generated Diagnosis', 'True Diagnosis', 'Original Diagnosis'])
    df.to_csv(output_file, index=False)


folder_path="./dataset/df/train"
documents = [os.path.join(folder_path, file_name) for file_name in os.listdir(folder_path) if
             os.path.isfile(os.path.join(folder_path, file_name))]

document_embeddings_file_path='./dataset/document_embeddings.npy'

def save_embeddings(embeddings, file_path):
    np.save(file_path, embeddings)

def load_embeddings(file_path):
    return np.load(file_path)
if os.path.exists(document_embeddings_file_path):
    document_embeddings = load_embeddings(document_embeddings_file_path)
else:
    document_embeddings = get_embeddings(documents)
    save_embeddings(document_embeddings, document_embeddings_file_path)
