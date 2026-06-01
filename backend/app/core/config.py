from pathlib import Path

from pydantic_settings import BaseSettings


BASE_DIR = Path(__file__).resolve().parents[3]

class Settings(BaseSettings):
    PROJECT_NAME: str = "Paper Knowledge Base"
    
    # Auth
    SECRET_KEY: str = "your-super-secret-key-change-this"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 # 1 day
    
    # Neo4j
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "password"
    
    # ChromaDB
    CHROMA_PATH: str = "./chroma_db"
    
    # AI
    LLM_API_KEY: str = ""
    S2_API_KEY: str = ""
    HF_TOKEN: str = ""
    EMBEDDING_MODEL_NAME: str = "thenlper/gte-large" #"sentence-transformers/all-MiniLM-L6-v2"
    OPENALEX_API_KEY: str = ""
    
    # Logic
    MIN_PAPER_COUNT: int = 5

    class Config:
        env_file = BASE_DIR / ".env"

settings = Settings()
