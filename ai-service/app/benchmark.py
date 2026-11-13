import time
import torch
from sentence_transformers import SentenceTransformer

# Назва твоєї моделі
model_name = 'paraphrase-multilingual-MiniLM-L12-v2'

# Тестовий набір речень (імітуємо реальні запити користувачів)
texts = [
    'Як розв`язати квадратне рівняння?',
    'Мені тривожно і страшно перед іспитом',
    'Поясни поняття рекурсії простими словами',
    'Які причини виникнення Другої світової війни?',
    'Допоможи скласти план підготовки до сесії',
] * 20  # Повторюємо, щоб отримати 100 запитів для точності

print(f"Завантаження моделі та тест для {len(texts)} запитів...\n")

# --- 1. Тест на CPU ---
print('1. Тестування на CPU...')
model_cpu = SentenceTransformer(model_name, device='cpu')

# Прогрів (warm-up) для чистоти експерименту
_ = model_cpu.encode(texts[:5])

start_time = time.time()
_ = model_cpu.encode(texts)
cpu_time = time.time() - start_time

print(f'   -> Загальний час на CPU: {cpu_time:.4f} секунд')
print(f'   -> Середній час на 1 запит: {(cpu_time/len(texts))*1000:.2f} мс\n')


# --- 2. Тест на GPU (якщо доступно) ---
if torch.cuda.is_available():
  print('2. Тестування на GPU (CUDA)...')
  model_gpu = SentenceTransformer(model_name, device='cuda')

  # Прогрів відеокарти
  _ = model_gpu.encode(texts[:5])

  start_time = time.time()
  _ = model_gpu.encode(texts)
  gpu_time = time.time() - start_time

  print(f'   -> Загальний час на GPU: {gpu_time:.4f} секунд')
  print(f'   -> Середній час на 1 запит: {(gpu_time/len(texts))*1000:.2f} мс\n')

  # Порівняння
  speedup = cpu_time / gpu_time
  print(f'🚀 GPU працює швидше у {speedup:.1f} рази!')
else:
  print(
      '2. Тест на GPU пропущено: у поточному середовищі встановлена CPU-версія'
      ' PyTorch або немає драйверів CUDA.'
  )