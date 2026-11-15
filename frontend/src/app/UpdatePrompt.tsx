import { useRegisterSW } from 'virtual:pwa-register/react'

/** Як часто перевіряти нову версію, поки застосунок відкритий (і лише з мережею). */
const UPDATE_CHECK_MS = 60 * 60 * 1000

const button =
  'h-11 shrink-0 rounded-[10px] px-4 text-sm font-semibold whitespace-nowrap focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none'

/**
 * Реєструє Service Worker і показує дві підказки:
 * - «готово до роботи без мережі» після першого кешування застосунку;
 * - «доступна нова версія»: оновлення лише з дозволу, бо учень може бути посеред уроку.
 * Застарілий застосунок нічого не ламає: дані в IndexedDB, події чекають в outbox.
 */
export default function UpdatePrompt() {
  const {
    needRefresh: [needRefresh, setNeedRefresh],
    offlineReady: [offlineReady, setOfflineReady],
    updateServiceWorker,
  } = useRegisterSW({
    onRegisteredSW(_url, registration) {
      if (!registration) return
      // Рідка перевірка оновлень: лише коли вкладка видима й є мережа (енергоменеджер).
      setInterval(() => {
        if (document.visibilityState === 'visible' && navigator.onLine) void registration.update()
      }, UPDATE_CHECK_MS)
    },
  })

  if (!needRefresh && !offlineReady) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-4 bottom-[88px] z-50 mx-auto flex max-w-md flex-col gap-3 rounded-2xl border border-line bg-surface-2 p-4 shadow-lg md:bottom-6 md:flex-row md:items-center"
    >
      <p className="min-w-0 flex-1 text-sm leading-5 text-parchment">
        {needRefresh
          ? 'Доступна нова версія ShelterED. Оновіть, коли буде зручно: незбережене не загубиться.'
          : 'ShelterED готовий працювати без інтернету.'}
      </p>
      <div className="flex gap-2">
        {needRefresh && (
          <button type="button" onClick={() => void updateServiceWorker()} className={`${button} bg-accent text-oil`}>
            Оновити
          </button>
        )}
        <button
          type="button"
          onClick={() => {
            setNeedRefresh(false)
            setOfflineReady(false)
          }}
          className={`${button} border border-line-strong text-parchment hover:bg-surface`}
        >
          {needRefresh ? 'Пізніше' : 'Добре'}
        </button>
      </div>
    </div>
  )
}
