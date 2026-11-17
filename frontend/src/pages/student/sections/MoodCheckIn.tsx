import { useState } from 'react'
import { weatherIcon } from '@/features/wellbeing/weather'
import type { Hotline, WellbeingTexts, WellbeingValue } from '@/features/wellbeing/wellbeingApi'
import { calmPage } from '../content'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'

function HotlineList({ hotlines }: { hotlines: Hotline[] }) {
  return (
    <ul className="flex flex-col gap-2">
      {hotlines.map((line) => (
        <li key={line.phone} className="flex items-center justify-between gap-3 rounded-2xl bg-surface-2 p-3">
          <span className="min-w-0">
            <span className="block font-heading text-lg text-parchment">{line.phone}</span>
            <span className="block text-xs text-dim">{line.note}</span>
          </span>
          <a
            href={`tel:${line.phone.replace(/\s/g, '')}`}
            className="flex h-11 shrink-0 items-center rounded-[10px] border border-line-strong px-4 text-sm font-semibold text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {calmPage.call}
          </a>
        </li>
      ))}
    </ul>
  )
}

/**
 * «Як ти зараз?»: картинка погоди замість слів і чисел. Повністю добровільно (є «Пропустити»,
 * пропуск ніде не записується). Відповідь на будь-який вибір однаково тепла; для «Грози» й
 * «Дощику» — м'яка пропозиція подихати й поговорити з дорослим. Блок гарячої лінії — лише за
 * сигналом сервера (show_support), без тривожних вікон.
 */
export default function MoodCheckIn({
  texts,
  answeredToday,
  showSupport,
  onAnswer,
  onBreathe,
}: {
  texts: WellbeingTexts
  answeredToday: boolean
  showSupport: boolean
  onAnswer: (value: WellbeingValue) => Promise<void>
  onBreathe: () => void
}) {
  const t = texts.child
  const [chosen, setChosen] = useState<WellbeingValue | null>(null)
  const [skipped, setSkipped] = useState(false)
  const [changing, setChanging] = useState(false)
  const [lowOfferClosed, setLowOfferClosed] = useState(false)

  if (skipped) return null

  // Після вибору — відповідь; картинки знову показуємо лише на прохання змінити.
  if (chosen !== null) {
    const low = chosen <= 2
    return (
      <section className={card} aria-live="polite">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.question}</h2>
        <p className="flex items-center gap-3 text-[17px] leading-6 text-parchment">
          <span className="text-4xl" aria-hidden="true">
            {weatherIcon[t.scale.find((s) => s.value === chosen)?.picture ?? 'cloud']}
          </span>
          {t.reply}
        </p>
        {low && !lowOfferClosed && (
          <div className="flex flex-col gap-3 rounded-2xl bg-surface-2 p-4">
            <p className="text-[15px] leading-[22.5px] text-parchment">{t.reply_low_extra.text}</p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={onBreathe}
                className="h-11 rounded-[10px] bg-accent px-5 text-sm font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
              >
                {t.reply_low_extra.breathing.start}
              </button>
              <button
                type="button"
                onClick={() => setLowOfferClosed(true)}
                className="h-11 rounded-[10px] border border-line-strong px-5 text-sm font-semibold text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
              >
                {t.reply_low_extra.breathing.later}
              </button>
            </div>
            <p className="text-sm text-muted">{t.reply_low_extra.trusted_adult}</p>
          </div>
        )}
        {showSupport && (
          <div className="flex flex-col gap-3 border-t border-line-soft pt-4">
            <h3 className="text-[17px] font-semibold text-parchment">{t.support.title}</h3>
            <p className="text-[15px] leading-[22.5px] text-muted">{t.support.text}</p>
            <HotlineList hotlines={t.support.hotlines} />
          </div>
        )}
        <button
          type="button"
          onClick={() => {
            setChosen(null)
            setChanging(true)
          }}
          className="self-start rounded text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {calmPage.change}
        </button>
      </section>
    )
  }

  return (
    <section className={card}>
      <div className="flex flex-col gap-1">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.question}</h2>
        <p className="text-sm text-muted">{answeredToday && !changing ? calmPage.answeredToday : t.hint}</p>
      </div>
      <ul className="grid grid-cols-5 gap-2">
        {t.scale.map((item) => (
          <li key={item.value}>
            <button
              type="button"
              onClick={() => {
                setChosen(item.value)
                void onAnswer(item.value)
              }}
              className="flex w-full flex-col items-center gap-1 rounded-2xl border border-line bg-surface-2/50 px-1 py-3 hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            >
              <span className="text-3xl md:text-4xl" aria-hidden="true">
                {weatherIcon[item.picture]}
              </span>
              <span className="text-center text-xs leading-4 text-parchment">{item.label}</span>
            </button>
          </li>
        ))}
      </ul>
      <button
        type="button"
        onClick={() => setSkipped(true)}
        className="self-start rounded text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        {t.skip}
      </button>
    </section>
  )
}
