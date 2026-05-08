from fastapi import APIRouter, Depends, HTTPException
from ..services.knowledge_service import knowledge_base_service
from .auth import get_current_user
from pydantic import BaseModel

router = APIRouter()

class PaperUpload(BaseModel):
    title: str
    text: str

@router.post("/papers")
async def upload_paper(data: PaperUpload, current_user: dict = Depends(get_current_user)):
    try:
        result = knowledge_base_service.add_paper(current_user["id"], data.title, data.text)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/graph")
async def get_graph(current_user: dict = Depends(get_current_user)):
    try:
        return knowledge_base_service.get_graph_data(current_user["id"])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/quiz")
async def get_quiz(current_user: dict = Depends(get_current_user)):
    quiz = knowledge_base_service.get_pending_quiz(current_user["id"])
    if not quiz:
        return {"message": "No pending quizzes"}
    return quiz

class QuizAnswer(BaseModel):
    link_id: str
    description: str
    rel_type: str = "RELATED_TO"

@router.post("/quiz/confirm")
async def confirm_quiz(data: QuizAnswer, current_user: dict = Depends(get_current_user)):
    try:
        # Validate that the link belongs to the user or at least check permission
        return knowledge_base_service.confirm_relationship(data.link_id, data.description, data.rel_type)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
