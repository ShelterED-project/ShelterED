from langgraph.graph import END, START, StateGraph

from app.state import AgentState
from app.schemas import ChatRequest, ChatResponse
from app.router import route_intent

from app.actions.explain import run as run_explain
from app.actions.practice import run as run_practice
from app.actions.check import run as run_check


ROUTES = {
    "explain": "explain_node",
    "practice": "practice_node",
    "check": "check_node",
}


async def router_node(state: AgentState) -> dict:
  # Якщо клієнт явно вибрав дію, використовуємо її
  if state.action in ROUTES:
    return {"current_action": state.action}

  try:
    intent = await route_intent(message=state.user_input, history=state.history)
  except Exception:
    # Якщо модель недоступна, не ламаємо запит
    intent = "explain"

  return {"current_action": intent}


def _base_request(state: AgentState, **extra) -> ChatRequest:
  return ChatRequest(
      user_id=state.user_id,
      grade=state.grade,
      subject=state.subject,
      topic=state.topic,
      topic_id=state.topic_id,
      message=state.user_input,
      history=state.history or None,
      profile=state.profile,
      **extra,
  )


async def explain_node(state: AgentState) -> dict:
  response: ChatResponse = await run_explain(_base_request(state))
  return {
      "output_text": response.reply,
      "suggestions": ["⛏️ Копати глибше", "✍️ До практики"],
  }


async def practice_node(state: AgentState) -> dict:
  response: ChatResponse = await run_practice(
      _base_request(state, task=state.current_task, hints_used=state.hints_used)
  )
  return {
      "output_text": response.reply,
      "current_task": response.task,
      "hints_used": response.hints_used or 0,
      "suggestions": ["💡 Дай підказку", "✅ Відповісти", "📖 Показати розв'язок"],
  }


async def check_node(state: AgentState) -> dict:
  if not state.current_task:
    return {
        "output_text": "Спочатку попроси завдання, а потім надсилай свою відповідь.",
        "current_action": "practice",
        "suggestions": ["✍️ До практики"],
    }

  response: ChatResponse = await run_check(
      _base_request(
          state,
          task=state.current_task,
          hints_used=state.hints_used,
          image_base64=state.image_base64,
      )
  )
  return {
      "output_text": response.reply,
      "check_result": response.check_result,
      "suggestions": ["🔄 Пройти ще раз", "🚀 Наступна тема"],
  }


def decide_next_node(state: AgentState) -> str:
  # support і chat поки що ведуться як explain, доки не буде окремих вузлів
  return ROUTES.get(state.current_action, "explain_node")


workflow = StateGraph(AgentState)

workflow.add_node("router_node", router_node)
workflow.add_node("explain_node", explain_node)
workflow.add_node("practice_node", practice_node)
workflow.add_node("check_node", check_node)

workflow.add_edge(START, "router_node")
workflow.add_conditional_edges("router_node", decide_next_node, {
    "explain_node": "explain_node",
    "practice_node": "practice_node",
    "check_node": "check_node",
})
workflow.add_edge("explain_node", END)
workflow.add_edge("practice_node", END)
workflow.add_edge("check_node", END)

app_graph = workflow.compile()