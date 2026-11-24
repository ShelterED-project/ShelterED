import type { PackQuestion } from '@/shared/db/packTypes'
import type { QuestionAnswer } from '@/shared/db/types'
import { question as texts } from './content'

export interface QuestionInputProps {
  question: PackQuestion
  /** Поточна відповідь (формат за kind, див. docs/sync-protocol.md) */
  answer: QuestionAnswer | undefined
  onChange: (answer: QuestionAnswer) => void
  disabled?: boolean
  /** Enter у полі тексту: перейти далі */
  onSubmit?: () => void
}

const optionBase =
  'flex min-h-14 items-center gap-3 rounded-[14px] border border-line bg-surface px-4 py-2 text-[17px] leading-[25.5px] font-semibold text-parchment'

function ChoiceQuestion({ question, answer, onChange, disabled }: QuestionInputProps) {
  const multiple = question.kind === 'multiple'
  const selected = Array.isArray(answer) ? answer : []

  const choose = (id: string) =>
    onChange(multiple ? (selected.includes(id) ? selected.filter((s) => s !== id) : [...selected, id]) : [id])

  return (
    <fieldset className="grid gap-3 pt-[9px] md:grid-cols-2">
      <legend className="sr-only">{question.prompt}</legend>
      {multiple && <p className="col-span-full text-sm text-dim">{texts.multipleHint}</p>}
      {question.options.map((option) => (
        <label
          key={option.id}
          className={`${optionBase} cursor-pointer has-checked:border-accent has-checked:bg-surface-2 has-focus-visible:ring-2 has-focus-visible:ring-accent/40 has-disabled:cursor-default`}
        >
          <input
            type={multiple ? 'checkbox' : 'radio'}
            name={`q-${question.id}`}
            value={option.id}
            checked={selected.includes(option.id)}
            onChange={() => choose(option.id)}
            disabled={disabled}
            className={`size-5 shrink-0 appearance-none border border-[#767676] bg-white checked:border-accent checked:bg-[radial-gradient(circle,var(--color-accent)_0_6px,white_6.5px)] ${multiple ? 'rounded-md' : 'rounded-full'}`}
          />
          {option.text}
        </label>
      ))}
    </fieldset>
  )
}

function TextQuestion({ question, answer, onChange, disabled, onSubmit }: QuestionInputProps) {
  const value = Array.isArray(answer) ? (answer[0] ?? '') : ''
  const inputId = `q-${question.id}`
  return (
    <div className="flex flex-col gap-2 pt-[9px]">
      <label htmlFor={inputId} className="text-sm font-semibold text-muted">
        {texts.textLabel}
      </label>
      <input
        id={inputId}
        type="text"
        value={value}
        onChange={(e) => onChange([e.target.value])}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && value.trim() !== '') onSubmit?.()
        }}
        disabled={disabled}
        maxLength={200}
        placeholder={texts.textPlaceholder}
        autoComplete="off"
        autoCorrect="off"
        autoCapitalize="off"
        spellCheck={false}
        enterKeyHint="done"
        className="h-14 w-full rounded-[14px] border border-line-strong bg-surface-2 px-4 text-lg font-semibold text-parchment placeholder:font-normal placeholder:text-dim focus:border-accent focus:outline-none focus-visible:ring-2 focus-visible:ring-accent/40"
      />
    </div>
  )
}

/**
 * Відповідність без перетягування: під кожним лівим елементом — кнопки правих. Натиск обирає
 * пару; той самий правий в іншого рядка знімається (праві не повторюються).
 */
function MatchQuestion({ question, answer, onChange, disabled }: QuestionInputProps) {
  const pairs = answer && !Array.isArray(answer) ? answer : {}
  const rights = question.right_options ?? []

  const pick = (leftId: string, rightId: string) => {
    const next: Record<string, string> = {}
    for (const [left, right] of Object.entries(pairs)) if (right !== rightId) next[left] = right
    if (pairs[leftId] !== rightId) next[leftId] = rightId
    onChange(next)
  }

  return (
    <div className="flex flex-col gap-3 pt-[9px]">
      <p className="text-sm text-dim">{texts.matchHint}</p>
      <ol className="flex flex-col gap-3">
        {question.options.map((left, i) => {
          const chosen = pairs[left.id]
          return (
            <li key={left.id} className="flex flex-col gap-2.5 rounded-[14px] border border-line bg-surface p-4">
              <p className="text-[17px] leading-[25.5px] font-semibold text-parchment">
                <span className="mr-2 text-accent">{i + 1}.</span>
                {left.text}
              </p>
              <div role="group" aria-label={`${texts.matchPick} ${left.text}`} className="flex flex-wrap gap-2">
                {rights.map((right) => {
                  const active = chosen === right.id
                  const usedElsewhere = !active && Object.values(pairs).includes(right.id)
                  return (
                    <button
                      key={right.id}
                      type="button"
                      aria-pressed={active}
                      disabled={disabled}
                      onClick={() => pick(left.id, right.id)}
                      className={`min-h-12 rounded-xl border px-4 py-2 text-left text-base leading-6 font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
                        active
                          ? 'border-accent bg-accent text-oil'
                          : usedElsewhere
                            ? 'border-line bg-surface-2 text-dim'
                            : 'border-line-strong bg-surface-2 text-parchment'
                      }`}
                    >
                      {right.text}
                    </button>
                  )
                })}
              </div>
            </li>
          )
        })}
      </ol>
    </div>
  )
}

/** Поле відповіді за видом питання: варіанти (single/multiple), текст або відповідність. */
export default function QuestionInput(props: QuestionInputProps) {
  if (props.question.kind === 'text') return <TextQuestion {...props} />
  if (props.question.kind === 'match') return <MatchQuestion {...props} />
  return <ChoiceQuestion {...props} />
}
