import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link } from 'react-router'
import iconMail from '@/assets/auth/icon-mail.svg'
import arrowRight from '@/assets/register/icon-arrow-right.svg'
import iconSchool from '@/assets/register/icon-school.svg'
import iconUser from '@/assets/register/icon-user.svg'
import AuthLayout from '@/shared/ui/AuthLayout'
import { PasswordField, SelectField, TextField } from '@/shared/ui/Field'
import { roleOptions, schools } from './content'
import type { Role } from './content'

type Errors = Partial<Record<'firstName' | 'lastName' | 'email' | 'school' | 'password' | 'consent', string>>

const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/

function validate(v: {
  firstName: string
  lastName: string
  email: string
  school: string
  password: string
  consent: boolean
}): Errors {
  const errors: Errors = {}
  if (!v.firstName.trim()) errors.firstName = 'Вкажіть ім’я'
  if (!v.lastName.trim()) errors.lastName = 'Вкажіть прізвище'
  if (!emailRe.test(v.email.trim())) errors.email = 'Введіть пошту у форматі name@school.edu.ua'
  if (!v.school) errors.school = 'Оберіть школу'
  if (v.password.length < 8 || !/\p{L}/u.test(v.password) || !/\d/.test(v.password)) {
    errors.password = 'Літери й цифри, щонайменше 8 символів'
  }
  if (!v.consent) errors.consent = 'Потрібна згода з умовами'
  return errors
}

export default function RegisterPage() {
  const [role, setRole] = useState<Role>('teacher')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [email, setEmail] = useState('')
  const [school, setSchool] = useState('')
  const [password, setPassword] = useState('')
  const [consent, setConsent] = useState(false)
  const [errors, setErrors] = useState<Errors>({})

  function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const found = validate({ firstName, lastName, email, school, password, consent })
    setErrors(found)
    if (Object.keys(found).length > 0) return
    // TODO: API реєстрації ще немає. Коли зʼявиться, відправляти через єдиний шар даних
    // (RTK Query), а не fetch у компоненті.
  }

  return (
    <AuthLayout bubble="Дані дітей — мінімум і тільки за ролями. Обіцяю!">
      <p className="text-xs font-bold tracking-[2px] text-accent uppercase">Реєстрація</p>
      <h1 className="mt-2 font-heading text-[26px] leading-[1.25] text-parchment lg:text-[32px]">Створіть акаунт</h1>
      <p className="mt-2 text-[15px] leading-6 text-muted">
        Учні не реєструються самі — вчитель додає їх до класу, а вони входять за кодом.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-5">
        <fieldset className="flex flex-col gap-3">
          <legend className="mb-3 text-sm font-semibold text-parchment">Хто ви?</legend>
          <div className="flex flex-col gap-3 md:flex-row">
            {roleOptions.map((r) => (
              <label
                key={r.value}
                className="flex flex-1 cursor-pointer gap-3 rounded-[14px] border border-line bg-surface p-4 has-checked:border-accent has-checked:bg-surface-2 has-focus-visible:ring-2 has-focus-visible:ring-accent/40 md:flex-col md:gap-[7px]"
              >
                <span className="flex items-center gap-3 md:justify-between">
                  <input
                    type="radio"
                    name="role"
                    value={r.value}
                    checked={role === r.value}
                    onChange={() => setRole(r.value)}
                    className="size-4 shrink-0 appearance-none rounded-full border border-[#767676] bg-white outline-none checked:border-accent checked:bg-[radial-gradient(circle,var(--color-accent)_0_30%,#fff_34%)]"
                  />
                  <img src={r.icon} alt="" width={20} height={20} />
                </span>
                <span className="flex flex-col gap-[1.25px]">
                  <span className="text-[15px] leading-[22.5px] font-bold text-parchment">{r.title}</span>
                  <span className="text-xs leading-[16.5px] text-dim">{r.text}</span>
                </span>
              </label>
            ))}
          </div>
        </fieldset>

        <div className="grid gap-5 md:grid-cols-2">
          <TextField
            label="Ім’я"
            icon={iconUser}
            placeholder="Олена"
            autoComplete="given-name"
            value={firstName}
            onChange={(e) => setFirstName(e.target.value)}
            error={errors.firstName}
          />
          <TextField
            label="Прізвище"
            icon={iconUser}
            placeholder="Коваль"
            autoComplete="family-name"
            value={lastName}
            onChange={(e) => setLastName(e.target.value)}
            error={errors.lastName}
          />
        </div>

        <TextField
          label="Робоча пошта"
          icon={iconMail}
          type="email"
          placeholder="olena.koval@school12.edu.ua"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          error={errors.email}
        />

        <SelectField label="Школа" icon={iconSchool} value={school} onChange={(e) => setSchool(e.target.value)} error={errors.school}>
          <option value="" disabled>
            Оберіть школу
          </option>
          {schools.map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </SelectField>

        <PasswordField
          placeholder="Щонайменше 8 символів"
          autoComplete="new-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          hint="Літери й цифри, щонайменше 8 символів"
          error={errors.password}
        />

        <div>
          <label className="flex cursor-pointer items-start gap-3 text-sm leading-5 text-muted">
            <input
              type="checkbox"
              checked={consent}
              onChange={(e) => setConsent(e.target.checked)}
              aria-invalid={errors.consent ? true : undefined}
              className="mt-0.5 size-5 shrink-0 rounded-[2.5px] accent-accent"
            />
            <span>
              Погоджуюсь з <span className="underline">умовами</span> та{' '}
              <span className="underline">політикою приватності</span>
            </span>
          </label>
          {errors.consent && <p className="mt-2 text-xs text-danger">{errors.consent}</p>}
        </div>

        <button
          type="submit"
          className="flex h-14 items-center justify-center gap-2 rounded-[10px] bg-accent font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none"
        >
          Зареєструватися
          <img src={arrowRight} alt="" width={20} height={20} />
        </button>
      </form>

      <p className="mt-6 text-sm text-muted">
        Уже маєте акаунт?{' '}
        <Link to="/login" className="rounded font-semibold hover:text-parchment">
          Увійти
        </Link>
      </p>
    </AuthLayout>
  )
}
