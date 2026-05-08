from fastapi import APIRouter, Depends, HTTPException
from .auth import get_current_user
from ..core.database import neo4j_client
from pydantic import BaseModel

router = APIRouter()

class UserSettings(BaseModel):
    ai_provider: str
    quiz_frequency: int

@router.get("/stats")
async def get_stats(current_user: dict = Depends(get_current_user)):
    with neo4j_client.get_session() as session:
        result = session.run("""
            MATCH (u:User {username: $username})
            OPTIONAL MATCH (u)-[:OWNS]->(p:Paper)
            OPTIONAL MATCH (p)-[r:RELATED_TO|SHADOW_LINK]-(m:Paper)
            RETURN count(DISTINCT p) as paperCount, count(DISTINCT r)/2 as linkCount
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
        result = session.run("MATCH (u:User {username: $username}) RETURN u.ai_provider as ai_provider, u.quiz_frequency as quiz_frequency", 
                             username=current_user["username"])
        record = result.single()
        return {
            "ai_provider": record["ai_provider"],
            "quiz_frequency": record["quiz_frequency"]
        }

@router.post("/settings")
async def update_settings(settings: UserSettings, current_user: dict = Depends(get_current_user)):
    with neo4j_client.get_session() as session:
        session.run("""
            MATCH (u:User {username: $username})
            SET u.ai_provider = $ai_provider, u.quiz_frequency = $quiz_frequency
        """, username=current_user["username"], ai_provider=settings.ai_provider, quiz_frequency=settings.quiz_frequency)
    return {"status": "updated"}
