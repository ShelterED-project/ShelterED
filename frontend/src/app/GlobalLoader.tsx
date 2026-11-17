import { useEffect, useState } from 'react'
import mole from '@/assets/landing/mole.svg'
import { useAppSelector } from '@/app/hooks'
import Spinner from '@/shared/ui/Spinner'

/** Довше не тримаємо: застосунок має відкриватися з локальних даних навіть без мережі. */
const MAX_MS = 4000
/** Короткі паузи між запитами не вважаємо кінцем завантаження. */
const SETTLE_MS = 150

/**
 * Заставка на весь екран, поки сторінка робить перші запити: замість «Завантаження…» у кожному
 * блоці. Лише при старті й після входу іншого користувача; при переходах між сторінками її немає
 * (фонові запити на кшталт опитування тривог показували б її вже після завантаження сторінки).
 * Без мережі зникає одразу, у будь-якому разі — не пізніше ніж за 4 с.
 */
export default function GlobalLoader() {
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  const pending = useAppSelector((s) => Object.values(s.api.queries).some((q) => q?.status === 'pending'))
  const [doneFor, setDoneFor] = useState<string | null | undefined>(undefined)
  const visible = doneFor !== (userId ?? null)

  useEffect(() => {
    if (!visible) return
    const finish = () => setDoneFor(userId ?? null)
    if (!navigator.onLine) {
      finish()
      return
    }
    const limit = setTimeout(finish, MAX_MS)
    const settle = pending ? undefined : setTimeout(finish, SETTLE_MS)
    return () => {
      clearTimeout(limit)
      clearTimeout(settle)
    }
  }, [visible, pending, userId])

  if (!visible) return null

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-0 z-[60] flex flex-col items-center justify-center gap-5 bg-oil"
    >
      <img src={mole} alt="" width={96} height={96} className="size-24 drop-shadow-[0_0_10px_rgba(242,178,92,0.35)]" />
      <p className="font-heading text-2xl text-parchment">ShelterED</p>
      <p className="flex items-center gap-3 text-sm text-muted">
        <Spinner className="text-accent" />
        Завантаження…
      </p>
    </div>
  )
}
