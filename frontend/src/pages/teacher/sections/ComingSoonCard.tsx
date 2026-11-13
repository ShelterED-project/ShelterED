/**
 * Розділ, якого ще немає: чесна позначка «буде пізніше» замість кнопок без дії.
 * Локальний сервер укриття й QR-синхронізація чекають на local-server і B10 на бекенді.
 */
export default function ComingSoonCard({ title, soon, text, icon }: { title: string; soon: string; text: string; icon?: string }) {
  return (
    <section className="flex gap-4 rounded-[22px] border border-dashed border-line bg-surface p-5 md:p-6">
      <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-surface-2">
        {icon ? (
          <img src={icon} alt="" width={24} height={24} />
        ) : (
          <span aria-hidden="true" className="text-xl text-muted">
            ▦
          </span>
        )}
      </span>
      <div className="flex min-w-0 flex-col gap-1">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-[17px] leading-[25.5px] font-semibold text-parchment">{title}</h2>
          <span className="rounded-md bg-line-soft px-2 py-0.5 text-xs font-semibold text-dim">{soon}</span>
        </div>
        <p className="text-sm leading-5 text-muted">{text}</p>
      </div>
    </section>
  )
}
