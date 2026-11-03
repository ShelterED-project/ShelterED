/** Сьогоднішня дата для підписів, наприклад «вівторок, 14 жовтня». Реальна, не мок. */
export function todayLabel({ capitalize = false }: { capitalize?: boolean } = {}): string {
  const text = new Date().toLocaleDateString('uk-UA', { weekday: 'long', day: 'numeric', month: 'long' })
  return capitalize ? text.charAt(0).toUpperCase() + text.slice(1) : text
}
