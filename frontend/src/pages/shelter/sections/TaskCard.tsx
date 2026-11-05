import { useState } from 'react'
import iconCheck from '@/assets/shelter/check-dim.svg'
import mole from '@/assets/landing/mole.svg'
import { submitAnswer } from '@/features/lessons/submitAnswer'
import { task } from '../content'

export default function TaskCard() {
  const [answer, setAnswer] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)

  const choose = (option: string) => {
    setAnswer(option)
    setSaved(false)
  }

  const check = async () => {
    if (answer === null) return
    await submitAnswer(task.cardId, answer)
    setSaved(true)
  }

  return (
    <section
      aria-labelledby="task-title"
      className="flex flex-col gap-[11px] rounded-3xl border border-line bg-surface p-5 xl:p-7"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs leading-4 text-dim">{task.meta}</p>
        <p className="flex items-center gap-1.5 text-xs leading-4 text-dim">
          <img src={iconCheck} alt="" width={16} height={16} className="shrink-0" />
          {task.saved}
        </p>
      </div>

      <h2
        id="task-title"
        className="font-heading text-[22px] leading-[27.5px] tracking-[-0.22px] text-parchment xl:text-[26px] xl:leading-[32.5px] xl:tracking-[-0.26px]"
      >
        {task.question}
      </h2>

      <fieldset className="grid gap-3 pt-[9px] md:grid-cols-2">
        <legend className="sr-only">{task.question}</legend>
        {task.options.map((option) => (
          <label
            key={option}
            className="flex h-14 cursor-pointer items-center gap-3 rounded-[14px] border border-line bg-surface px-4 text-[17px] leading-[25.5px] font-semibold text-parchment has-checked:border-accent has-checked:bg-surface-2 has-focus-visible:ring-2 has-focus-visible:ring-accent/40"
          >
            <input
              type="radio"
              name="answer"
              value={option}
              checked={answer === option}
              onChange={() => choose(option)}
              className="size-5 shrink-0 appearance-none rounded-full border border-[#767676] bg-white checked:border-accent checked:bg-[radial-gradient(circle,var(--color-accent)_0_6px,white_6.5px)]"
            />
            {option}
          </label>
        ))}
      </fieldset>

      <div className="flex items-end gap-3 pt-[9px]">
        <img
          src={mole}
          alt="Кріт — маскот ShelterED"
          width={64}
          height={64}
          className="size-16 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]"
        />
        <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[19px] leading-[1.25] font-semibold text-parchment md:text-[22px]">
          {task.hint}
        </p>
      </div>

      {/* TODO: «Показати підказку ще раз» — повторне відображення підказки, коли зʼявиться логіка підказок */}
      <div className="flex flex-col gap-3 pt-[9px] md:flex-row md:justify-end">
        <button
          type="button"
          className="h-12 rounded-[10px] border border-line-strong px-5 text-[15px] font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {task.hintAgain}
        </button>
        <button
          type="button"
          onClick={check}
          disabled={answer === null}
          className="h-12 rounded-[10px] bg-accent px-7 text-[15px] font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:opacity-50"
        >
          {task.check}
        </button>
      </div>

      {saved && (
        <p role="status" className="text-sm font-semibold text-safe md:text-right">
          {task.answerSaved}
        </p>
      )}
    </section>
  )
}
