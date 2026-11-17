import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { useParentLinkMutation } from '@/features/auth/authApi'
import { getErrorMessage } from '@/features/auth/errors'
import { childName } from '@/features/parent/useParentChildren'
import { linkChild as t } from '../content'

type Props = {
  /** Нова дитина стає вибраною */
  onLinked: (childId: string) => void
  /** Дітей ще немає: картка стає головною на сторінці */
  empty?: boolean
}

export default function LinkChild({ onLinked, empty = false }: Props) {
  const [code, setCode] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [added, setAdded] = useState<string>()
  const [link, { isLoading, error }] = useParentLinkMutation()

  async function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const value = code.trim()
    if (!value) {
      setFieldError(t.required)
      return
    }
    setFieldError(undefined)
    setAdded(undefined)
    try {
      // Повторний виклик з тим самим кодом ідемпотентний; список дітей оновиться за тегом Children.
      const child = await link({ code: value }).unwrap()
      setAdded(childName(child))
      setCode('')
      onLinked(child.child_id)
    } catch {
      // Текст помилки береться зі стану мутації нижче.
    }
  }

  const message = fieldError ?? (error ? getErrorMessage(error) : undefined)

  return (
    <section
      className={`flex flex-col gap-4 rounded-[22px] border bg-surface p-5 md:p-6 ${empty ? 'border-accent/50' : 'border-line'}`}
    >
      <div>
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
          {empty ? t.emptyTitle : t.title}
        </h2>
        <p className="mt-1 text-sm leading-5 text-dim">{empty ? t.emptyText : t.text}</p>
      </div>

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <label htmlFor="link-code" className="sr-only">
            {t.placeholder}
          </label>
          <input
            id="link-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={32}
            autoComplete="off"
            autoCapitalize="characters"
            placeholder={t.placeholder}
            aria-invalid={message ? true : undefined}
            aria-describedby={message ? 'link-code-error' : undefined}
            className={`h-12 w-full rounded-[10px] border bg-oil px-4 text-base text-parchment outline-none placeholder:text-dim focus:border-accent focus-visible:ring-2 focus-visible:ring-accent/40 ${message ? 'border-danger' : 'border-line'}`}
          />
        </div>
        <button
          type="submit"
          disabled={isLoading}
          className="flex h-12 items-center justify-center rounded-[10px] bg-accent px-6 font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
        >
          {isLoading ? t.submitting : t.submit}
        </button>
      </form>

      {message && (
        <p id="link-code-error" role="alert" className="text-sm text-danger">
          {message}
        </p>
      )}
      {added && (
        <p role="status" className="text-sm text-safe">
          {t.added(added)}
        </p>
      )}
    </section>
  )
}
