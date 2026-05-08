import ollama
import openai
from ..core.config import settings
from sentence_transformers import SentenceTransformer

class AIService:
    def __init__(self):
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

    async def get_summary_and_keywords(self, text: str, provider: str = "openai"):
        prompt = f"""
        Analyze the following research paper abstract/text. 
        Provide a concise summary and 3-5 key keywords.
        Format:
        Summary: <summary>
        Keywords: <keyword1>, <keyword2>, ...
        
        Text: {text}
        """
        
        # Priority 1: Requested Provider
        if provider == "openai" and settings.LLM_API_KEY:
            try:
                client = openai.OpenAI(api_key=settings.LLM_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                return self._parse_llm_response(response.choices[0].message.content)
            except Exception as e:
                print(f"OpenAI API failed, falling back to Ollama: {e}")
        
        # Priority 2: Fallback to Ollama
        try:
            response = ollama.chat(
                model="llama3",
                messages=[{'role': 'user', 'content': prompt}]
            )
            return self._parse_llm_response(response['message']['content'])
        except Exception as e:
            print(f"Ollama failed: {e}")
            return {"summary": "Summary generation failed.", "keywords": []}

    def _parse_llm_response(self, content: str):
        lines = content.strip().split("\n")
        summary = ""
        keywords = []
        for line in lines:
            if line.startswith("Summary:"):
                summary = line.replace("Summary:", "").strip()
            elif line.startswith("Keywords:"):
                keywords = [k.strip() for k in line.replace("Keywords:", "").split(",")]
        return {"summary": summary, "keywords": keywords}

    def get_embedding(self, text: str):
        return self.embedding_model.encode(text).tolist()

ai_service = AIService()
