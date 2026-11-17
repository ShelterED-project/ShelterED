/** Сьогоднішня дата для підписів, наприклад «вівторок, 14 жовтня». Реальна, не мок. */
export function todayLabel({ capitalize = false }: { capitalize?: boolean } = {}): string {
  const text = new Date().toLocaleDateString('uk-UA', { weekday: 'long', day: 'numeric', month: 'long' })
  return capitalize ? text.charAt(0).toUpperCase() + text.slice(1) : text
}

/** Час «10:35» за поясом пристрою. */
export function timeLabel(iso: string | number): string {
  return new Date(iso).toLocaleTimeString('uk-UA', { hour: '2-digit', minute: '2-digit' })
}

/** Коротка дата «14 жовт.». */
export function shortDateLabel(iso: string): string {
  return new Date(iso).toLocaleDateString('uk-UA', { day: 'numeric', month: 'short' })
}

/** Дата й час «14 жовт., 10:35». */
export function dateTimeLabel(iso: string): string {
  return new Date(iso).toLocaleString('uk-UA', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
}
