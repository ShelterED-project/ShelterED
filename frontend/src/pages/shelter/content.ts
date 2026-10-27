// TODO: тимчасові моки. Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).
// Кількість записів у черзі не мок: її дають useOutboxStats / useOutboxCount.

export const alert = {
  title: 'Повітряна тривога',
  region: 'Львівська обл.',
  since: 'з 10:14 · 23 хв',
  sound: 'Звук вимкнено',
}

export const header = { quiet: 'Тихий режим', offline: 'Офлайн', battery: '38%', help: 'Допомога' }

export const lesson = {
  eyebrow: 'Урок продовжується',
  title: 'Алгебра: лінійні рівняння',
  text: 'Пакет збережено зранку · ≈ 12 хв · підготувала Олена Коваль',
  progress: 0.5,
  steps: [
    { label: 'Картка 1', state: 'done' },
    { label: 'Картка 2', state: 'done' },
    { label: 'Картка 3', state: 'current' },
    { label: 'Тест', state: 'todo' },
  ] as { label: string; state: 'done' | 'current' | 'todo' }[],
  resume: 'Продовжити з картки 3',
  others: 'Інші уроки офлайн',
}

export const task = {
  cardId: 'algebra-linear-3',
  meta: 'Картка 3 з 4 · завдання',
  saved: 'відповідь збережеться офлайн',
  question: 'Розв’яжи рівняння: 3x + 5 = 20',
  options: ['x = 3', 'x = 5', 'x = 8', 'x = 25/3'],
  hint: 'Підказка: спершу перенеси 5 праворуч — що залишиться?',
  hintAgain: 'Показати підказку ще раз',
  check: 'Перевірити',
  answerSaved: 'Відповідь збережено',
}

export const next = {
  title: 'Далі в пакеті',
  hint: 'усе доступно без мережі',
  items: [
    { subject: 'Українська мова', name: 'Прислівник: правопис', meta: '8 хв · картки' },
    { subject: 'Історія України', name: 'Київська Русь: князі', meta: '10 хв · відео з субтитрами' },
    { subject: 'Спокій', name: 'Історія Крота перед сном', meta: '4 хв · текст' },
  ],
}

export const checkIn = {
  title: 'Перекличка',
  who: '7-Б · Олена Коваль',
  text: 'Відміться, щоб вчителька і батьки знали, що ти в безпеці.',
  shelter: 'Я в укритті',
  safe: 'Я в безпеці вдома',
  note: 'Зараз без мережі — відправимо автоматично',
  saved: 'Відмітку збережено',
}

export const connection = {
  title: 'Зв’язок',
  status: 'Офлайн',
  queueHint: 'відправимо, щойно зʼявиться зв’язок',
  details: [
    { term: 'Інтернет', value: 'немає', strong: true },
    { term: 'Wi-Fi класу', value: 'шукаємо…', strong: false },
    { term: 'Остання синхронізація', value: 'сьогодні, 10:02', strong: true },
    { term: 'Пакет на день', value: 'збережено · 42 МБ', strong: true },
  ],
  answers: 'Відповіді на картки',
  rollCalls: 'Перекличка',
  retry: 'Спробувати зараз',
}

export const calm = {
  title: 'Хвилинка спокою',
  text: 'Вдих 4 · пауза 4 · видих 6 · 2 хв',
  start: 'Почати',
}

export const tips = {
  title: 'Поки триває тривога',
  items: [
    { title: 'Сядь подалі від входу й вікон', text: 'У коридорі або біля внутрішньої стіни.' },
    { title: 'Бережи заряд', text: 'Яскравість на мінімум — ShelterED уже в темному режимі.' },
    { title: 'Тримайся поруч із вчителем', text: 'Якщо загубився — натисни «Допомога».' },
  ],
}
