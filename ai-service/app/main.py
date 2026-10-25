from fastapi import FastAPI, Header, HTTPException
from app.schemas import ChatRequest, ChatResponse
from app.config import settings
from app.llm import generate_ai_response

app = FastAPI()

def auth(key: str | None):
    if key != settings.INTERNAL_KEY:
        raise HTTPException(status_code=401, detail="Unauthorized")

@app.get("/health")
def health():
    return {"status": "ok"}

@app.post("/ai/v1/chat", response_model=ChatResponse)
def chat(req: ChatRequest, x_internal_key: str | None = Header(default=None)):
    auth(x_internal_key)
    
    if req.action == "check" and req.task is None:
        raise HTTPException(status_code=422, detail={"code": "task_required"})

    if settings.MOCK_LLM:
        reply_text = "DevOps engineer зараз вивчає Delphi 🧠⚡напиши йому за зняття заглушки" 
    else:
        reply_text = generate_ai_response(req.message)
    
    return ChatResponse(reply=reply_text, 
                        intent=req.action, 
                        topic_id=req.topic_id)