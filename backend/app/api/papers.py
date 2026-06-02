from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
import json
import logging
import traceback
from ..services.knowledge_service import knowledge_base_service
from .auth import get_current_user
from pydantic import BaseModel
from ..core.database import neo4j_client
from typing import Optional

router = APIRouter()
logger = logging.getLogger(__name__)

class PaperUpload(BaseModel):
    title: str
    text: Optional[str] = None
    categories: Optional[list[str]] = None
    manual_keywords: Optional[list] = None
    manual_keyword_importance: Optional[list] = None


class QuizQuestionRequest(BaseModel):
    paper1_id: str
    paper2_id: str


class QuizConfirmRequest(BaseModel):
    paper1_id: str
    paper2_id: str
    description: str
    rel_type: str = "RELATED_TO"
    commonalities: str = ""
    differences: str = ""
    question: str = ""


class RecommendSingleRequest(BaseModel):
    paper_id: str
    prefilter_limit: Optional[int] = 100
    final_k: Optional[int] = 10


class RecommendDualRequest(BaseModel):
    paper1_id: str
    paper2_id: str
    prefilter_limit: Optional[int] = 100
    final_k: Optional[int] = 10

@router.post("/papers")
async def upload_paper(data: PaperUpload, current_user: dict = Depends(get_current_user)):
    try:
        result = knowledge_base_service.add_paper(
            current_user["id"],
            data.title,
            data.text,
            categories=data.categories,
            manual_keywords=data.manual_keywords,
            manual_keyword_importance=data.manual_keyword_importance,
        )
        return result
    except Exception as e:
        logger.error("Error in upload_paper: %s", e)
        logger.debug(traceback.format_exc())
        # Don't expose internals to client; return generic message
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/graph")
async def get_graph(category: Optional[str] = None, current_user: dict = Depends(get_current_user)):
    try:
        return knowledge_base_service.get_graph_data(current_user["id"], category=category)
    except Exception as e:
        logger.error("Error in get_graph: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/graph/similarity")
async def get_graph_similarity(paper1_id: str, paper2_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return knowledge_base_service.get_pair_similarity(current_user["id"], paper1_id, paper2_id)
    except Exception as e:
        logger.error("Error in get_graph_similarity: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/graph/relationship")
async def get_graph_relationship(paper1_id: str, paper2_id: str, current_user: dict = Depends(get_current_user)):
    try:
        relationship = knowledge_base_service.get_existing_relationship(current_user["id"], paper1_id, paper2_id)
        return relationship or {}
    except Exception as e:
        logger.error("Error in get_graph_relationship: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

@router.get("/quiz")
async def get_quiz(current_user: dict = Depends(get_current_user)):
    quiz_bundle = knowledge_base_service.get_quiz_candidates(current_user["id"])
    return quiz_bundle


@router.post("/quiz/question")
async def get_quiz_question(data: QuizQuestionRequest, current_user: dict = Depends(get_current_user)):
    try:
        return knowledge_base_service.get_relationship_question(current_user["id"], data.paper1_id, data.paper2_id)
    except Exception as e:
        logger.error("Error in get_quiz_question: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")

@router.post("/quiz/confirm")
async def confirm_quiz(data: QuizConfirmRequest, current_user: dict = Depends(get_current_user)):
    try:
        return knowledge_base_service.confirm_relationship(
            current_user["id"],
            data.paper1_id,
            data.paper2_id,
            data.description,
            data.rel_type,
            data.question,
            data.commonalities,
            data.differences,
        )
    except Exception as e:
        logger.error("Error in confirm_quiz: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/quiz/refresh")
async def refresh_quiz_slot(current_user: dict = Depends(get_current_user)):
    try:
        # remove the earliest active cooldown so the slot can refill immediately
        with neo4j_client.get_session() as session:
            res = session.run(
                """
                MATCH (u:User)-[r:HAS_COOLDOWN]->(s:QuizCooldown)
                WHERE elementId(u) = $user_id AND s.expiresAt > datetime()
                WITH r, s
                ORDER BY s.expiresAt ASC
                LIMIT 1
                DELETE r, s
                RETURN 1 as removed
                """,
                user_id=current_user["id"],
            )
            rec = res.single()
            return {"removed": int(rec["removed"]) if rec else 0}
    except Exception as e:
        logger.error("Error in refresh_quiz_slot: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.delete("/papers/{paper_id}")
async def delete_paper(paper_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return knowledge_base_service.delete_paper(current_user["id"], paper_id)
    except Exception as e:
        logger.error("Error in delete_paper: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.post("/recommend/single/stream")
async def recommend_single_stream(data: RecommendSingleRequest, current_user: dict = Depends(get_current_user)):
    import asyncio
    loop = asyncio.get_running_loop()
    queue = asyncio.Queue()

    def progress_cb(step: str, pct: int):
        logger.info(f"[PROGRESS] {pct}% - {step}")
        loop.call_soon_threadsafe(queue.put_nowait, {"step": step, "pct": pct})

    async def run():
        try:
            result = await asyncio.to_thread(
                knowledge_base_service.recommend_single,
                current_user["id"],
                data.paper_id,
                data.prefilter_limit or 100,
                data.final_k or 10,
                progress_cb,
            )
            queue.put_nowait({"step": "done", "pct": 100, "result": result})
        except Exception as e:
            queue.put_nowait({"step": "error", "pct": 0, "error": str(e)})

    async def event_generator():
        asyncio.create_task(run())
        while True:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=120.0)
            except asyncio.TimeoutError:
                yield f"data: {json.dumps({'step': 'error', 'pct': 0, 'error': 'timeout'})}\n\n"
                break
            yield f"data: {json.dumps(msg)}\n\n"
            if msg["step"] in ("done", "error"):
                break

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
            "Transfer-Encoding": "chunked",
        }
    )


@router.post("/recommend/dual")
async def recommend_dual(data: RecommendDualRequest, current_user: dict = Depends(get_current_user)):
    try:
        prefilter_limit = data.prefilter_limit or 100
        final_k = data.final_k or 10
        return knowledge_base_service.recommend_dual(current_user["id"], data.paper1_id, data.paper2_id, prefilter_limit, final_k)
    except Exception as e:
        logger.error("Error in recommend_dual: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")


@router.get("/recommend/latest")
async def recommend_latest(paper_id: str, method: str = "single", current_user: dict = Depends(get_current_user)):
    try:
        result = knowledge_base_service.get_latest_recommendation(current_user["id"], paper_id, method)
        return result or {}
    except Exception as e:
        logger.error("Error in recommend_latest: %s", e)
        logger.debug(traceback.format_exc())
        raise HTTPException(status_code=500, detail="Internal server error")
