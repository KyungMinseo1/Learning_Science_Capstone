import re
import chromadb, os
from chromadb.config import Settings as ChromaSettings
from .config import settings

class ChromaClient:
    def __init__(self):
        host = os.getenv("CHROMA_HOST")
        if host:
            self.client = chromadb.HttpClient(
                host=host, 
                port=int(os.getenv("CHROMA_PORT", 8000))
            )
        else:
            self.client = chromadb.PersistentClient(path=settings.CHROMA_PATH)

    def _sanitize_collection_name(self, user_id: str) -> str:
        # Chroma requires names with characters [a-zA-Z0-9._-], 3-512 chars, start/end with alnum
        base = f"papers_user_{user_id}"
        # replace disallowed chars with '_'
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", base)
        # trim to max length
        if len(safe) > 512:
            safe = safe[:512]
        # ensure starts and ends with alnum
        safe = re.sub(r'^[^A-Za-z0-9]+', '', safe)
        safe = re.sub(r'[^A-Za-z0-9]+$', '', safe)
        # fallback if empty
        if not safe:
            safe = "papers_user"
        # ensure minimum length (pad if necessary)
        if len(safe) < 3:
            safe = safe.ljust(3, '_')
        return safe

    def get_collection(self, user_id: str):
        # Native multi-tenancy logic could be implemented here
        # Use sanitized user-specific collection names
        name = self._sanitize_collection_name(user_id)
        return self.client.get_or_create_collection(name=name)
    

chroma_client = ChromaClient()
