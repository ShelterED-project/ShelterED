import { useState } from 'react'
import type { FormEvent } from 'react'
import { useUpdateLessonMutation } from '@/features/teacher/lessonEditorApi'
import type { LessonFields, LessonOut } from '@/features/teacher/lessonEditorApi'
import { useSubjectsQuery } from '@/features/teacher/teacherApi'
import Spinner from '@/shared/ui/Spinner'
import { editor } from './content'
import { card, field, primaryButton, textarea } from './styles'
import { useAction } from './useAction'

const GRADES = Array.from({ length: 11 }, (_, i) => i + 1)

function fieldsOf(lesson: LessonOut): LessonFields {
  return {
    title: lesson.title,
    subject_id: lesson.subject_id,
    grade: lesson.grade,
    shelter_part: lesson.shelter_part,
    main_part: lesson.main_part,
  }
}

/** Назва, предмет, клас і тексти уроку. Зберігає лише змінені поля (PATCH). */
export default function LessonDetails({ lesson, readOnly }: { lesson: LessonOut; readOnly: boolean }) {
  const t = editor.details
  const { data: subjects } = useSubjectsQuery()
  const [update] = useUpdateLessonMutation()
  const { busy, error, run } = useAction()
  const [form, setForm] = useState<LessonFields>(() => fieldsOf(lesson))
  const [savedAt, setSavedAt] = useState<number | null>(null)

  // Після збереження сервер повертає урок: якщо поле не змінювали, підхоплюємо нове значення.
  const [base, setBase] = useState<LessonFields>(() => fieldsOf(lesson))
  const fresh = fieldsOf(lesson)
  if (JSON.stringify(fresh) !== JSON.stringify(base)) {
    setBase(fresh)
    setForm(fresh)
  }

  const patch: Partial<LessonFields> = {}
  for (const key of Object.keys(form) as (keyof LessonFields)[]) {
    if (form[key] !== base[key]) Object.assign(patch, { [key]: key === 'title' ? form.title.trim() : form[key] })
  }
  const dirty = Object.keys(patch).length > 0

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (await run(() => update({ id: lesson.id, patch }).unwrap())) setSavedAt(Date.now())
  }

  const set = <K extends keyof LessonFields>(key: K, value: LessonFields[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }))
    setSavedAt(null)
  }

  return (
    <form onSubmit={(e) => void submit(e)} className={card}>
      <h2 className="font-heading text-xl leading-7 text-parchment">{t.title}</h2>
      <fieldset disabled={readOnly || busy} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.name}
          <input required maxLength={200} value={form.title} onChange={(e) => set('title', e.target.value)} className={field} />
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-muted">
            {t.subject}
            <select value={form.subject_id} onChange={(e) => set('subject_id', e.target.value)} className={field}>
              {(subjects ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm text-muted">
            {t.grade}
            <select
              value={form.grade ?? ''}
              onChange={(e) => set('grade', e.target.value ? Number(e.target.value) : null)}
              className={field}
            >
              <option value="">{t.noGrade}</option>
              {GRADES.map((g) => (
                <option key={g} value={g}>
                  {g}
                </option>
              ))}
            </select>
          </label>
        </div>
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.shelterPart}
          <span className="text-xs text-dim">{t.shelterHint}</span>
          <textarea
            maxLength={20000}
            value={form.shelter_part}
            onChange={(e) => set('shelter_part', e.target.value)}
            className={textarea}
          />
        </label>
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.mainPart}
          <span className="text-xs text-dim">{t.mainHint}</span>
          <textarea maxLength={20000} value={form.main_part} onChange={(e) => set('main_part', e.target.value)} className={textarea} />
        </label>
      </fieldset>
      {error && (
        <p role="alert" className="text-sm font-semibold text-accent">
          {error}
        </p>
      )}
      {!readOnly && (
        <div className="flex items-center gap-3">
          <button type="submit" disabled={busy || !dirty || !form.title.trim()} className={primaryButton}>
            {busy && <Spinner />}
            {busy ? editor.saving : editor.save}
          </button>
          {savedAt && !dirty && (
            <span role="status" className="text-sm text-safe">
              {editor.saved}
            </span>
          )}
        </div>
      )}
    </form>
  )
}
