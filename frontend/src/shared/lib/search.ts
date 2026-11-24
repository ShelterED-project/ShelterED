/** Для пошуку: нижній регістр, без варіантів апострофа (’ ʼ ' `) і зайвих пробілів. */
export function normalizeSearch(text: string): string {
  return text.toLowerCase().replace(/[’ʼ'`]/g, '').replace(/\s+/g, ' ').trim()
}

/** Чи містить хоч одне з полів запит (порожній запит підходить усім). */
export function matchesSearch(query: string, ...fields: (string | null | undefined)[]): boolean {
  const q = normalizeSearch(query)
  if (!q) return true
  return fields.some((field) => normalizeSearch(field ?? '').includes(q))
}
