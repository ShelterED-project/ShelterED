import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { Link } from 'react-router'
import iconKey from '@/assets/auth/icon-key.svg'
import arrowRight from '@/assets/register/icon-arrow-right.svg'
import iconUser from '@/assets/register/icon-user.svg'
import { useStudentJoin } from '@/features/auth/useStudentJoin'
import AuthLayout from '@/shared/ui/AuthLayout'
import { PasswordField, TextField } from '@/shared/ui/Field'

type Errors = Partial<Record<'joinCode' | 'firstName' | 'lastName' | 'pin', string>>

function validate(v: { joinCode: string; firstName: string; lastName: string; pin: string }): Errors {
  const errors: Errors = {}
  if (!v.joinCode.trim()) errors.joinCode = 'Введіть код класу'
  const first = v.firstName.trim()
  const last = v.lastName.trim()
  if (!first) errors.firstName = 'Вкажіть ім’я'
  else if (first.length > 50) errors.firstName = 'Не більше 50 символів'
  if (!last) errors.lastName = 'Вкажіть прізвище'
  else if (last.length > 50) errors.lastName = 'Не більше 50 символів'
  if (!/^\d{4,6}$/.test(v.pin)) errors.pin = 'PIN — від 4 до 6 цифр'
  return errors
}

export default function RegisterPage() {
  const [joinCode, setJoinCode] = useState('')
  const [firstName, setFirstName] = useState('')
  const [lastName, setLastName] = useState('')
  const [pin, setPin] = useState('')
  const [errors, setErrors] = useState<Errors>({})
  const { submit, loading, error } = useStudentJoin()

  async function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const found = validate({ joinCode, firstName, lastName, pin })
    setErrors(found)
    if (Object.keys(found).length > 0) return
    await submit({
      join_code: joinCode.trim(),
      display_name: firstName.trim(),
      last_name: lastName.trim(),
      pin,
    })
  }

  return (
    <AuthLayout bubble="Дані дітей — мінімум і тільки за ролями. Обіцяю!">
      <p className="text-xs font-bold tracking-[2px] text-accent uppercase">Для учнів</p>
      <h1 className="mt-2 font-heading text-[26px] leading-[1.25] text-parchment lg:text-[32px]">
        Увійти за кодом класу
      </h1>
      <p className="mt-2 text-[15px] leading-6 text-muted">
        Код класу дає вчитель. Уперше вводиш ім’я й вигадуєш PIN, наступного разу вводиш той самий.
      </p>

      <form onSubmit={onSubmit} noValidate className="mt-6 flex flex-col gap-5">
        <TextField
          label="Код класу"
          icon={iconKey}
          placeholder="Наприклад, KLASS7A"
          autoComplete="off"
          autoCapitalize="characters"
          value={joinCode}
          onChange={(e) => setJoinCode(e.target.value)}
          error={errors.joinCode}
        />

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

        <PasswordField
          label="PIN"
          placeholder="4–6 цифр"
          inputMode="numeric"
          maxLength={6}
          autoComplete="off"
          value={pin}
          onChange={(e) => setPin(e.target.value.replace(/\D/g, ''))}
          hint="Запам’ятай PIN: він потрібен для наступного входу"
          error={errors.pin}
        />

        {error && (
          <p role="alert" className="text-sm text-danger">
            {error}
          </p>
        )}

        <button
          type="submit"
          disabled={loading}
          className="flex h-14 items-center justify-center gap-2 rounded-[10px] bg-accent font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
        >
          {loading ? 'Входимо…' : 'Увійти'}
          <img src={arrowRight} alt="" width={20} height={20} />
        </button>
      </form>

      <p className="mt-6 text-sm text-muted">
        Ви вчитель, батьки чи адміністрація?{' '}
        <Link to="/login" className="rounded font-semibold hover:text-parchment">
          Увійти з поштою
        </Link>
      </p>
    </AuthLayout>
  )
}
