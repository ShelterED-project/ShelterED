import type { ReactNode } from 'react'

/** Невелика контурна кнопка в рядку налаштувань («Синхронізувати зараз», «Захистити», «Створити код»). */
export const smallButton =
  'flex h-10 shrink-0 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-3 text-sm leading-5 font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60'

/** Секція налаштувань: заголовок і рядки, розділені лінією. action — дія праворуч від заголовка. */
export function Section({ title, action, children }: { title: string; action?: ReactNode; children: ReactNode }) {
  return (
    <section className="flex flex-col rounded-[22px] border border-line bg-surface px-5 py-2 md:px-6">
      <div className="flex items-center justify-between gap-3 pt-4 pb-1">
        <h2 className="font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">{title}</h2>
        {action}
      </div>
      <ul className="flex flex-col [&>li+li]:border-t [&>li+li]:border-line-soft">{children}</ul>
    </section>
  )
}

/** Рядок: назва й пояснення ліворуч, стан чи дія праворуч. */
export function Row({ title, note, children }: { title: string; note?: string; children?: ReactNode }) {
  return (
    <li className="flex items-center justify-between gap-4 py-4">
      <div className="flex min-w-0 flex-col gap-px">
        <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">{title}</p>
        {note && <p className="text-xs leading-[16.5px] text-dim">{note}</p>}
      </div>
      {children}
    </li>
  )
}

/** Стан праворуч у рядку: «✓ готово» бірюзовим або «ще ні» приглушено. */
export function Status({ ok, children }: { ok: boolean; children: ReactNode }) {
  return <span className={`shrink-0 text-xs leading-4 font-semibold ${ok ? 'text-safe' : 'text-dim'}`}>{children}</span>
}
