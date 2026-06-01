from ..core.database import neo4j_client
import random
import uuid
import logging
import traceback
import math
import json
import numpy as np
from typing import Optional
from ..core.vector_db import chroma_client
from .ai_service import ai_service
from ..core.config import settings
from .semantic_scholar_service import semantic_scholar_service
from datetime import datetime

logger = logging.getLogger(__name__)

class KnowledgeBaseService:
    # session-scoped cache for generated relationship questions
    _question_cache = {}


    # Utility helpers
    @staticmethod
    def _normalize_pair_key(paper1_id: str, paper2_id: str):
        return tuple(sorted([paper1_id, paper2_id]))

    @staticmethod
    def _normalize_keywords(values):
        # Used for Jaccard similarity - normalize to lowercase and strip whitespace, return as a sorted list
        return sorted({str(item).strip().lower() for item in (values or []) if str(item).strip()})

    @staticmethod
    def _normalize_category_values(values):
        if not values:
            return []
        if isinstance(values, str):
            raw_values = [item.strip() for item in values.split(",")]
        else:
            raw_values = [str(item).strip() for item in values]

        normalized = []
        seen = set()
        for value in raw_values:
            if not value:
                continue
            lowered = value.lower()
            if lowered in seen:
                continue
            normalized.append(value)
            seen.add(lowered)
        return normalized

    @staticmethod
    def _normalize_manual_keyword_inputs(keywords, importance):
        keyword_values = []
        importance_values = []
        structured_importance_values = []

        if isinstance(keywords, str):
            keyword_values = [item.strip() for item in keywords.split(",") if item.strip()]
        elif isinstance(keywords, list):
            for item in keywords:
                if isinstance(item, dict):
                    keyword = str(item.get("keyword") or item.get("value") or "").strip()
                    if not keyword:
                        continue
                    keyword_values.append(keyword)
                    try:
                        structured_importance_values.append(float(item.get("importance", 1.0)))
                    except Exception:
                        structured_importance_values.append(1.0)
                else:
                    keyword = str(item).strip()
                    if keyword:
                        keyword_values.append(keyword)

        if isinstance(importance, str):
            try:
                parsed_importance = json.loads(importance)
                if isinstance(parsed_importance, list):
                    importance = parsed_importance
            except Exception:
                importance = [item.strip() for item in importance.split(",")]

        if isinstance(importance, list):
            for item in importance:
                try:
                    importance_values.append(float(item))
                except Exception:
                    importance_values.append(1.0)

        if not importance_values and structured_importance_values:
            importance_values = structured_importance_values

        while len(importance_values) < len(keyword_values):
            importance_values.append(1.0)

        return keyword_values[:5], importance_values[:5]

    @staticmethod
    def _merge_keyword_lists(manual_keywords, manual_importance, ai_keywords, ai_importance):
        merged_keywords = []
        merged_importance = []
        seen = set()

        def add_keyword(keyword, importance):
            normalized = str(keyword).strip().lower()
            if not normalized or normalized in seen:
                return
            seen.add(normalized)
            merged_keywords.append(normalized)
            try:
                merged_importance.append(float(importance))
            except Exception:
                merged_importance.append(0.0)

        manual_importance = manual_importance or []
        ai_importance = ai_importance or []

        for index, keyword in enumerate(manual_keywords or []):
            add_keyword(keyword, manual_importance[index] if index < len(manual_importance) else 1.0)

        for index, keyword in enumerate(ai_keywords or []):
            add_keyword(keyword, ai_importance[index] if index < len(ai_importance) else 0.0)

        return merged_keywords, merged_importance

    @staticmethod
    def _get_user_categories(user_id: str):
        with neo4j_client.get_session() as session:
            result = session.run(
                """
                MATCH (p:Paper {userId: $user_id})
                UNWIND coalesce(p.categories, []) AS category
                WITH trim(category) AS category
                WHERE category <> ''
                RETURN DISTINCT category AS category
                ORDER BY toLower(category)
                """,
                user_id=user_id,
            )
            return [record["category"] for record in result]


    # User preference helpers
    @staticmethod
    def _get_user_provider(user_id: str):
        provider = "openai"
        with neo4j_client.get_session() as session:
            result = session.run(
                "MATCH (u:User) WHERE elementId(u) = $user_id RETURN u.ai_provider as provider",
                user_id=user_id,
            )
            record = result.single()
            if record and record["provider"]:
                provider = record["provider"]
        return provider

    @staticmethod
    def _get_user_quiz_frequency(user_id: str):
        quiz_frequency = 3
        with neo4j_client.get_session() as session:
            result = session.run(
                "MATCH (u:User) WHERE elementId(u) = $user_id RETURN u.quiz_frequency as quiz_frequency",
                user_id=user_id,
            )
            record = result.single()
            if record and record["quiz_frequency"]:
                quiz_frequency = int(record["quiz_frequency"])
        return max(1, quiz_frequency)

    @staticmethod
    def _get_user_edge_threshold(user_id: str):
        edge_threshold = 0.35
        with neo4j_client.get_session() as session:
            result = session.run(
                "MATCH (u:User) WHERE elementId(u) = $user_id RETURN u.ai_edge_threshold as ai_edge_threshold",
                user_id=user_id,
            )
            record = result.single()
            if record and record["ai_edge_threshold"] is not None:
                try:
                    edge_threshold = float(record["ai_edge_threshold"])
                except Exception:
                    edge_threshold = 0.35
        return max(0.0, min(1.0, edge_threshold))


    # Neo4j paper fetchers
    @staticmethod
    def _get_latest_paper(user_id: str):
        with neo4j_client.get_session() as session:
            result = session.run(
                """
                MATCH (p:Paper {userId: $user_id})
                RETURN p
                ORDER BY p.createdAt DESC
                LIMIT 1
                """,
                user_id=user_id,
            )
            record = result.single()
            if not record:
                return None
            paper = record["p"]
            return {
                "id": paper["id"],
                "title": paper["title"],
                "summary": paper.get("summary", ""),
                "keywords": paper.get("keywords", []),
                "keyword_importance": paper.get("keyword_importance", []),
            }

    @staticmethod
    def _get_paper_by_id(user_id: str, paper_id: str):
        with neo4j_client.get_session() as session:
            # Allow lookup by either stable property id or Neo4j elementId
            result = session.run(
                """
                MATCH (p:Paper)
                WHERE (p.id = $paper_id OR elementId(p) = $paper_id) AND p.userId = $user_id
                RETURN p
                LIMIT 1
                """,
                paper_id=paper_id,
                user_id=user_id,
            )
            record = result.single()
            if not record:
                return None
            paper = record["p"]
            return {
                "id": paper["id"],
                "title": paper["title"],
                "summary": paper.get("summary", ""),
                "keywords": paper.get("keywords", []),
                "keyword_importance": paper.get("keyword_importance", []),
            }

    @staticmethod
    def _get_all_papers(user_id: str, category: str | None = None):
        with neo4j_client.get_session() as session:
            params = {"user_id": user_id}
            category_clause = ""
            if category:
                params["category"] = category
                category_clause = " AND any(cat IN coalesce(p.categories, []) WHERE toLower(cat) = toLower($category))"
            result = session.run(
                """
                MATCH (p:Paper {userId: $user_id})
                WHERE true
                """ + category_clause + """
                RETURN p
                ORDER BY p.createdAt DESC
                """,
                **params,
            )
            papers = []
            for record in result:
                paper = record["p"]
                papers.append({
                    "element_id": paper.element_id,
                    "id": paper["id"],
                    "title": paper["title"],
                    "summary": paper.get("summary", ""),
                    "keywords": paper.get("keywords", []),
                    "keyword_importance": paper.get("keyword_importance", []),
                    "categories": paper.get("categories", []),
                })
            return papers


    # ChromaDB embedding store
    @staticmethod
    def _get_all_embeddings(user_id: str, category: str | None = None) -> dict:
        try:
            collection = chroma_client.get_collection(user_id)
            results = collection.get(
                where={"userId": user_id},
                include=["embeddings", "metadatas"],
            )
        except Exception as e:
            logger.warning("Failed to fetch embeddings from ChromaDB: %s", e)
            return {}

        store = {}
        ids = results.get("ids", [])
        embeddings = results.get("embeddings", [])
        metadatas = results.get("metadatas", [])

        for i, paper_id in enumerate(ids):
            emb = embeddings[i] if i < len(embeddings) else None
            meta = metadatas[i] if i < len(metadatas) else {}

            try:
                keywords = json.loads(meta.get("keywords", "[]"))
            except Exception:
                keywords = []
            try:
                keyword_importance = json.loads(meta.get("keyword_importance", "[]"))
            except Exception:
                keyword_importance = []

            try:
                categories = json.loads(meta.get("categories", "[]"))
            except Exception:
                categories = []

            if category:
                category_lower = str(category).strip().lower()
                if category_lower not in {str(item).strip().lower() for item in categories}:
                    continue

            store[paper_id] = {
                "embedding": emb,
                "keywords": keywords,
                "keyword_importance": keyword_importance,
                "categories": categories,
            }
        return store

    @staticmethod
    def _resolve_embedding_data(user_id: str, paper_id: str, embedding_store: dict) -> dict | None:
        data = embedding_store.get(paper_id)
        if data:
            return data
        paper = KnowledgeBaseService._get_paper_by_id(user_id, paper_id)
        if paper:
            data = embedding_store.get(paper["id"])
        return data

    # Hybrid similarity
    @staticmethod
    def _cosine_similarity_np(vec1: list, vec2: list) -> float:
        """Cosine similarity using numpy for better performance, with fallback to manual calculation."""
        try:
            a = np.array(vec1, dtype=np.float32)
            b = np.array(vec2, dtype=np.float32)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return float(np.dot(a, b) / (norm_a * norm_b))
        except Exception:
            dot = sum(float(x) * float(y) for x, y in zip(vec1, vec2))
            n1 = math.sqrt(sum(float(x) ** 2 for x in vec1))
            n2 = math.sqrt(sum(float(x) ** 2 for x in vec2))
            if n1 == 0 or n2 == 0:
                return 0.0
            return dot / (n1 * n2)

    @staticmethod
    def _compute_weighted_keyword_score(kw1_dict: dict, kw2_dict: dict) -> float:
        total = sum(kw1_dict.values()) + sum(kw2_dict.values())
        if not total:
            return 0.0
        common_keys = set(kw1_dict.keys()) & set(kw2_dict.keys())
        return sum(kw1_dict[k] + kw2_dict[k] for k in common_keys) / total

    @staticmethod
    def _compute_hybrid_score(
        embedding1: list,
        keywords1: list,
        keyword_importance1: list,
        embedding2: list,
        keywords2: list,
        keyword_importance2: list,
    ) -> dict:
        """
        Compute a hybrid similarity score between two papers based on both vector embeddings and keyword importance.
         - Vector similarity is weighted at 60%
         - Keyword importance similarity is weighted at 40%
         - Final score is normalized to [0,1]
         - Returns a breakdown of vector score, keyword score, and final combined score
        """
        vector_score = max(0.0, KnowledgeBaseService._cosine_similarity_np(embedding1, embedding2))

        # Use lowercase letters only for keyword matching
        lower_keywords1 = [k.lower() for k in keywords1]
        lower_keywords2 = [k.lower() for k in keywords2]

        kw1_dict = dict(zip(lower_keywords1, keyword_importance1))
        kw2_dict = dict(zip(lower_keywords2, keyword_importance2))
        keyword_score = KnowledgeBaseService._compute_weighted_keyword_score(kw1_dict, kw2_dict)

        score = max(0.0, min(1.0, (vector_score * 0.6) + (keyword_score * 0.4)))
        return {
            "vector_score": round(vector_score, 4),
            "keyword_score": round(keyword_score, 4),
            "score": round(score, 4),
        }

    @staticmethod
    def _compute_similarity_batch(
        target_embedding: list,
        target_keywords: list,
        target_keyword_importance: list,
        embedding_store: dict,
        exclude_ids: Optional[set] = None,
    ) -> dict:
        """
        Compute similarity scores for a batch of papers against a target embedding and keywords, excluding certain paper IDs.
        Return: {paper_id: {"vector_score", "keyword_score", "score"}}
        """
        exclude_ids = exclude_ids or set()
        results = {}
        for paper_id, data in embedding_store.items():
            if paper_id in exclude_ids:
                continue
            emb = data.get("embedding")
            if emb is None:
                continue
            results[paper_id] = KnowledgeBaseService._compute_hybrid_score(
                target_embedding,
                target_keywords,
                target_keyword_importance,
                emb,
                data.get("keywords", []),
                data.get("keyword_importance", []),
            )
        return results


    # Confirmed pair helpers
    @staticmethod
    def _get_confirmed_pair_keys(user_id: str):
        confirmed_pairs = set()
        with neo4j_client.get_session() as session:
            result = session.run(
                """
                MATCH (p1:Paper {userId: $user_id})-[r:SHADOW_LINK]->(p2:Paper {userId: $user_id})
                WHERE coalesce(r.status, '') = 'confirmed' OR r.description IS NOT NULL
                RETURN p1.id as paper1_id, p2.id as paper2_id
                """,
                user_id=user_id,
            )
            for record in result:
                p1 = record["paper1_id"]
                p2 = record["paper2_id"]
                if p1 and p2:
                    confirmed_pairs.add(KnowledgeBaseService._normalize_pair_key(p1, p2))
        return confirmed_pairs


    # Core public methods
    @staticmethod
    def add_paper(user_id: str, title: str, text: Optional[str] = None, categories=None, manual_keywords=None, manual_keyword_importance=None):
        try:
            # 0. User provider
            provider = "openai"
            with neo4j_client.get_session() as session:
                res = session.run(
                    "MATCH (u) WHERE elementId(u) = $user_id RETURN u.ai_provider as p",
                    user_id=user_id,
                )
                record = res.single()
                if record:
                    provider = record["p"]

            # 1. Semantic Scholar metadata + LLM keyword extraction
            resolved = semantic_scholar_service.resolve_paper(title)
            paper_record = resolved.get("record") or {}

            summary_source = (
                paper_record.get("abstract")
                or paper_record.get("tldr")
                or (text or "")
                or title
            )

            keyword_input = "\n\n".join([
                f"Title: {paper_record.get('title') or title}",
                f"Abstract: {paper_record.get('abstract') or ''}",
                f"TLDR: {paper_record.get('tldr') or ''}",
                f"User Text: {text or ''}",
            ])
            category_values = KnowledgeBaseService._normalize_category_values(categories)
            manual_keyword_values, manual_importance_values = KnowledgeBaseService._normalize_manual_keyword_inputs(
                manual_keywords,
                manual_keyword_importance,
            )
            ai_data = ai_service.get_keywords_and_importance(
                keyword_input,
                provider=provider,
                min_keywords=max(0, 3 - len(manual_keyword_values)),
                max_keywords=max(1, 7 - len(manual_keyword_values)),
                manual_keywords=manual_keyword_values,
            )
            ai_keywords = ai_data.get("keywords") or []
            ai_keyword_importance = ai_data.get("keyword_importance") or []
            keywords, keyword_importance = KnowledgeBaseService._merge_keyword_lists(
                manual_keyword_values,
                manual_importance_values,
                ai_keywords,
                ai_keyword_importance,
            )
            external_ids_value = paper_record.get("external_ids")
            if isinstance(external_ids_value, (dict, list)):
                try:
                    external_ids_value = json.dumps(external_ids_value)
                except Exception:
                    external_ids_value = str(external_ids_value)

            embedding = ai_service.get_embedding(summary_source)

            # 2. Save to Neo4j
            new_paper_id = str(uuid.uuid4())
            with neo4j_client.get_session() as session:
                session.run(
                    """
                    MATCH (u:User)
                    WHERE elementId(u) = $user_id
                    CREATE (p:Paper {
                        id: $id,
                        title: $title,
                        summary: $summary,
                        keywords: $keywords,
                        keyword_importance: $keyword_importance,
                        categories: $categories,
                        ssPaperId: $ss_paper_id,
                        doi: $doi,
                        year: $year,
                        authors: $authors,
                        citationCount: $citation_count,
                        tldr: $tldr,
                        abstract: $abstract,
                        externalIds: $external_ids,
                        semanticScholarUrl: $semantic_scholar_url,
                        userId: $user_id,
                        createdAt: datetime()
                    })
                    CREATE (u)-[:OWNS]->(p)
                    """,
                    user_id=user_id,
                    title=paper_record.get("title") or title,
                    summary=summary_source,
                    keywords=keywords,
                    keyword_importance=keyword_importance,
                    categories=category_values,
                    ss_paper_id=paper_record.get("ss_paper_id"),
                    doi=paper_record.get("doi"),
                    year=paper_record.get("year"),
                    authors=paper_record.get("authors"),
                    citation_count=paper_record.get("citation_count"),
                    tldr=paper_record.get("tldr"),
                    abstract=paper_record.get("abstract"),
                    external_ids=external_ids_value,
                    semantic_scholar_url=paper_record.get("url"),
                    id=new_paper_id,
                )
                if paper_record.get("ss_paper_id"):
                    KnowledgeBaseService._store_related_semantic_scholar_papers(
                        session=session,
                        source_user_id=user_id,
                        source_paper_id=new_paper_id,
                        source_ss_paper_id=paper_record.get("ss_paper_id"),
                        references=paper_record.get("references") or [],
                        citations=paper_record.get("citations") or [],
                    )
                count_result = session.run(
                    "MATCH (u:User)-[:OWNS]->(p:Paper) WHERE elementId(u) = $user_id RETURN count(p) as count",
                    user_id=user_id,
                )
                paper_count = count_result.single()["count"]

            # 3. Save to ChromaDB (embedding + metadata)
            collection = chroma_client.get_collection(user_id)
            raw_metadata = {
                "title": paper_record.get("title") or title,
                "userId": user_id,
                "paperId": new_paper_id,
                "keywords": json.dumps(keywords),
                "keyword_importance": json.dumps(keyword_importance),
                "categories": json.dumps(category_values),
                "ssPaperId": paper_record.get("ss_paper_id"),
                "doi": paper_record.get("doi"),
                "year": paper_record.get("year"),
            }

            chroma_metadata = {}
            for key, value in raw_metadata.items():
                if value is None:
                    continue
                if isinstance(value, (str, int, float, bool)):
                    chroma_metadata[key] = value
                elif isinstance(value, (dict, list)):
                    chroma_metadata[key] = json.dumps(value)
                else:
                    chroma_metadata[key] = str(value)

            collection.add(
                embeddings=[embedding],
                documents=[summary_source],
                metadatas=[chroma_metadata],
                ids=[new_paper_id],
            )

            if category_values:
                with neo4j_client.get_session() as session:
                    for category in category_values:
                        session.run(
                            """
                            MATCH (p:Paper {id: $paper_id, userId: $user_id})
                            MERGE (c:Category {userId: $user_id, name: toLower($category)})
                            SET c.displayName = $category,
                                c.updatedAt = datetime()
                            MERGE (p)-[:IN_CATEGORY]->(c)
                            """,
                            user_id=user_id,
                            paper_id=new_paper_id,
                            category=category,
                        )

            # 4. If count >= min_paper_threshold, trigger shadow link creation
            if paper_count >= settings.MIN_PAPER_COUNT:
                KnowledgeBaseService.create_shadow_links(
                    user_id,
                    embedding,
                    keywords,
                    keyword_importance,
                    new_paper_id,
                )

            return {
                "status": "success",
                "paper_count": paper_count,
                "active": paper_count >= settings.MIN_PAPER_COUNT,
            }
        except Exception as e:
            logger.error("Exception in add_paper: %s", e)
            logger.debug(traceback.format_exc())
            raise

    @staticmethod
    def create_shadow_links(
        user_id: str,
        new_embedding: list,
        new_keywords: list,
        new_keyword_importance: list,
        new_paper_id: str,
    ):
        """
        Fetch all existing embeddings and metadata from ChromaDB for the user.
        Compute hybrid similarity scores in batch, excluding the new paper itself, and create SHADOW_LINK that exceed the user's edge threshold.
        No use of ChromaDB distance, only the custom hybrid score.
        """
        embedding_store = KnowledgeBaseService._get_all_embeddings(user_id)
        scores = KnowledgeBaseService._compute_similarity_batch(
            new_embedding,
            new_keywords,
            new_keyword_importance,
            embedding_store,
            exclude_ids={new_paper_id},
        )

        edge_threshold = KnowledgeBaseService._get_user_edge_threshold(user_id)
        with neo4j_client.get_session() as session:
            for target_paper_id, sim in scores.items():
                if sim["score"] < edge_threshold:
                    continue
                session.run(
                    """
                    MATCH (p1:Paper {id: $paper1_id, userId: $user_id})
                    MATCH (p2:Paper {id: $paper2_id, userId: $user_id})
                    MERGE (p1)-[r:SHADOW_LINK]->(p2)
                    ON CREATE SET r.score = $score,
                                  r.vector_score = $vector_score,
                                  r.keyword_score = $keyword_score,
                                  r.status = 'pending',
                                  r.createdAt = datetime()
                    """,
                    paper1_id=new_paper_id,
                    paper2_id=target_paper_id,
                    user_id=user_id,
                    score=sim["score"],
                    vector_score=sim["vector_score"],
                    keyword_score=sim["keyword_score"],
                )

    @staticmethod
    def _store_related_semantic_scholar_papers(
        session,
        source_user_id: str,
        source_paper_id: str,
        source_ss_paper_id: Optional[str],
        references: list,
        citations: list,
    ):
        def _normalize_related_item(item: dict) -> dict:
            authors = []
            for author in item.get("authors") or []:
                if isinstance(author, dict):
                    name = author.get("name")
                else:
                    name = str(author)
                if name:
                    authors.append(str(name).strip())
            return {
                "paper_id": item.get("paperId"),
                "title": item.get("title"),
                "year": item.get("year"),
                "authors": authors,
            }

        related_rows = []
        for item in references:
            normalized = _normalize_related_item(item)
            normalized["rel_type"] = "HAS_REFERENCE"
            related_rows.append(normalized)

        for item in citations:
            normalized = _normalize_related_item(item)
            normalized["rel_type"] = "HAS_CITATION"
            related_rows.append(normalized)

        for related in related_rows:
            related_paper_id = related.get("paper_id")
            if not related_paper_id:
                continue
            session.run(
                """
                MATCH (u:User) WHERE elementId(u) = $user_id
                MATCH (p:Paper {id: $source_paper_id, userId: $user_id})
                MERGE (r:SemanticScholarPaper {paperId: $paper_id})
                SET r.title = $title,
                    r.year = $year,
                    r.authors = $authors,
                    r.updatedAt = datetime()
                MERGE (p)-[rel:%s]->(r)
                SET rel.sourcePaperId = $source_paper_id,
                    rel.sourceSsPaperId = $source_ss_paper_id,
                    rel.updatedAt = datetime()
                """ % related["rel_type"],
                user_id=source_user_id,
                source_paper_id=source_paper_id,
                source_ss_paper_id=source_ss_paper_id,
                paper_id=related_paper_id,
                title=related.get("title"),
                year=related.get("year"),
                authors=related.get("authors"),
            )

    @staticmethod
    def get_quiz_candidates(user_id: str):
        latest_paper = KnowledgeBaseService._get_latest_paper(user_id)
        if not latest_paper:
            return {"anchor": None, "items": []}

        paper_count = 0
        with neo4j_client.get_session() as session:
            result = session.run(
                "MATCH (p:Paper {userId: $user_id}) RETURN count(p) as count",
                user_id=user_id,
            )
            record = result.single()
            if record:
                paper_count = record["count"]

        if paper_count < settings.MIN_PAPER_COUNT:
            return {"anchor": latest_paper, "items": []}

        paper_lookup = {p["id"]: p for p in KnowledgeBaseService._get_all_papers(user_id)}
        confirmed_pairs = KnowledgeBaseService._get_confirmed_pair_keys(user_id)

        embedding_store = KnowledgeBaseService._get_all_embeddings(user_id)

        def _build_candidate(p1_id: str, p2_id: str):
            pair_key = KnowledgeBaseService._normalize_pair_key(p1_id, p2_id)
            if pair_key in confirmed_pairs:
                return None

            paper1 = paper_lookup.get(p1_id)
            paper2 = paper_lookup.get(p2_id)
            if not paper1 or not paper2:
                return None

            categories1 = {str(item).strip().lower() for item in (paper1.get("categories") or []) if str(item).strip()}
            categories2 = {str(item).strip().lower() for item in (paper2.get("categories") or []) if str(item).strip()}
            if not categories1 or not categories2 or not (categories1 & categories2):
                return None

            data1 = embedding_store.get(paper1["id"])
            data2 = embedding_store.get(paper2["id"])
            if not data1 or not data2 or data1.get("embedding") is None or data2.get("embedding") is None:
                return None

            similarity = KnowledgeBaseService._compute_hybrid_score(
                data1["embedding"], data1["keywords"], data1["keyword_importance"],
                data2["embedding"], data2["keywords"], data2["keyword_importance"],
            )
            return {
                "paper1_id": paper1["id"],
                "paper1_title": paper1["title"],
                "paper1_summary": paper1.get("summary", ""),
                "paper1_keywords": paper1.get("keywords", []),
                "paper1_keyword_importance": paper1.get("keyword_importance", []),
                "paper2_id": paper2["id"],
                "paper2_title": paper2["title"],
                "paper2_summary": paper2.get("summary", ""),
                "paper2_keywords": paper2.get("keywords", []),
                "paper2_keyword_importance": paper2.get("keyword_importance", []),
                "paper1_categories": paper1.get("categories", []),
                "paper2_categories": paper2.get("categories", []),
                "score": similarity["score"],
                "vector_score": similarity["vector_score"],
                "keyword_score": similarity["keyword_score"],
            }

        candidate_pool = []
        paper_ids = [paper["id"] for paper in paper_lookup.values()]
        for index, paper1_id in enumerate(paper_ids):
            for paper2_id in paper_ids[index + 1:]:
                candidate = _build_candidate(paper1_id, paper2_id)
                if candidate:
                    candidate_pool.append(candidate)

        if not candidate_pool:
            return {"anchor": latest_paper, "items": []}

        candidate_pool.sort(key=lambda item: item["score"], reverse=True)

        anchor_candidates = [
            item for item in candidate_pool
            if latest_paper["id"] in (item["paper1_id"], item["paper2_id"])
        ]
        anchor_pool = anchor_candidates[:3] if len(anchor_candidates) >= 3 else anchor_candidates
        if not anchor_pool:
            anchor_pool = candidate_pool[:3]
        first_item = random.choice(anchor_pool)

        remaining_candidates = [
            item for item in candidate_pool
            if KnowledgeBaseService._normalize_pair_key(item["paper1_id"], item["paper2_id"])
            != KnowledgeBaseService._normalize_pair_key(first_item["paper1_id"], first_item["paper2_id"])
        ]

        quiz_frequency = KnowledgeBaseService._get_user_quiz_frequency(user_id)
        selected_items = [dict(first_item, selection_source="anchor_random_top3")]

        remaining_slots = max(quiz_frequency - 1, 0)
        top_pool_size = min(len(remaining_candidates), max(2 * remaining_slots, 0))
        top_pool = remaining_candidates[:top_pool_size]
        if remaining_slots and top_pool:
            random_count = min(remaining_slots, len(top_pool))
            sampled = random.sample(top_pool, k=random_count)
            selected_pairs = {
                KnowledgeBaseService._normalize_pair_key(item["paper1_id"], item["paper2_id"])
                for item in selected_items
            }
            for item in sampled:
                pair_key = KnowledgeBaseService._normalize_pair_key(item["paper1_id"], item["paper2_id"])
                if pair_key in selected_pairs:
                    continue
                selected_items.append(dict(item, selection_source="random_top2n"))
                selected_pairs.add(pair_key)

        if len(selected_items) < quiz_frequency:
            selected_pairs = {
                KnowledgeBaseService._normalize_pair_key(item["paper1_id"], item["paper2_id"])
                for item in selected_items
            }
            for item in remaining_candidates:
                pair_key = KnowledgeBaseService._normalize_pair_key(item["paper1_id"], item["paper2_id"])
                if pair_key in selected_pairs:
                    continue
                selected_items.append(dict(item, selection_source="ranked"))
                selected_pairs.add(pair_key)
                if len(selected_items) >= quiz_frequency:
                    break

        selected_items = selected_items[:quiz_frequency]
        for index, item in enumerate(selected_items, start=1):
            item["rank"] = str(index)

        cooldown_slots = []
        with neo4j_client.get_session() as session:
            cd_res = session.run(
                """
                MATCH (u:User)-[:HAS_COOLDOWN]->(s:QuizCooldown)
                WHERE elementId(u) = $user_id AND s.expiresAt > datetime()
                RETURN
                    toString(s.expiresAt) as expiresAt,
                    s.id as id,
                    s.paper1_id as paper1_id,
                    s.paper2_id as paper2_id
                ORDER BY s.expiresAt ASC
                """,
                user_id=user_id,
            )
            for rec in cd_res:
                cooldown_slots.append({
                    "status": "cooldown",
                    "id": rec["id"],
                    "expiresAt": rec["expiresAt"],
                    "paper1_id": rec["paper1_id"],
                    "paper2_id": rec["paper2_id"],
                })

        active_slots = max(quiz_frequency - len(cooldown_slots), 0)
        active_items = selected_items[:active_slots]
        for item in active_items:
            item["status"] = "active"

        slots = cooldown_slots + active_items
        while len(slots) < quiz_frequency:
            slots.append({"status": "empty"})

        return {"anchor": latest_paper, "items": slots, "quiz_frequency": quiz_frequency}

    @staticmethod
    def get_relationship_question(user_id: str, paper1_id: str, paper2_id: str):
        provider = KnowledgeBaseService._get_user_provider(user_id)
        paper1 = KnowledgeBaseService._get_paper_by_id(user_id, paper1_id)
        paper2 = KnowledgeBaseService._get_paper_by_id(user_id, paper2_id)

        if not paper1 or not paper2:
            raise ValueError("Paper pair not found")

        # session cache key per user
        pair_key = KnowledgeBaseService._normalize_pair_key(paper1_id, paper2_id)
        user_cache = KnowledgeBaseService._question_cache.setdefault(user_id, {})
        if pair_key in user_cache:
            return {"question": user_cache[pair_key], "cached": True}

        res = ai_service.get_relationship_question(paper1, paper2, provider=provider)
        question = res.get("question") if isinstance(res, dict) else res
        if question:
            try:
                user_cache[pair_key] = question
            except Exception:
                pass
        return {"question": question}

    @staticmethod
    def get_pair_similarity(user_id: str, paper1_id: str, paper2_id: str):
        embedding_store = KnowledgeBaseService._get_all_embeddings(user_id)

        # directly resolve from embedding store using paper_id as key, if not found then fallback to Neo4j lookup
        data1 = KnowledgeBaseService._resolve_embedding_data(user_id, paper1_id, embedding_store)
        data2 = KnowledgeBaseService._resolve_embedding_data(user_id, paper2_id, embedding_store)

        if not data1 or not data2:
            raise ValueError("Paper embeddings not found")

        similarity = KnowledgeBaseService._compute_hybrid_score(
            data1["embedding"], data1["keywords"], data1["keyword_importance"],
            data2["embedding"], data2["keywords"], data2["keyword_importance"],
        )
        return {"paper1_id": paper1_id, "paper2_id": paper2_id, **similarity}

    @staticmethod
    def get_graph_data(user_id: str, category: str | None = None):
        nodes = []
        links = []
        edge_threshold = KnowledgeBaseService._get_user_edge_threshold(user_id)
        category_filter = str(category).strip().lower() if category else None

        with neo4j_client.get_session() as session:
            result = session.run(
                """
                MATCH (n:Paper {userId: $user_id})
                WHERE $category IS NULL OR any(cat IN coalesce(n.categories, []) WHERE toLower(cat) = $category)
                OPTIONAL MATCH (n)-[r:RELATED_TO|SHADOW_LINK]->(m:Paper {userId: $user_id})
                WHERE $category IS NULL OR any(cat IN coalesce(m.categories, []) WHERE toLower(cat) = $category)
                RETURN n, r, m
                """,
                user_id=user_id,
                category=category_filter,
            )
            node_ids = set()
            existing_pairs = set()
            for record in result:
                n = record["n"]
                # prefer stable property id (UUID) if present, fallback to element id
                n_prop_id = n.get("id") if "id" in n else n.element_id
                if n_prop_id not in node_ids:
                    nodes.append({
                        "id": n_prop_id,
                        "title": n["title"],
                        "summary": n.get("summary", ""),
                        "keywords": n.get("keywords", []),
                        "categories": n.get("categories", []),
                    })
                    node_ids.add(n_prop_id)

                m = record.get("m")
                r = record.get("r")
                if m and r:
                    link_type = r.get("type", r.type)
                    link_status = r.get("status", "pending")
                    link_score = r.get("score", None)
                    m_prop_id = m.get("id") if "id" in m else m.element_id
                    pair_key = KnowledgeBaseService._normalize_pair_key(n_prop_id, m_prop_id)
                    existing_pairs.add(pair_key)
                    if link_type == "SHADOW_LINK" and link_status != "confirmed":
                        try:
                            if link_score is None or float(link_score) < edge_threshold:
                                continue
                        except Exception:
                            continue
                    links.append({
                        "source": n_prop_id,
                        "target": m_prop_id,
                        "type": link_type,
                        "score": link_score,
                        "description": r.get("description", ""),
                        "status": link_status,
                    })




        # Backfill visible AI edges on the fly for pairs that have not yet been persisted.
        if len(nodes) >= settings.MIN_PAPER_COUNT:
            embedding_store = KnowledgeBaseService._get_all_embeddings(user_id, category=category_filter)
            paper_lookup = {
                p["element_id"]: p
                for p in KnowledgeBaseService._get_all_papers(user_id, category=category_filter)
                if p.get("element_id")
            }
            paper_eids = list(paper_lookup.keys())

            for i, eid1 in enumerate(paper_eids):
                pid1 = paper_lookup[eid1]["id"]
                data1 = embedding_store.get(pid1)
                if not data1 or data1.get("embedding") is None:
                    continue
                for eid2 in paper_eids[i + 1:]:
                    pid2 = paper_lookup[eid2]["id"]
                    pair_key = KnowledgeBaseService._normalize_pair_key(pid1, pid2)
                    if pair_key in existing_pairs:
                        continue
                    data2 = embedding_store.get(pid2)
                    if not data2 or data2.get("embedding") is None:
                        continue
                    similarity = KnowledgeBaseService._compute_hybrid_score(
                        data1["embedding"], data1["keywords"], data1["keyword_importance"],
                        data2["embedding"], data2["keywords"], data2["keyword_importance"],
                    )
                    if similarity["score"] < edge_threshold:
                        continue
                    existing_pairs.add(pair_key)
                    links.append({
                        "source": pid1,
                        "target": pid2,
                        "type": "SHADOW_LINK",
                        "score": similarity["score"],
                        "description": "",
                        "status": "pending",
                    })

        return {
            "nodes": nodes,
            "links": links,
            "ai_edge_threshold": edge_threshold,
            "available_categories": KnowledgeBaseService._get_user_categories(user_id),
            "selected_category": category,
        }

    @staticmethod
    def recommend_single(user_id: str, paper_id: str, prefilter_limit: int = 100, final_k: int = 5):
        """
        Recommend papers for a single anchor paper.
        See: prefilter by metadata, LLM-guided selection, hybrid scoring, persist run.
        """
        current_year = datetime.now().year

        provider = KnowledgeBaseService._get_user_provider(user_id)

        with neo4j_client.get_session() as session:
            # Load source paper
            res = session.run(
                "MATCH (p:Paper) WHERE p.userId = $user_id AND (p.id = $paper_id OR elementId(p) = $paper_id) RETURN p LIMIT 1",
                user_id=user_id, paper_id=paper_id,
            )
            rec = res.single()
            if not rec:
                raise ValueError("Source paper not found")
            src = rec["p"]
            source_keywords = src.get("keywords") or []
            source_keyword_importance = src.get("keyword_importance") or []
            source_authors = set([a.lower() for a in (src.get("authors") or [])])
            source_summary = src.get("summary") or src.get("abstract") or src.get("tldr") or src.get("title")

            # Fetch related SemanticScholarPaper nodes
            rels = session.run(
                "MATCH (p:Paper {id: $paper_id, userId: $user_id})-[:HAS_REFERENCE|HAS_CITATION]->(r:SemanticScholarPaper) RETURN r",
                paper_id=src.get("id"), user_id=user_id,
            )
            candidates = []
            for rrec in rels:
                r = rrec["r"]
                candidates.append({
                    "paper_id": r.get("paperId") or r.element_id,
                    "title": r.get("title"),
                    "year": r.get("year"),
                    "authors": r.get("authors") or [],
                })

            # Fallback: use other user Papers if no external refs
            if not candidates:
                other_res = session.run(
                    "MATCH (o:Paper {userId: $user_id}) WHERE o.id <> $paper_id RETURN o LIMIT 200",
                    user_id=user_id, paper_id=src.get("id"),
                )
                for orec in other_res:
                    o = orec["o"]
                    candidates.append({
                        "paper_id": o.get("id") or o.element_id,
                        "title": o.get("title"),
                        "year": o.get("year"),
                        "authors": o.get("authors") or [],
                        "keywords": o.get("keywords") or [],
                    })

        # Prefilter using simple heuristics
        candidates = sorted(candidates, key=lambda c: KnowledgeBaseService._prefilter_score_for(c, source_keywords, source_authors, current_year), reverse=True)
        prefiltered = candidates[:max(50, min(prefilter_limit, len(candidates)))]

        # Ask LLM to pick top final_k candidates
        selected_ids = ai_service.select_top_candidates(prefiltered, top_k=final_k, provider=provider)

        # Build final detailed candidate list using batched operations:
        embedding_store = KnowledgeBaseService._get_all_embeddings(user_id)

        # Ensure source embedding (avoid treating numpy arrays as booleans)
        source_embedding = None
        src_data = embedding_store.get(src.get("id"))
        if src_data and src_data.get("embedding") is not None:
            source_embedding = src_data.get("embedding")
        else:
            source_embedding = ai_service.get_embedding(source_summary or src.get("title") or "")

        # Collect candidate metadata for selected ids in order
        selected_candidates = []
        for sid in selected_ids:
            cand_meta = next((c for c in prefiltered if str(c.get("paper_id")) == str(sid)), None)
            if not cand_meta:
                cand_meta = next((c for c in candidates if str(c.get("paper_id")) == str(sid)), None)
            if cand_meta:
                selected_candidates.append(cand_meta)

        # 1) Batch-resolve Semantic Scholar records (if batch API exists, use it)
        resolved_records = {}
        titles = [c.get("title") or "" for c in selected_candidates]
        try:
            if hasattr(semantic_scholar_service, "resolve_papers"):
                batch_res = semantic_scholar_service.resolve_papers(titles)
                # expect list/dict mapping
                for idx, rec in enumerate(batch_res or []):
                    resolved_records[idx] = rec.get("record") if isinstance(rec, dict) else rec
            else:
                for idx, t in enumerate(titles):
                    try:
                        r = semantic_scholar_service.resolve_paper(t)
                        resolved_records[idx] = r.get("record") or {}
                    except Exception:
                        resolved_records[idx] = {}
        except Exception:
            # fallback to per-title resolve
            resolved_records = {}
            for idx, t in enumerate(titles):
                try:
                    r = semantic_scholar_service.resolve_paper(t)
                    resolved_records[idx] = r.get("record") or {}
                except Exception:
                    resolved_records[idx] = {}

        # 2) Build keyword inputs and request keywords in batch if supported
        kw_inputs = []
        for idx, cand in enumerate(selected_candidates):
            rec = resolved_records.get(idx) or {}
            kw_inputs.append("\n\n".join([
                f"Title: {rec.get('title') or cand.get('title') or ''}",
                f"Abstract: {rec.get('abstract') or ''}",
                f"TLDR: {rec.get('tldr') or ''}",
                f"User Text: "
            ]))

        kw_results = []
        try:
            if hasattr(ai_service, "get_keywords_and_importance_batch"):
                kw_results = ai_service.get_keywords_and_importance_batch(kw_inputs, provider=provider)
            else:
                for ki in kw_inputs:
                    try:
                        kw_results.append(ai_service.get_keywords_and_importance(ki, provider=provider))
                    except Exception:
                        kw_results.append({})
        except Exception:
            # fallback to individual calls
            kw_results = []
            for ki in kw_inputs:
                try:
                    kw_results.append(ai_service.get_keywords_and_importance(ki, provider=provider))
                except Exception:
                    kw_results.append({})

        # 3) Batch embeddings for candidates (prefer abstract/tldr)
        texts_for_embedding = []
        for idx, cand in enumerate(selected_candidates):
            rec = resolved_records.get(idx) or {}
            texts_for_embedding.append(rec.get('abstract') or rec.get('tldr') or cand.get('title') or '')

        cand_embeddings = []
        try:
            if hasattr(ai_service, "get_embedding_batch"):
                cand_embeddings = ai_service.get_embedding_batch(texts_for_embedding)
            else:
                for t in texts_for_embedding:
                    try:
                        cand_embeddings.append(ai_service.get_embedding(t))
                    except Exception:
                        cand_embeddings.append(None)
        except Exception:
            cand_embeddings = []
            for t in texts_for_embedding:
                try:
                    cand_embeddings.append(ai_service.get_embedding(t))
                except Exception:
                    cand_embeddings.append(None)

        # 4) Compute vector similarities in batch using numpy for speed
        vec_scores = [0.0] * len(selected_candidates)
        try:
            src_vec = np.array(source_embedding, dtype=np.float32)
            cand_matrix = np.array([e if e is not None else np.zeros_like(src_vec) for e in cand_embeddings], dtype=np.float32)
            # handle zero norms
            src_norm = np.linalg.norm(src_vec)
            cand_norms = np.linalg.norm(cand_matrix, axis=1)
            # safe dot products
            dots = cand_matrix.dot(src_vec)
            for i in range(len(selected_candidates)):
                if src_norm == 0 or cand_norms[i] == 0:
                    vec_scores[i] = 0.0
                else:
                    vec_scores[i] = float(dots[i] / (src_norm * cand_norms[i]))
        except Exception:
            # fallback to per-item cosine
            for i, emb in enumerate(cand_embeddings):
                try:
                    vec_scores[i] = KnowledgeBaseService._cosine_similarity_np(source_embedding, emb or [])
                except Exception:
                    vec_scores[i] = 0.0

        # 5) Assemble final scores using keyword matching and combine
        results = []
        for idx, cand in enumerate(selected_candidates):
            rec = resolved_records.get(idx) or {}
            kw_res = kw_results[idx] if idx < len(kw_results) else {}
            cand_keywords = kw_res.get('keywords') or []
            cand_kw_importance = kw_res.get('keyword_importance') or [1.0] * len(cand_keywords)

            # compute keyword score
            lower_src_kw = [k.lower() for k in (source_keywords or [])]
            lower_cand_kw = [k.lower() for k in cand_keywords]
            kw1_dict = dict(zip(lower_src_kw, source_keyword_importance or [1.0] * len(lower_src_kw)))
            kw2_dict = dict(zip(lower_cand_kw, cand_kw_importance))
            keyword_score = KnowledgeBaseService._compute_weighted_keyword_score(kw1_dict, kw2_dict)

            vector_score = max(0.0, vec_scores[idx])
            score = max(0.0, min(1.0, (vector_score * 0.6) + (keyword_score * 0.4)))

            # persist semantic scholar paper metadata (but do NOT create a user-owned Paper)
            try:
                with neo4j_client.get_session() as s2:
                    s2.run(
                        "MERGE (r:SemanticScholarPaper {paperId: $paper_id}) SET r.title = $title, r.year = $year, r.authors = $authors, r.abstract = $abstract, r.tldr = $tldr, r.updatedAt = datetime()",
                        paper_id=rec.get('paperId') or cand.get('paper_id'),
                        title=rec.get('title') or cand.get('title'),
                        year=rec.get('year'),
                        authors=rec.get('authors') or cand.get('authors') or [],
                        abstract=rec.get('abstract'),
                        tldr=rec.get('tldr'),
                    )
            except Exception:
                logger.debug("Failed to persist SemanticScholarPaper metadata for candidate", exc_info=True)

            results.append({
                'paper_id': rec.get('paperId') or cand.get('paper_id'),
                'title': rec.get('title') or cand.get('title'),
                'year': rec.get('year') or cand.get('year'),
                'authors': rec.get('authors') or cand.get('authors'),
                'abstract': rec.get('abstract') or '',
                'tldr': rec.get('tldr') or '',
                'keywords': cand_keywords,
                'keyword_importance': cand_kw_importance,
                'rank': idx + 1,
                'score': round(score, 4),
                'vector_score': round(vector_score, 4),
                'keyword_score': round(keyword_score, 4),
            })

        # Persist recommendation record
        try:
            with neo4j_client.get_session() as session:
                KnowledgeBaseService._store_recommendation(
                    session=session,
                    user_id=user_id,
                    source_paper_id=src.get("id"),
                    method="single",
                    params={"prefilter_limit": prefilter_limit, "final_k": final_k},
                    results=results,
                )
        except Exception:
            logger.warning("Failed to store recommendation record", exc_info=True)

        return {"source": src.get("id"), "candidates": results}

    @staticmethod
    def _store_recommendation(session, user_id: str, source_paper_id: str, method: str, params: dict, results: list):
        rec_id = str(uuid.uuid4())
        session.run(
            "MATCH (u:User) WHERE elementId(u) = $user_id MATCH (p:Paper {id: $paper_id, userId: $user_id}) CREATE (r:Recommendation {id: $rec_id, method: $method, params: $params, createdAt: datetime()}) CREATE (u)-[:CREATED]->(r) CREATE (r)-[:RAN_ON]->(p)",
            user_id=user_id, paper_id=source_paper_id, rec_id=rec_id, method=method, params=json.dumps(params),
        )
        # link candidates
        for idx, item in enumerate(results, start=1):
            pid = item.get("paper_id")
            score = item.get("score")
            session.run(
                """
                MATCH (r:Recommendation {id: $rec_id})
                MERGE (c:RecommendedCandidate {paperId: $paper_id})
                ON CREATE SET
                    c.title = $title,
                    c.year = $year,
                    c.authors = $authors,
                    c.abstract = $abstract,
                    c.tldr = $tldr,
                    c.keywords = $keywords,
                    c.keyword_importance = $keyword_importance
                SET
                    c.title = $title,
                    c.year = $year,
                    c.authors = $authors,
                    c.abstract = $abstract,
                    c.tldr = $tldr,
                    c.keywords = $keywords,
                    c.keyword_importance = $keyword_importance,
                    c.updatedAt = datetime()
                MERGE (r)-[rel:RECOMMENDED_CANDIDATE {rank: $rank}]->(c)
                SET
                    rel.score = $score,
                    rel.vector_score = $vector_score,
                    rel.keyword_score = $keyword_score
                """,
                rec_id=rec_id,
                paper_id=pid,
                title=item.get("title"),
                year=item.get("year"),
                authors=item.get("authors") or [],
                abstract=item.get("abstract") or "",
                tldr=item.get("tldr") or "",
                keywords=item.get("keywords") or [],
                keyword_importance=item.get("keyword_importance") or [],
                rank=idx,
                score=score,
                vector_score=item.get("vector_score"),
                keyword_score=item.get("keyword_score"),
            )

    @staticmethod
    def get_latest_recommendation(user_id: str, paper_id: str, method: str = "single"):
        with neo4j_client.get_session() as session:
            result = session.run(
                """
                MATCH (u:User)-[:CREATED]->(r:Recommendation)-[:RAN_ON]->(p:Paper)
                WHERE elementId(u) = $user_id
                  AND (p.id = $paper_id OR elementId(p) = $paper_id)
                  AND r.method = $method
                OPTIONAL MATCH (r)-[rel:RECOMMENDED_CANDIDATE]->(c:RecommendedCandidate)
                WITH r, p, c, rel
                ORDER BY r.createdAt DESC, rel.rank ASC
                RETURN r, p, c, rel
                """,
                user_id=user_id,
                paper_id=paper_id,
                method=method,
            )

            recommendation = None
            candidates = []
            source = None

            for record in result:
                if recommendation is None:
                    recommendation = record["r"]
                    paper = record["p"]
                    source = {
                        "id": paper.get("id") or paper.element_id,
                        "title": paper.get("title"),
                    }

                candidate = record.get("c")
                rel = record.get("rel")
                if candidate:
                    candidates.append({
                        "paper_id": candidate.get("paperId") or candidate.element_id,
                        "title": candidate.get("title"),
                        "year": candidate.get("year"),
                        "authors": candidate.get("authors") or [],
                        "abstract": candidate.get("abstract") or "",
                        "tldr": candidate.get("tldr") or "",
                        "keywords": candidate.get("keywords") or [],
                        "keyword_importance": candidate.get("keyword_importance") or [],
                        "score": rel.get("score") if rel else None,
                        "vector_score": rel.get("vector_score") if rel else None,
                        "keyword_score": rel.get("keyword_score") if rel else None,
                        "rank": rel.get("rank") if rel else None,
                    })

            if not recommendation:
                return None

            params = recommendation.get("params")
            try:
                params = json.loads(params) if isinstance(params, str) else (params or {})
            except Exception:
                params = {}

            return {
                "recommendation": {
                    "id": recommendation.get("id") or recommendation.element_id,
                    "method": recommendation.get("method"),
                    "params": params,
                    "createdAt": str(recommendation.get("createdAt")) if recommendation.get("createdAt") else None,
                },
                "source": source,
                "candidates": candidates,
            }

    @staticmethod
    def recommend_dual(user_id: str, paper1_id: str, paper2_id: str, prefilter_limit: int = 100, final_k: int = 10):
        """
        Recommend candidates relevant to both paper1 and paper2.
        Strategy:
        - If intersection of stored references exists, return intersection ranked by simple heuristics.
        - Else, combine keywords and follow single-paper flow on combined query.
        """
        # load both
        with neo4j_client.get_session() as session:
            res = session.run(
                "MATCH (p1:Paper {userId: $user_id}) WHERE (p1.id = $p1 OR elementId(p1) = $p1) RETURN p1",
                user_id=user_id, p1=paper1_id,
            )
            r1 = res.single()
            res = session.run(
                "MATCH (p2:Paper {userId: $user_id}) WHERE (p2.id = $p2 OR elementId(p2) = $p2) RETURN p2",
                user_id=user_id, p2=paper2_id,
            )
            r2 = res.single()
            if not r1 or not r2:
                raise ValueError("One or both source papers not found")
            p1 = r1["p1"] if "p1" in r1 else r1[0]
            p2 = r2["p2"] if "p2" in r2 else r2[0]

        # Attempt intersection of stored SemanticScholarPaper relations
        with neo4j_client.get_session() as session:
            inter = session.run(
                "MATCH (a:Paper {id: $p1, userId: $user_id})-[:HAS_REFERENCE|HAS_CITATION]->(r:SemanticScholarPaper)<-[:HAS_REFERENCE|HAS_CITATION]-(b:Paper {id: $p2, userId: $user_id}) RETURN r",
                p1=p1.get("id"), p2=p2.get("id"), user_id=user_id,
            )
            inter_cands = []
            for rec in inter:
                r = rec["r"]
                inter_cands.append({
                    "paper_id": r.get("paperId") or r.element_id,
                    "title": r.get("title"),
                    "year": r.get("year"),
                    "authors": r.get("authors") or [],
                })

        if inter_cands:
            # rank by simple heuristics and return top final_k
            inter_cands = sorted(inter_cands, key=lambda c: KnowledgeBaseService._prefilter_score_for(c, [], set(), datetime.now().year), reverse=True)[:final_k]
            return {"source": [p1.get("id"), p2.get("id")], "candidates": inter_cands}

        # else combine keywords and reuse single flow
        base = KnowledgeBaseService.recommend_single(user_id, p1.get("id"), prefilter_limit=prefilter_limit, final_k=final_k*2)
        # Filter base candidates by relevance to paper2
        p2_keywords = p2.get("keywords") or []
        def _score_against_p2(item):
            kw_overlap = len(set([k.lower() for k in (item.get('title') or '').split()]) & set([k.lower() for k in p2_keywords]))
            return kw_overlap
        filtered = sorted(base.get("candidates", []), key=_score_against_p2, reverse=True)[:final_k]
        return {"source": [p1.get("id"), p2.get("id")], "candidates": filtered}

    @staticmethod
    def get_pending_quiz(user_id: str):
        quiz_bundle = KnowledgeBaseService.get_quiz_candidates(user_id)
        items = quiz_bundle.get("items", [])
        if not items:
            return None
        first_item = items[0]
        return {
            "paper1": first_item["paper1_title"],
            "paper2": first_item["paper2_title"],
            "summary1": first_item.get("paper1_summary", ""),
            "summary2": first_item.get("paper2_summary", ""),
            "link_id": first_item["paper2_id"],
        }

    @staticmethod
    def _prefilter_score_for(cand: dict, source_keywords: list, source_authors: set, current_year: int) -> float:
        score = 0.0
        try:
            cand_authors = set([a.lower() for a in (cand.get("authors") or [])])
            score += 2.0 * len(source_authors & cand_authors)
        except Exception:
            pass
        try:
            cand_keywords = set([k.lower() for k in (cand.get("keywords") or [])])
            score += 1.0 * len(set([k.lower() for k in (source_keywords or [])]) & cand_keywords)
        except Exception:
            pass
        try:
            year = int(cand.get("year") or 0)
            if year > 0:
                year_delta = max(0, current_year - year)
                recency = 1.0 / (1.0 + year_delta)
                score += 0.5 * recency
        except Exception:
            pass
        return score

    @staticmethod
    def get_existing_relationship(user_id: str, paper1_id: str, paper2_id: str):
        paper1 = KnowledgeBaseService._get_paper_by_id(user_id, paper1_id)
        paper2 = KnowledgeBaseService._get_paper_by_id(user_id, paper2_id)
        if not paper1 or not paper2:
            raise ValueError("Paper pair not found")

        with neo4j_client.get_session() as session:
            result = session.run(
                """
                MATCH (p1:Paper {userId: $user_id})-[r:SHADOW_LINK|RELATED_TO]-(p2:Paper {userId: $user_id})
                WHERE (
                    (p1.id = $paper1_id OR elementId(p1) = $paper1_id)
                    AND (p2.id = $paper2_id OR elementId(p2) = $paper2_id)
                )
                OR (
                    (p1.id = $paper2_id OR elementId(p1) = $paper2_id)
                    AND (p2.id = $paper1_id OR elementId(p2) = $paper1_id)
                )
                RETURN r
                LIMIT 1
                """,
                user_id=user_id,
                paper1_id=paper1_id,
                paper2_id=paper2_id,
            )
            record = result.single()
            if not record or not record["r"]:
                return None

            rel = record["r"]
            return {
                "paper1_id": paper1_id,
                "paper2_id": paper2_id,
                "rel_type": rel.get("type", rel.type),
                "status": rel.get("status", "confirmed"),
                "description": rel.get("description", ""),
                "commonalities": rel.get("commonalities", ""),
                "differences": rel.get("differences", ""),
                "question": rel.get("question", ""),
                "score": rel.get("score", None),
            }

    @staticmethod
    def confirm_relationship(
        user_id: str,
        paper1_id: str,
        paper2_id: str,
        description: str,
        rel_type: str = "RELATED_TO",
        question: str = "",
        commonalities: str = "",
        differences: str = "",
    ):
        embedding_store = KnowledgeBaseService._get_all_embeddings(user_id)
        data1 = KnowledgeBaseService._resolve_embedding_data(user_id, paper1_id, embedding_store)
        data2 = KnowledgeBaseService._resolve_embedding_data(user_id, paper2_id, embedding_store)

        if not data1 or not data2:
            raise ValueError("Paper pair not found")

        similarity = KnowledgeBaseService._compute_hybrid_score(
            data1["embedding"], data1["keywords"], data1["keyword_importance"],
            data2["embedding"], data2["keywords"], data2["keyword_importance"],
        )

        with neo4j_client.get_session() as session:
            session.run(
                """
                MATCH (p1:Paper {userId: $user_id})
                MATCH (p2:Paper {userId: $user_id})
                WHERE (p1.id = $paper1_id OR elementId(p1) = $paper1_id)
                  AND (p2.id = $paper2_id OR elementId(p2) = $paper2_id)
                                MERGE (p1)-[r:SHADOW_LINK]-(p2)
                SET r.description = $description,
                    r.type = $rel_type,
                    r.question = $question,
                    r.commonalities = $commonalities,
                    r.differences = $differences,
                    r.score = $score,
                    r.vector_score = $vector_score,
                    r.keyword_score = $keyword_score,
                    r.status = 'confirmed',
                    r.updatedAt = datetime()
                """,
                user_id=user_id,
                paper1_id=paper1_id,
                paper2_id=paper2_id,
                description=description,
                rel_type=rel_type,
                question=question,
                commonalities=commonalities,
                differences=differences,
                score=similarity["score"],
                vector_score=similarity["vector_score"],
                keyword_score=similarity["keyword_score"],
            )

        # create cooldown slot so frontend shows timer before new candidate fills the slot
        try:
            KnowledgeBaseService._create_cooldown_for_user(user_id, paper1_id, paper2_id, hours=3)
        except Exception:
            pass
        # invalidate any cached question for this pair
        try:
            pair_key = KnowledgeBaseService._normalize_pair_key(paper1_id, paper2_id)
            user_cache = KnowledgeBaseService._question_cache.get(user_id, {})
            if pair_key in user_cache:
                del user_cache[pair_key]
        except Exception:
            pass

        return {"status": "confirmed", "paper1_id": paper1_id, "paper2_id": paper2_id, "rel_type": rel_type}

    @staticmethod
    def _create_cooldown_for_user(user_id: str, paper1_id: str, paper2_id: str, hours: int = 3):
        import datetime as _dt
        expires_iso = (_dt.datetime.utcnow() + _dt.timedelta(hours=hours)).isoformat()
        cooldown_id = str(uuid.uuid4())
        with neo4j_client.get_session() as session:
            session.run(
                """
                MATCH (u:User) WHERE elementId(u) = $user_id
                CREATE (s:QuizCooldown {
                    id: $id,
                    paper1_id: $paper1_id,
                    paper2_id: $paper2_id,
                    expiresAt: datetime($iso),
                    createdAt: datetime()
                })
                CREATE (u)-[:HAS_COOLDOWN]->(s)
                """,
                user_id=user_id,
                id=cooldown_id,
                paper1_id=paper1_id,
                paper2_id=paper2_id,
                iso=expires_iso,
            )
        return cooldown_id

    @staticmethod
    def delete_paper(user_id: str, paper_id: str):
        # remove paper node and all relationships, plus chroma entry and any quiz cooldowns
        try:
            prop_id = None
            # Resolve property id if element id provided
            with neo4j_client.get_session() as session:
                res = session.run(
                    """
                    MATCH (p:Paper)
                    WHERE elementId(p) = $paper_id OR p.id = $paper_id
                    RETURN p.id as prop_id
                    LIMIT 1
                    """,
                    paper_id=paper_id,
                )
                rec = res.single()
                if rec:
                    prop_id = rec.get('prop_id')

            # Delete the node by matching either elementId or property id
            with neo4j_client.get_session() as session:
                session.run(
                    """
                    MATCH (p:Paper)
                    WHERE (elementId(p) = $paper_id OR p.id = $paper_id) AND p.userId = $user_id
                    DETACH DELETE p
                    """,
                    paper_id=paper_id,
                    user_id=user_id,
                )

                # remove any quiz cooldowns that reference this paper property id (if available)
                if prop_id:
                    session.run(
                        """
                        MATCH (u:User)-[rel:HAS_COOLDOWN]->(s:QuizCooldown)
                        WHERE elementId(u) = $user_id AND (s.paper1_id = $prop_id OR s.paper2_id = $prop_id)
                        DELETE rel, s
                        """,
                        user_id=user_id,
                        prop_id=prop_id,
                    )

            # Remove from Chroma by property id if available
            try:
                collection = chroma_client.get_collection(user_id)
                if prop_id:
                    collection.delete(ids=[prop_id])
                else:
                    # best-effort: try element id as well
                    collection.delete(ids=[paper_id])
            except Exception:
                pass

            # Invalidate any cached questions that mention this paper
            try:
                user_cache = KnowledgeBaseService._question_cache.get(user_id, {})
                keys_to_remove = [
                    k for k in list(user_cache.keys())
                    if (prop_id and prop_id in k) or (paper_id in k)
                ]
                for k in keys_to_remove:
                    user_cache.pop(k, None)
            except Exception:
                pass

            return {"status": "deleted", "paper_id": paper_id, "prop_id": prop_id}
        except Exception as e:
            logger.error("Error deleting paper %s: %s", paper_id, e)
            raise

knowledge_base_service = KnowledgeBaseService()
