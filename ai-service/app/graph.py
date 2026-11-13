from langgraph.graph import END, START, StateGraph

from app.state import AgentState
from app.schemas import ChatRequest, ChatResponse

from app.router import route_intent

# Імпортуємо модулі
from app.actions.explain import run as run_explain
from app.actions.practice import run as run_practice
from app.actions.check import run as run_check


async def router_node(state: AgentState) -> dict:
  """Вузол-роутер на базі ML: аналізує текст учня та визначає current_action"""
  
  # Викликаємо твою модель класифікації
  detected_intent = await route_intent(
      message=state.user_input,
      history=state.history
  )
  
  # Повертаємо оновлений intent у стан графа
  return {
      "current_action": detected_intent  
  }


async def explain_node(state: AgentState) -> dict:
  """Вузол пояснення (Кріт-Дослідник)"""
  req = ChatRequest(
      user_id=state.user_id,
      grade=state.grade,
      subject=state.subject,
      topic=state.topic,
      topic_id=state.topic_id,
      message=state.user_input,
      profile=state.profile,
  )

  response: ChatResponse = await run_explain(req)

  return {
      "output_text": response.reply,
      "suggestions": [
          "⛏️ Копати глибше",
          "✍️ До практики",
      ],
  }


async def practice_node(state: AgentState) -> dict:
  """Вузол тренажера та практики"""
  req = ChatRequest(
      user_id=state.user_id,
      grade=state.grade,
      subject=state.subject,
      topic=state.topic,
      topic_id=state.topic_id,
      message=state.user_input,
      task=state.current_task,
      hints_used=state.hints_used,
      profile=state.profile,
  )

  response: ChatResponse = await run_practice(req)

  return {
      "output_text": response.reply,
      "current_task": response.task,
      "hints_used": response.hints_used,
      "suggestions": [
          "💡 Дай підказку",
          "✅ Відповісти",
          "📖 Показати розв'язок",
      ],
  }


async def check_node(state: AgentState) -> dict:
  """Вузол мікро-перевірки знань"""
  req = ChatRequest(
      user_id=state.user_id,
      grade=state.grade,
      subject=state.subject,
      topic=state.topic,
      topic_id=state.topic_id,
      message=state.user_input,
      task=state.current_task,
      hints_used=state.hints_used,
      profile=state.profile,
  )

  response: ChatResponse = await run_check(req)

  return {
      "output_text": response.reply,
      "suggestions": [
          "🔄 Пройти ще раз",
          "🚀 Наступна тема",
      ],
  }


# --- ФУНКЦІЯ МАРШРУТИЗАЦІЇ ДЛЯ ГРАФА ---

def decide_next_node(state: AgentState) -> str:
  """Читає вже визначений ML-моделлю current_action і обирає гілку"""
  if state.current_action == "practice":
    return "practice_node"
  elif state.current_action == "explain":
    return "explain_node"
  return "check_node"


# --- ЗБИРАННЯ ТА КОМПІЛЯЦІЯ ГРАФА ---

workflow = StateGraph(AgentState)

# 1. Додаємо вузли (включаючи роутер як повноцінний вузол)
workflow.add_node("router_node", router_node)
workflow.add_node("explain_node", explain_node)
workflow.add_node("practice_node", practice_node)
workflow.add_node("check_node", check_node)

# 2. Потік починається з роутера: START -> router_node
workflow.add_edge(START, "router_node")

# 3. Після того як роутер визначив intent, робимо умовний перехід у потрібний модуль
workflow.add_conditional_edges(
    "router_node",
    decide_next_node,
    {
        "explain_node": "explain_node",
        "practice_node": "practice_node",
        "check_node": "check_node",
    },
)

# 4. Закриваємо такти виконання гілок
workflow.add_edge("explain_node", END)
workflow.add_edge("practice_node", END)
workflow.add_edge("check_node", END)

# 5. Компілюємо граф
app_graph = workflow.compile()