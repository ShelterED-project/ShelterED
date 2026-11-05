import { useEffect, useRef, useState } from 'react'
import type { SubmitEvent } from 'react'
import iconMail from '@/assets/auth/icon-mail.svg'
import iconSchool from '@/assets/register/icon-school.svg'
import iconUser from '@/assets/register/icon-user.svg'
import { useCreateUserMutation } from '@/features/auth/authApi'
import { getErrorMessage } from '@/features/auth/errors'
import type { AdminCreateUserRequest } from '@/features/auth/types'
import { PasswordField, SelectField, TextField } from '@/shared/ui/Field'

type Role = AdminCreateUserRequest['role']
type Errors = Partial<Record<'firstName' | 'lastName' | 'email' | 'password', string>>

const roles: { value: Role; label: string }[] = [
  { value: 'teacher', label: 'Вчитель' },
  { value: 'parent', label: 'Батьки' },
  { value: 'admin', label: 'Адміністрація' },
]

const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(v: { firstName: string; lastName: string; email: string; password: string }): Errors {
  const errors: Errors = {}
  const first = v.firstName.trim()
  const last = v.lastName.trim()
  const email = v.email.trim()
  if (!first) errors.firstName = 'Вкажіть ім’я'
  else if (first.length > 50) errors.firstName = 'Не більше 50 символів'
  if (last.length > 50) errors.lastName = 'Не більше 50 символів'
  if (!emailRe.test(email) || email.length > 254) errors.email = 'Введіть пошту у форматі name@school.edu.ua'
  if (v.password.length < 8 || v.password.length > 128) errors.password = 'Від 8 до 128 символів'
  return errors
}

type Props = { open: boolean; onClose: () => void }

export default function CreateUserDialog({ open, onClose }: Props) {
  const ref = useRef<HTMLDialogElement>(null)
  const [role, setRole] = useState<Role>('teacher')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const [created, setCreated] = useState<string>()
  const [createUser, { isLoading, error, reset }] = useCreateUserMutation()

  useEffect(() => {
    const dialog = ref.current
    if (!dialog) return
    if (open && !dialog.open) dialog.showModal()
    if (!open && dialog.open) dialog.close()
  }, [open])

  function close() {
    setErrors({})
    setCreated(undefined)
    reset()
    onClose()
  }

  async function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    setCreated(undefined)
    const found = validate({ firstName, lastName, email, password })
    setErrors(found)
    if (Object.keys(found).length > 0) return
    try {
      const user = await createUser({
        email: email.trim(),
        display_name: firstName.trim(),
        last_name: lastName.trim() || undefined,
        role,
        password,
      }).unwrap()
      setCreated(`${user.display_name} ${user.last_name ?? ''}`.trim())
      setFirstName('')
      setLastName('')
      setEmail('')
      setPassword('')
    } catch {
      // Текст помилки береться зі стану мутації.
    }
  }

  return (
    <dialog
      ref={ref}
      onClose={close}
      onClick={(e) => e.target === ref.current && close()}
      aria-labelledby="create-user-title"
      className="m-auto w-[calc(100%-2.5rem)] max-w-[480px] rounded-[22px] border border-line bg-surface p-0 text-parchment backdrop:bg-oil/80"
    >
      <form onSubmit={onSubmit} noValidate className="flex flex-col gap-5 p-5 md:p-6">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 id="create-user-title" className="font-heading text-xl leading-7 text-parchment md:text-[22px]">
              Додати користувача
            </h2>
            <p className="mt-1 text-sm leading-5 text-dim">
              Акаунт у вашій школі. Пароль передайте користувачу самостійно.
            </p>
          </div>
          <button
            type="button"
            onClick={close}
            aria-label="Закрити"
            className="flex size-9 shrink-0 items-center justify-center rounded-lg text-muted hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            ✕
          </button>
        </div>

        <SelectField label="Роль" icon={iconSchool} value={role} onChange={(e) => setRole(e.target.value as Role)}>
          {roles.map((r) => (
            <option key={r.value} value={r.value}>
              {r.label}
            </option>
          ))}
        </SelectField>

        <div className="grid gap-5 sm:grid-cols-2">
          <TextField
            label="Ім’я"
            icon={iconUser}
            autoComplete="off"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            error={errors.firstName}
          />
          <TextField
            label="Прізвище"
            icon={iconUser}
            autoComplete="off"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            error={errors.lastName}
          />
        </div>

        <TextField
          label="Електронна пошта"
          icon={iconMail}
          type="email"
          autoComplete="off"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />

        <PasswordField
          label="Початковий пароль"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint="Від 8 символів"
          error={errors.password}
        />

        {error && (
          <p role="alert" className="text-sm text-danger">
            {getErrorMessage(error)}
          </p>
        )}
        {created && (
          <p role="status" className="text-sm text-parchment">
            Користувача {created} створено. Можна додати наступного.
          </p>
        )}

        <button
          type="submit"
          disabled={isLoading}
          className="flex h-12 items-center justify-center rounded-[10px] bg-accent font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
        >
          {isLoading ? 'Створюємо…' : 'Створити'}
        </button>
      </form>
    </dialog>
  )
}
