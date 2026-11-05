import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { useParentLinkMutation } from '@/features/auth/authApi'
import { getErrorMessage } from '@/features/auth/errors'
import type { ParentLinkResponse } from '@/features/auth/types'

export default function LinkChild() {
  const [code, setCode] = useState('')
  const [fieldError, setFieldError] = useState<string>()
  const [linked, setLinked] = useState<ParentLinkResponse[]>([])
  const [link, { isLoading, error }] = useParentLinkMutation()

  async function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const value = code.trim()
    if (!value) {
      setFieldError('Введіть код від вчителя')
      return
    }
    setFieldError(undefined)
    try {
      const child = await link({ code: value }).unwrap()
      // Повторний виклик з тим самим кодом ідемпотентний: не дублюємо дитину в списку.
      setLinked((prev) => (prev.some((c) => c.child_id === child.child_id) ? prev : [...prev, child]))
      setCode('')
    } catch {
      // Текст помилки береться зі стану мутації нижче.
    }
  }

  const message = fieldError ?? (error ? getErrorMessage(error) : undefined)

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <div>
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
          Додати дитину
        </h2>
        <p className="mt-1 text-sm leading-5 text-dim">Код дає класний керівник. Він діє 7 днів.</p>
      </div>

      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-3 sm:flex-row">
        <div className="flex-1">
          <label htmlFor="link-code" className="sr-only">
            Код від вчителя
          </label>
          <input
            id="link-code"
            value={code}
            onChange={(e) => setCode(e.target.value)}
            maxLength={32}
            autoComplete="off"
            placeholder="Код від вчителя"
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
          {isLoading ? 'Перевіряємо…' : 'Додати'}
        </button>
      </form>

      {message && (
        <p id="link-code-error" role="alert" className="text-sm text-danger">
          {message}
        </p>
      )}

      {linked.length > 0 && (
        <ul className="flex flex-col gap-2" aria-label="Прив’язані діти">
          {linked.map((c) => (
            <li key={c.child_id} role="status" className="text-sm text-parchment">
              Дитину {c.display_name} {c.last_name} додано.
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
