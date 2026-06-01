from fastapi import APIRouter, Depends, HTTPException
from .auth import get_current_user
from ..core.database import neo4j_client
from pydantic import BaseModel, Field
from ..services.knowledge_service import knowledge_base_service

router = APIRouter()

class UserSettings(BaseModel):
    ai_provider: str
    quiz_frequency: int
    ai_edge_threshold: float = Field(default=0.35, ge=0.0, le=1.0)
    final_k: int = Field(default=10, ge=1, le=50)

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    with neo4j_client.get_session() as session:
        result = session.run("""
            MATCH (u:User {username: $username})
            OPTIONAL MATCH (u)-[:OWNS]->(p:Paper)
            OPTIONAL MATCH (p)-[r:RELATED_TO|SHADOW_LINK]->(m:Paper)
            WHERE coalesce(r.status, 'confirmed') = 'confirmed'
            RETURN count(DISTINCT p) as paperCount, count(DISTINCT r) as linkCount
        """, username=current_user["username"])
        record = result.single()
        return {
            "paperCount": record["paperCount"],
            "linkCount": record["linkCount"],
            "username": current_user["username"]
        }

@router.get("/settings")
async def get_settings(current_user: dict = Depends(get_current_user)):
    with neo4j_client.get_session() as session:
        result = session.run("MATCH (u:User {username: $username}) RETURN u.ai_provider as ai_provider, u.quiz_frequency as quiz_frequency, u.ai_edge_threshold as ai_edge_threshold, u.final_k as final_k",
                             username=current_user["username"])
        record = result.single()
        ai_provider = record["ai_provider"] if record and record["ai_provider"] else "openai"
        quiz_frequency = record["quiz_frequency"] if record and record["quiz_frequency"] is not None else 3
        ai_edge_threshold = record["ai_edge_threshold"] if record and record["ai_edge_threshold"] is not None else 0.35
        final_k = record["final_k"] if record and record["final_k"] is not None else 10
        return {
            "ai_provider": ai_provider,
            "quiz_frequency": quiz_frequency,
            "ai_edge_threshold": ai_edge_threshold,
            "final_k": final_k,
        }


@router.get("/categories")
async def get_categories(current_user: dict = Depends(get_current_user)):
    return {"categories": knowledge_base_service._get_user_categories(current_user["id"])}

@router.post("/settings")
async def update_settings(settings: UserSettings, current_user: dict = Depends(get_current_user)):
    with neo4j_client.get_session() as session:
        session.run("""
            MATCH (u:User {username: $username})
            SET u.ai_provider = $ai_provider, u.quiz_frequency = $quiz_frequency, u.ai_edge_threshold = $ai_edge_threshold, u.final_k = $final_k
        """, username=current_user["username"], ai_provider=settings.ai_provider, quiz_frequency=settings.quiz_frequency, ai_edge_threshold=settings.ai_edge_threshold, final_k=settings.final_k)
    return {"status": "updated"}
