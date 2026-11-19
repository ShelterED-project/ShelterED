import { useState } from 'react'
import type { Hotline, WeatherPicture, WellbeingTexts, WellbeingValue } from '@/features/wellbeing/wellbeingApi'
import { calmPage } from '../content'
import { weatherImage } from './weatherImages'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
const textButton =
  'rounded text-sm leading-5 font-semibold text-dim hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none'

const HISTORY_DAYS = 14

/** День школи (YYYY-MM-DD) як «пт». Полудень UTC: день не зсувається поясом. */
function weekday(date: string): string {
  return new Date(`${date}T12:00:00Z`).toLocaleDateString('uk-UA', { weekday: 'short' })
}

/** Останні 14 днів до сьогодні включно: два тижні в сітці 7 × 2, дні без відповіді порожні. */
function History({
  title,
  days,
  labels,
}: {
  title: string
  days: { date: string; picture: WeatherPicture }[]
  labels: Map<WeatherPicture, string>
}) {
  const byDate = new Map(days.map((d) => [d.date, d.picture]))
  // Дати фіксуємо при відкритті: сітка не перебудовується посеред перегляду.
  const [dates] = useState(() =>
    Array.from({ length: HISTORY_DAYS }, (_, i) => {
      const d = new Date()
      d.setDate(d.getDate() - (HISTORY_DAYS - 1 - i))
      return d.toLocaleDateString('sv-SE')
    }),
  )

  return (
    <div className="flex flex-col gap-2 border-t border-line-soft pt-4">
      <div className="flex items-center justify-between gap-3 text-xs leading-4 text-dim">
        <h3>{title}</h3>
        <span>{calmPage.history.onlyYou}</span>
      </div>
      {days.length === 0 ? (
        <p className="text-sm text-muted">{calmPage.history.empty}</p>
      ) : (
        <ol className="grid grid-cols-7 gap-y-2">
          {dates.map((date) => {
            const picture = byDate.get(date)
            return (
              <li
                key={date}
                className="flex flex-col items-center gap-1"
                aria-label={`${weekday(date)}: ${picture ? (labels.get(picture) ?? '') : calmPage.history.noAnswer}`}
              >
                {picture ? (
                  <span className="flex size-7 items-center justify-center rounded-lg bg-surface-2" aria-hidden="true">
                    <img src={weatherImage[picture]} alt="" width={20} height={20} />
                  </span>
                ) : (
                  <span className="size-7 rounded-lg border border-dashed border-line" aria-hidden="true" />
                )}
                <span className="text-[10px] leading-[15px] text-dim" aria-hidden="true">
                  {weekday(date)}
                </span>
              </li>
            )
          })}
        </ol>
      )}
    </div>
  )
}

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
  days,
  onAnswer,
  onBreathe,
}: {
  texts: WellbeingTexts
  answeredToday: boolean
  showSupport: boolean
  /** Свої картинки за 14 днів; null — ще не завантажені й не збережені на пристрої */
  days: { date: string; picture: WeatherPicture }[] | null
  onAnswer: (value: WellbeingValue) => Promise<void>
  onBreathe: () => void
}) {
  const t = texts.child
  const [chosen, setChosen] = useState<WellbeingValue | null>(null)
  const [skipped, setSkipped] = useState(false)
  const [changing, setChanging] = useState(false)
  const [lowOfferClosed, setLowOfferClosed] = useState(false)
  const labels = new Map(t.scale.map((item) => [item.picture, item.label]))
  const footer = (
    <>
      {days && <History title={t.history_title} days={days} labels={labels} />}
      <p className="text-xs leading-[19.5px] text-dim">{calmPage.privacy}</p>
    </>
  )

  // «Пропустити» ховає лише питання: свої картинки й пояснення приватності лишаються.
  if (skipped) {
    return (
      <section className={card} aria-label={t.history_title}>
        {footer}
      </section>
    )
  }

  // Після вибору — відповідь; картинки знову показуємо лише на прохання змінити.
  if (chosen !== null) {
    const low = chosen <= 2
    return (
      <section className={card} aria-live="polite">
        <h2 className="font-heading text-xl leading-7 text-parchment">{t.question}</h2>
        <p className="flex items-center gap-3 text-[17px] leading-6 text-parchment">
          <img
            src={weatherImage[t.scale.find((item) => item.value === chosen)?.picture ?? 'cloud']}
            alt=""
            width={44}
            height={44}
            className="shrink-0"
          />
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
          className={`self-start ${textButton}`}
        >
          {calmPage.change}
        </button>
        {footer}
      </section>
    )
  }

  return (
    <section className={`${card} md:gap-4`}>
      <div className="flex flex-col gap-1">
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">{t.question}</h2>
          <button type="button" onClick={() => setSkipped(true)} className={`shrink-0 ${textButton}`}>
            {t.skip}
          </button>
        </div>
        <p className="text-sm leading-5 text-muted">{answeredToday && !changing ? calmPage.answeredToday : t.hint}</p>
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
              className="flex h-full w-full flex-col items-center gap-1.5 rounded-2xl border border-line bg-surface px-1 py-3 hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            >
              <img src={weatherImage[item.picture]} alt="" width={44} height={44} className="size-10 md:size-11" />
              <span className="text-center text-[11px] leading-[13.75px] text-muted">{item.label}</span>
            </button>
          </li>
        ))}
      </ul>
      {footer}
    </section>
  )
}
