import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link } from 'react-router'
import iconGoogle from '@/assets/auth/icon-google.svg'
import iconKey from '@/assets/auth/icon-key.svg'
import iconMail from '@/assets/auth/icon-mail.svg'
import AuthLayout from '@/shared/ui/AuthLayout'
import { PasswordField, TextField } from '@/shared/ui/Field'
import { loginRoles } from './content'
import type { LoginRole } from './content'

const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const altButton =
  'flex h-12 items-center justify-center gap-3 rounded-[10px] border border-line-strong text-[15px] font-semibold text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none'

export default function LoginPage() {
  const [role, setRole] = useState<LoginRole>('teacher')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})

  function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const found: typeof errors = {}
    if (!emailRe.test(email.trim())) found.email = 'Введіть пошту у форматі name@school.edu.ua'
    if (!password) found.password = 'Введіть пароль'
    setErrors(found)
    if (Object.keys(found).length > 0) return
    // TODO: API входу ще немає. Коли зʼявиться, відправляти через єдиний шар даних
    // (RTK Query), а не fetch у компоненті. Прапорець «Запамʼятати для офлайн-входу» (remember)
    // має керувати збереженням даних для входу без мережі.
  }

  return (
    <AuthLayout bubble="Привіт! Я Кріт. Увійди — і продовжимо маршрут.">
      <p className="text-xs font-bold tracking-[2px] text-accent uppercase">Вхід</p>
      <h1 className="mt-2 font-heading text-[36px] leading-[1.15] tracking-[-0.56px] text-parchment md:text-[56px]">
        З поверненням
      </h1>
      <p className="mt-2 text-[15px] leading-6 text-muted">
        Увійдіть, щоб завантажити пакет уроків і бути готовими до тривоги.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-5">
        <fieldset>
          <legend className="sr-only">Роль</legend>
          <div className="flex gap-1 rounded-xl border border-line bg-surface p-1">
            {loginRoles.map((r) => (
              <label
                key={r.value}
                className="flex h-10 flex-1 cursor-pointer items-center justify-center rounded-lg text-[13px] font-semibold text-muted has-checked:bg-surface-2 has-checked:text-accent has-checked:shadow-[inset_0_0_0_1px_var(--color-line-strong)] has-focus-visible:ring-2 has-focus-visible:ring-accent/40 md:text-sm"
              >
                <input
                  type="radio"
                  name="role"
                  value={r.value}
                  checked={role === r.value}
                  onChange={() => setRole(r.value)}
                  className="sr-only"
                />
                {r.label}
              </label>
            ))}
          </div>
        </fieldset>

        <TextField
          label="Електронна пошта"
          icon={iconMail}
          type="email"
          placeholder="olena.koval@school12.edu.ua"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />

        <PasswordField
          placeholder="Щонайменше 8 символів"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          error={errors.password}
        />

        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <label className="flex cursor-pointer items-center gap-3 text-sm text-muted">
            <input
              type="checkbox"
              checked={remember}
              onChange={(e) => setRemember(e.target.checked)}
              className="size-5 shrink-0 rounded-[2.5px] accent-accent"
            />
            Запам’ятати для офлайн-входу
          </label>
          <button type="button" className="self-start rounded text-sm font-semibold text-muted hover:text-parchment">
            Забули пароль?
          </button>
        </div>

        <button
          type="submit"
          className="flex h-14 items-center justify-center rounded-[10px] bg-accent font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none"
        >
          Увійти
        </button>
      </form>

      <div className="mt-4 flex items-center gap-4 pt-4" aria-hidden="true">
        <span className="h-px flex-1 bg-line-soft" />
        <span className="text-xs text-dim">або</span>
        <span className="h-px flex-1 bg-line-soft" />
      </div>

      <div className="mt-4 flex flex-col gap-3">
        <button type="button" className={altButton}>
          <img src={iconGoogle} alt="" width={20} height={20} />
          Увійти через Google
        </button>
        <button type="button" className={altButton}>
          <img src={iconKey} alt="" width={18} height={18} />
          Я учень — увійти за кодом класу
        </button>
      </div>

      <p className="mt-6 text-sm text-muted">
        Ще немає акаунта?{' '}
        <Link to="/register" className="rounded font-semibold hover:text-parchment">
          Зареєструватися
        </Link>
      </p>
    </AuthLayout>
  )
}
