import uvicorn

if __name__ == "__main__":
    uvicorn.run("llm_diagnosis:app", host="0.0.0.0", port=8000, log_level="info")
