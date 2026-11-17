import { useState } from 'react'
import type { SubmitEvent } from 'react'
import iconSchool from '@/assets/register/icon-school.svg'
import type { ClassFields } from '@/features/admin/adminApi'
import { currentAcademicYear } from '@/features/admin/format'
import { SelectField, TextField } from '@/shared/ui/Field'
import { classesPage } from '../content'

const t = classesPage.form
const YEAR_RE = /^\d{4}\/\d{4}$/
const grades = Array.from({ length: 11 }, (_, i) => i + 1)

type Props = {
  initial?: ClassFields
  submitLabel: string
  busy: boolean
  error?: string
  onSubmit: (fields: ClassFields) => void
  onCancel?: () => void
}

export default function ClassForm({ initial, submitLabel, busy, error, onSubmit, onCancel }: Props) {
  const [name, setName] = useState(initial?.name ?? '')
  const [grade, setGrade] = useState(initial?.grade ?? 5)
  const [year, setYear] = useState(initial?.academic_year ?? currentAcademicYear())
  const [errors, setErrors] = useState<{ name?: string; year?: string }>({})

  function submit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    const found = {
      name: name.trim() ? undefined : t.nameRequired,
      year: YEAR_RE.test(year.trim()) ? undefined : t.yearInvalid,
    }
    setErrors(found)
    if (found.name || found.year) return
    onSubmit({ name: name.trim(), grade, academic_year: year.trim() })
  }

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-4">
      <div className="grid gap-4 md:grid-cols-3">
        <TextField
          label={t.name}
          icon={iconSchool}
          placeholder={t.namePlaceholder}
          maxLength={50}
          autoComplete="off"
          value={name}
          onChange={(e) => setName(e.target.value)}
          error={errors.name}
        />
        <SelectField label={t.grade} icon={iconSchool} value={grade} onChange={(e) => setGrade(Number(e.target.value))}>
          {grades.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </SelectField>
        <TextField
          label={t.year}
          icon={iconSchool}
          hint={t.yearHint}
          inputMode="numeric"
          autoComplete="off"
          value={year}
          onChange={(e) => setYear(e.target.value)}
          error={errors.year}
        />
      </div>
      {error && (
        <p role="alert" className="text-sm text-danger">
          {error}
        </p>
      )}
      <div className="flex gap-3">
        <button
          type="submit"
          disabled={busy}
          className="h-11 rounded-[10px] bg-accent px-5 text-sm font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
        >
          {submitLabel}
        </button>
        {onCancel && (
          <button
            type="button"
            onClick={onCancel}
            className="h-11 rounded-[10px] border border-line-strong px-5 text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {t.cancel}
          </button>
        )}
      </div>
    </form>
  )
}
