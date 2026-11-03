import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link } from 'react-router'
import iconGoogle from '@/assets/auth/icon-google.svg'
import iconKey from '@/assets/auth/icon-key.svg'
import iconMail from '@/assets/auth/icon-mail.svg'
import { useAdultLogin } from '@/features/auth/useAdultLogin'
import AuthLayout from '@/shared/ui/AuthLayout'
import { PasswordField, TextField } from '@/shared/ui/Field'

const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

const altButton =
  'flex h-12 items-center justify-center gap-3 rounded-[10px] border border-line-strong text-[15px] font-semibold text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none'

export default function LoginPage() {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(true)
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({})
  const { login, loading, error } = useAdultLogin()

  async function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const found: typeof errors = {}
    if (!emailRe.test(email.trim())) found.email = 'Введіть пошту у форматі name@school.edu.ua'
    if (!password) found.password = 'Введіть пароль'
    setErrors(found)
    if (Object.keys(found).length > 0) return
    // «Запамʼятати для офлайн-входу» керує збереженням сесії в IndexedDB.
    await login(email.trim(), password, remember)
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

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex h-14 items-center justify-center rounded-[10px] bg-accent font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
        >
          {loading ? 'Входимо…' : 'Увійти'}
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
        <Link to="/register" className={altButton}>
          <img src={iconKey} alt="" width={18} height={18} />
          Я учень — увійти за кодом класу
        </Link>
      </div>

      <p className="mt-6 text-sm text-muted">
        Акаунти вчителів, батьків і адміністрації створює адміністрація школи.
      </p>
    </AuthLayout>
  )
}
