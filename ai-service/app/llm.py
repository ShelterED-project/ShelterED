from openai import OpenAI
from app.config import settings

client = OpenAI(
    api_key=settings.AI_KEY,
    base_url=settings.LLM_BASE_URL
)

def generate_ai_response(prompt: str) -> str:
    try:
        response = client.chat.completions.create(
            model=settings.MODELS,
            messages=[
                {"role": "system", "content": "Ти — корисний AI-репетитор для освітньої платформи ShelterED."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Помилка звернення до AI: {str(e)}"