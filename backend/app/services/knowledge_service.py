from .database import neo4j_client
from .vector_db import chroma_client
from ..services.ai_service import ai_service
from ..core.config import settings

class KnowledgeBaseService:
    @staticmethod
    def add_paper(user_id: str, title: str, text: str):
        # 0. Fetch User Provider Preference
        provider = "openai"
        with neo4j_client.get_session() as session:
            res = session.run("MATCH (u) WHERE elementId(u) = $user_id RETURN u.ai_provider as p", user_id=user_id)
            record = res.single()
            if record:
                provider = record["p"]

        # 1. Generate AI metadata
        ai_data = ai_service.get_summary_and_keywords(text, provider=provider)
        embedding = ai_service.get_embedding(ai_data['summary'])
        
        # 2. Save to Neo4j
        with neo4j_client.get_session() as session:
            session.run("""
                MERGE (u:User {id: $user_id})
                CREATE (p:Paper {
                    id: apoc.create.uuid(),
                    title: $title,
                    summary: $summary,
                    keywords: $keywords,
                    userId: $user_id,
                    createdAt: datetime()
                })
                CREATE (u)-[:OWNS]->(p)
            """, user_id=user_id, title=title, summary=ai_data['summary'], keywords=ai_data['keywords'])
            
            # Check paper count for this user
            count_result = session.run("MATCH (u:User {id: $user_id})-[:OWNS]->(p:Paper) RETURN count(p) as count", user_id=user_id)
            paper_count = count_result.single()["count"]
        
        # 3. Save to Chroma
        collection = chroma_client.get_collection(user_id)
        collection.add(
            embeddings=[embedding],
            documents=[ai_data['summary']],
            metadatas=[{"title": title, "userId": user_id}],
            ids=[title] # Using title as ID for simplicity in this draft
        )
        
        # 4. If count >= 5, trigger shadow link creation
        if paper_count >= settings.MIN_PAPER_COUNT:
            KnowledgeBaseService.create_shadow_links(user_id, embedding, title)
            
        return {"status": "success", "paper_count": paper_count, "active": paper_count >= settings.MIN_PAPER_COUNT}

    @staticmethod
    def create_shadow_links(user_id: str, new_embedding: list, new_paper_title: str):
        collection = chroma_client.get_collection(user_id)
        results = collection.query(
            query_embeddings=[new_embedding],
            n_results=5,
            where={"userId": user_id}
        )
        
        with neo4j_client.get_session() as session:
            for i, distance in enumerate(results['distances'][0]):
                if distance < 0.5: # Threshold for similarity
                    target_title = results['ids'][0][i]
                    if target_title != new_paper_title:
                        session.run("""
                            MATCH (p1:Paper {title: $title1, userId: $user_id})
                            MATCH (p2:Paper {title: $title2, userId: $user_id})
                            MERGE (p1)-[r:SHADOW_LINK]->(p2)
                            ON CREATE SET r.score = $score, r.createdAt = datetime()
                        """, title1=new_paper_title, title2=target_title, user_id=user_id, score=(1-distance))

    @staticmethod
    def get_graph_data(user_id: str):
        nodes = []
        links = []
        with neo4j_client.get_session() as session:
            result = session.run("""
                MATCH (n:Paper {userId: $user_id})
                OPTIONAL MATCH (n)-[r:OWNS|RELATED_TO|SHADOW_LINK]-(m:Paper {userId: $user_id})
                RETURN n, r, m
            """, user_id=user_id)
            
            node_ids = set()
            for record in result:
                n = record["n"]
                if n.element_id not in node_ids:
                    nodes.append({
                        "id": n.element_id,
                        "title": n["title"],
                        "summary": n["summary"],
                        "keywords": n["keywords"]
                    })
                    node_ids.add(n.element_id)
                
                m = record["m"]
                r = record["r"]
                if m and r:
                    links.append({
                        "source": n.element_id,
                        "target": m.element_id,
                        "type": r.type,
                        "score": r.get("score", 1.0),
                        "description": r.get("description", "")
                    })
        return {"nodes": nodes, "links": links}

    @staticmethod
    def get_pending_quiz(user_id: str):
        with neo4j_client.get_session() as session:
            result = session.run("""
                MATCH (p1:Paper {userId: $user_id})-[r:SHADOW_LINK]->(p2:Paper {userId: $user_id})
                WHERE r.description IS NULL
                RETURN p1, r, p2
                ORDER BY r.createdAt ASC
                LIMIT 1
            """, user_id=user_id)
            
            record = result.single()
            if record:
                return {
                    "paper1": record["p1"]["title"],
                    "paper2": record["p2"]["title"],
                    "summary1": record["p1"]["summary"],
                    "summary2": record["p2"]["summary"],
                    "link_id": record["r"].element_id
                }
        return None

    @staticmethod
    def confirm_relationship(link_id: str, description: str, rel_type: str = "RELATED_TO"):
        with neo4j_client.get_session() as session:
            session.run("""
                MATCH ()-[r]->()
                WHERE elementId(r) = $link_id
                SET r.description = $description, r.type = $rel_type
            """, link_id=link_id, description=description, rel_type=rel_type)
        return {"status": "confirmed"}

knowledge_base_service = KnowledgeBaseService()
