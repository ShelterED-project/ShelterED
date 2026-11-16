import hmac

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.graph import app_graph
from app.llm import LLMError
from app.schemas import ChatRequest, ChatResponse, IntentEnum

app = FastAPI(title="ShelterED AI")

# Граф може повернути класи, яких немає в IntentEnum (support, chat)
INTENT_MAP = {
    "explain": IntentEnum.explain,
    "practice": IntentEnum.practice,
    "check": IntentEnum.check,
}


@app.exception_handler(LLMError)
async def llm_error_handler(_, exc: LLMError):
    return JSONResponse(
        status_code=503,
        content={"code": "model_unavailable", "message": str(exc)},
    )


def auth(key: str | None) -> None:
    if not key or not hmac.compare_digest(key, settings.INTERNAL_KEY):
        raise HTTPException(status_code=401, detail={"code": "unauthorized"})


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/ai/v1/chat", response_model=ChatResponse)
async def chat(req: ChatRequest, x_internal_key: str | None = Header(default=None)):
    auth(x_internal_key)

    state = {
        "user_id": req.user_id,
        "action": req.action,
        "grade": req.grade,
        "subject": req.subject,
        "topic": req.topic,
        "topic_id": req.topic_id,
        "user_input": req.message or "",
        "history": req.history or [],
        "profile": req.profile,
        "current_task": req.task,
        "hints_used": req.hints_used,
    }

    result = await app_graph.ainvoke(state)
    if not isinstance(result, dict):
        result = result.model_dump()

    intent = result.get("current_action", "explain")
    return ChatResponse(
        reply=result.get("output_text", ""),
        intent=INTENT_MAP.get(intent, IntentEnum.explain),
        topic_id=req.topic_id,
        task=result.get("current_task"),
        hints_used=result.get("hints_used"),
    )