import json
import os
import logging
import time
from urllib import error, request

import ollama
import openai
from ..core.config import settings
from sentence_transformers import SentenceTransformer
try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger(__name__)


if settings.HF_TOKEN:
    os.environ["HF_TOKEN"] = settings.HF_TOKEN
    os.environ.setdefault("HUGGINGFACE_HUB_TOKEN", settings.HF_TOKEN)


class AIService:
    def __init__(self):
        self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL_NAME)

    def _clean_text_response(self, content: str) -> str:
        return content.strip().strip('"').strip("'")

    def _extract_text_from_gemini_response(self, payload: dict) -> str:
        candidates = payload.get("candidates", [])
        if not candidates:
            return ""

        content = candidates[0].get("content", {})
        parts = content.get("parts", [])
        return "\n".join(part.get("text", "") for part in parts if part.get("text"))

    def _call_gemini(self, prompt: str) -> str:
        if genai is None:
            raise ValueError("Gemini library is missing")
        if not settings.LLM_API_KEY:
            raise ValueError("Gemini API key is missing")

        client = genai.Client(api_key=settings.LLM_API_KEY)

        body = {
            "contents": [
                {
                    "parts": [
                        {"text": prompt},
                    ]
                }
            ]
        }
        response = client.models.generate_content(
            model="gemini-3.1-flash-lite",
            contents=prompt
        )

        return response.text

    def get_keywords_and_importance(
        self,
        text: str,
        provider: str = "openai",
        min_keywords: int = 3,
        max_keywords: int = 7,
        manual_keywords: list | None = None,
    ):
        min_keywords = max(0, int(min_keywords or 0))
        max_keywords = max(min_keywords, int(max_keywords or 0))
        manual_keyword_list = [str(keyword).strip().lower() for keyword in (manual_keywords or []) if str(keyword).strip()]
        manual_keyword_block = "\n".join(f"- {keyword}" for keyword in manual_keyword_list) or "- none"
        prompt = f"""
        You are given paper metadata and text.
        Extract only the most important keywords and a numeric importance score for each keyword.
        Do not write a summary.
        Return exactly the following format:

        Keywords: keyword1, keyword2, keyword3
        Keyword Importance: 0.9, 0.8, 0.7

        Rules:
        - Return between {min_keywords} and {max_keywords} additional keywords.
        - Do not repeat any keyword already provided by the user.
        - Use full phrases, not abbreviations (e.g., "reinforcement learning" not "RL").
        - Lowercase only.
        - Prefer established academic terms over informal ones.
        - Prefer specific over generic (e.g., "reward shaping" over "reward").
        - Keyword importance must be aligned with keyword order.

        User-provided keywords to avoid:
        {manual_keyword_block}

        ## Examples of preferred forms:
        - "RL" ??"reinforcement learning"
        - "LLMs" ??"large language models"
        - "KG" ??"knowledge graph"

        ## Format:
        Keywords: string, comma-separated
        Keyword Importance: float, comma-separated (in the same order as keywords)

        ## Text:
        {text}
        """

        # Priority 0: Gemini
        if provider == "gemini":
            try:
                gemini_response = self._call_gemini(prompt)
                logger.info(f"Gemini response: {gemini_response}")
                if gemini_response:
                    return self._filter_manual_keywords(self._parse_keyword_response(gemini_response), manual_keyword_list)
            except (ValueError, error.URLError, error.HTTPError, json.JSONDecodeError) as e:
                logger.warning("Gemini API failed, falling back to other providers: %s", e)

        # Priority 1: Requested Provider
        if provider == "openai" and settings.LLM_API_KEY:
            try:
                client = openai.OpenAI(api_key=settings.LLM_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                return self._filter_manual_keywords(self._parse_keyword_response(response.choices[0].message.content), manual_keyword_list)
            except Exception as e:
                logger.warning("OpenAI API failed, falling back to Ollama: %s", e)

        # Priority 2: Fallback to Ollama
        try:
            response = ollama.chat(
                model="llama3",
                messages=[{'role': 'user', 'content': prompt}]
            )
            return self._filter_manual_keywords(self._parse_keyword_response(response['message']['content']), manual_keyword_list)
        except Exception as e:
            logger.error("Ollama failed to generate keywords: %s", e)
            return {"keywords": [], "keyword_importance": []}

    def get_keywords_and_importance_batch(self, texts: list, provider: str = "openai", per_call_delay: float = 0.0):
        """
        Batch wrapper for `get_keywords_and_importance`.
        - `texts`: list of text inputs for keyword extraction.
        - `per_call_delay`: deprecated, kept for backward compatibility.
        Returns list of dicts, one per input.
        """
        if not texts:
            return []

        def _call(idx_text):
            idx, text = idx_text
            try:
                return self.get_keywords_and_importance(text, provider=provider)
            except Exception as e:
                logger.warning("Keyword extraction failed for batch index %s: %s", idx, e)
                return {"keywords": [], "keyword_importance": []}

        if provider == "ollama":
            max_workers = min(len(texts), 4)
        else:
            max_workers = min(len(texts), 5)

        from concurrent.futures import ThreadPoolExecutor

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            results = list(executor.map(_call, enumerate(texts)))

        return results

    def get_relationship_question(self, paper1: dict, paper2: dict, provider: str = "openai"):
        prompt = f"""
        You are a helper for creating paper relationship quizzes.
        Based on the following two papers, create one question in Korean that guides the user to define the relationship between them.
        The question should be short and clear, returning only the question text without any explanation.

        Paper A:
        Title: {paper1.get('title', '')}
        Summary: {paper1.get('summary', '')}

        Paper B:
        Title: {paper2.get('title', '')}
        Summary: {paper2.get('summary', '')}
        """

        if provider == "gemini":
            try:
                response = self._call_gemini(prompt)
                if response:
                    return {"question": self._clean_text_response(response)}
            except (ValueError, error.URLError, error.HTTPError, json.JSONDecodeError) as e:
                logger.warning("Gemini question generation failed, falling back to other providers: %s", e)

        if provider == "openai" and settings.LLM_API_KEY:
            try:
                client = openai.OpenAI(api_key=settings.LLM_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                return {"question": self._clean_text_response(response.choices[0].message.content)}
            except Exception as e:
                logger.warning("OpenAI question generation failed, falling back to Ollama: %s", e)

        try:
            response = ollama.chat(
                model="llama3",
                messages=[{'role': 'user', 'content': prompt}]
            )
            return {"question": self._clean_text_response(response['message']['content'])}
        except Exception as e:
            logger.error("Ollama question generation failed: %s", e)
            return {"question": "How would you define the relationship between these two papers?"}

    def _parse_keyword_response(self, content: str):
        lines = content.strip().split("\n")
        keywords = []
        keyword_importance = []
        for line in lines:
            if line.startswith("Keywords:"):
                keywords = [k.strip().lower() for k in line.replace("Keywords:", "").split(",") if k.strip()]
            elif line.startswith("Keyword Importance:"):
                parsed_values = []
                for value in line.replace("Keyword Importance:", "").split(","):
                    try:
                        parsed_values.append(float(value.strip()))
                    except Exception:
                        parsed_values.append(0.0)
                keyword_importance = parsed_values
        return {"keywords": keywords, "keyword_importance": keyword_importance}

    def _filter_manual_keywords(self, parsed: dict, manual_keywords: list[str]):
        keywords = parsed.get("keywords") or []
        keyword_importance = parsed.get("keyword_importance") or []
        manual_set = {keyword.lower() for keyword in manual_keywords if keyword}
        filtered_keywords = []
        filtered_importance = []

        for index, keyword in enumerate(keywords):
            normalized = str(keyword).strip().lower()
            if not normalized or normalized in manual_set:
                continue
            if normalized in {existing.lower() for existing in filtered_keywords}:
                continue
            filtered_keywords.append(normalized)
            importance = keyword_importance[index] if index < len(keyword_importance) else 0.0
            try:
                filtered_importance.append(float(importance))
            except Exception:
                filtered_importance.append(0.0)

        return {"keywords": filtered_keywords, "keyword_importance": filtered_importance}

    def get_embedding(self, text: str):
        return self.embedding_model.encode(text).tolist()

    def get_embedding_batch(self, texts: list):
        """
        Batch embedding using the sentence-transformers model which supports list input.
        Returns list of embeddings (lists).
        """
        try:
            embs = self.embedding_model.encode(texts)
            # ensure python lists
            return [e.tolist() if hasattr(e, 'tolist') else list(e) for e in embs]
        except Exception:
            # fallback to per-item
            out = []
            for t in texts:
                try:
                    out.append(self.get_embedding(t))
                except Exception:
                    out.append(None)
            return out

    def select_top_candidates(self, candidates: list, top_k: int = 10, provider: str = "openai"):
        """
        Ask an LLM to select the most relevant candidates from a provided list.
        `candidates` should be a list of dicts with at least `paper_id` and `title` keys,
        and may include `year`, `authors`, and `keywords`.
        Returns a list of selected `paper_id`s in ranked order (<= top_k).
        """
        if not candidates:
            return []

        # Build a concise prompt that lists candidates with indices
        lines = ["You are given a target paper and a list of candidate papers.\n"
                 "Select the most relevant candidate papers and return a JSON list of their paper_id values in ranked order."]
        for i, c in enumerate(candidates, start=1):
            authors = ", ".join(c.get("authors") or [])
            keywords = ", ".join(c.get("keywords") or [])
            lines.append(f"{i}. paper_id: {c.get('paper_id')} | title: {c.get('title')} | year: {c.get('year')} | authors: {authors} | keywords: {keywords}")

        lines.append(f"Return at most {top_k} paper_id values as a JSON array, e.g. [\"id1\", \"id2\"]. Do not add any explanation.")
        prompt = "\n".join(lines)

        # Try Gemini first if requested
        if provider == "gemini":
            try:
                response = self._call_gemini(prompt)
                text = self._clean_text_response(response)
                try:
                    return json.loads(text)
                except Exception:
                    # Fallback simple parse
                    return [t.strip().strip('\"') for t in text.replace('[', '').replace(']', '').split(',') if t.strip()][:top_k]
            except Exception:
                pass

        # OpenAI
        if provider == "openai" and settings.LLM_API_KEY:
            try:
                client = openai.OpenAI(api_key=settings.LLM_API_KEY)
                response = client.chat.completions.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                text = self._clean_text_response(response.choices[0].message.content)
                try:
                    return json.loads(text)
                except Exception:
                    return [t.strip().strip('\"') for t in text.replace('[', '').replace(']', '').split(',') if t.strip()][:top_k]
            except Exception:
                logger.warning("OpenAI select_top_candidates failed, falling back to Ollama")

        # Ollama fallback
        try:
            response = ollama.chat(
                model="llama3",
                messages=[{'role': 'user', 'content': prompt}]
            )
            text = self._clean_text_response(response['message']['content'])
            try:
                return json.loads(text)
            except Exception:
                return [t.strip().strip('\"') for t in text.replace('[', '').replace(']', '').split(',') if t.strip()][:top_k]
        except Exception as e:
            logger.error("select_top_candidates failed: %s", e)
            # Fallback deterministic selection: take first top_k
            return [c.get('paper_id') for c in candidates[:top_k]]
ai_service = AIService()
