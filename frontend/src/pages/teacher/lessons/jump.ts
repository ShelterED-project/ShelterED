// Перехід до проблеми з публікації: прокрутити до елемента, підсвітити й поставити фокус у поле.

const HIGHLIGHT = ['ring-2', 'ring-accent', 'ring-offset-2', 'ring-offset-oil']

export function jumpTo(elementId: string): boolean {
  const el = document.getElementById(elementId)
  if (!el) return false
  el.scrollIntoView({ block: 'center', behavior: 'smooth' })
  el.classList.add(...HIGHLIGHT)
  window.setTimeout(() => el.classList.remove(...HIGHLIGHT), 2600)
  const field = el.querySelector<HTMLElement>('textarea, input:not([type=file]), button')
  field?.focus({ preventScroll: true })
  return true
}

// Новостворений модуль, картка чи питання отримує фокус один раз (одразу писати, без зайвого кліку).
const pendingFocus = new Set<string>()

export function focusOnMount(id: string) {
  pendingFocus.add(id)
}

export function takeFocus(id: string): boolean {
  return pendingFocus.delete(id)
}
