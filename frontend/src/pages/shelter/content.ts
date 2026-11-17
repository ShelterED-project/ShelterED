// Моків немає: там, де мають бути дані з API, стоїть заглушка «Сюди: …» з описом, що саме додати.
// Коли зʼявиться API, замінити на RTK Query + локальне сховище
// (принцип 1: інтерфейс читає з локального сховища, а не з констант у коді).
// Кількість записів у черзі не заглушка: її дають useOutboxStats / useOutboxCount.

export const alert = {
  title: 'Повітряна тривога',
  drillTitle: 'Тренувальна тривога',
  since: (time: string) => `триває з ${time}`,
  endedTitle: 'Відбій тривоги',
  endedText: 'Можна повернутися на головну.',
  home: 'На головну',
  sound: 'Звук вимкнено',
}

export const header = { quiet: 'Тихий режим', offline: 'Офлайн', battery: '—', help: 'Допомога' }

export const lesson = {
  eyebrow: 'Урок продовжується',
  noPack: 'Пакет на сьогодні ще не збережено',
  noPackText: 'Підключись до мережі один раз, і уроки збережуться на пристрої.',
  noLesson: 'На сьогодні уроків немає',
  noLessonText: 'Відпочивай або повтори пройдене.',
  allDone: 'Урок пройдено',
  resume: 'Продовжити',
  others: 'Інші уроки офлайн',
}

export const task = {
  saved: 'прогрес збережеться офлайн',
  moduleMeta: (position: number, total: number) => `Картка ${position} з ${total}`,
  testMeta: (position: number, total: number) => `Питання ${position} з ${total}`,
  next: 'Далі',
  finishModule: 'Завершити модуль',
  check: 'Перевірити',
  finishTest: 'Завершити тест',
  moduleSaved: 'Модуль завершено',
  testSaved: 'Відповіді збережено, результат зʼявиться після синхронізації',
  correct: 'Так тримати!',
  wrong: 'Нічого, наступне вийде.',
  score: (points: number, max: number) => `Результат: ${points} з ${max}`,
  multipleHint: 'Можна обрати кілька відповідей',
  empty: 'Тут зʼявиться завдання, коли буде збережено пакет уроку.',
  allDone: 'Усі кроки уроку пройдено. Молодець!',
}

export const results = {
  title: 'Результати тестів',
  local: (points: number, max: number) => `${points} з ${max}`,
  server: (score: number) => `${Math.round(score)}%`,
  credited: 'зараховано',
  late: 'не зараховано: після дедлайну',
  repeat: 'не зараховано: зараховано першу спробу',
  pending: 'результат зʼявиться після синхронізації',
  checking: 'перевіряється',
  notTaken: 'ще не пройдено',
}

export const next = {
  title: 'Інші уроки на сьогодні',
  hint: 'усе доступно без мережі',
  empty: 'Інших уроків на сьогодні немає.',
}

export const checkIn = {
  title: 'Перекличка',
  who: 'Сюди: клас · імʼя вчителя',
  text: 'Відміться, щоб вчитель і батьки знали, що ти в безпеці.',
  shelter: 'Я в укритті',
  safe: 'Я в безпеці вдома',
  note: 'Зараз без мережі — відправимо автоматично',
  saved: 'Відмітку збережено',
}

export const connection = {
  title: 'Зв’язок',
  status: { online: 'Онлайн', offline: 'Офлайн', unreachable: 'Сервер недоступний' },
  queueEmpty: 'Черга порожня',
  queueHint: 'відправимо, щойно зʼявиться зв’язок',
  queueSentHint: 'усе відправлено на сервер',
  internet: { term: 'Інтернет', yes: 'Є', no: 'Немає' },
  server: { term: 'Сервер', ok: 'Відповідає', unreachable: 'Не відповідає', unknown: 'Ще не перевірено' },
  lastSync: { term: 'Остання синхронізація', never: 'Ще не було' },
  packs: {
    term: 'Уроки на пристрої',
    none: 'Не збережено',
    days: (n: number, until: string, word: string) => `${n} ${word}, до ${until}`,
  },
  app: { term: 'Застосунок без мережі', ready: 'Готовий', notReady: 'Ще не збережено' },
  answers: 'Прогрес і тести',
  rollCalls: 'Перекличка',
  retry: 'Спробувати зараз',
  retrying: 'Синхронізуємо…',
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
