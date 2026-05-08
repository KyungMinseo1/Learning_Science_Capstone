import chromadb
from chromadb.config import Settings as ChromaSettings
from .config import settings

class ChromaClient:
    def __init__(self):
        self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)

    def get_collection(self, user_id: str):
        # Native multi-tenancy logic could be implemented here
        # For now, we'll use user-specific collection names for simplicity
        return self.client.get_or_create_collection(name=f"papers_user_{user_id}")

chroma_client = ChromaClient()
