import { useUpdateLessonMutation } from '@/features/teacher/lessonEditorApi'
import type { LessonFields, LessonOut } from '@/features/teacher/lessonEditorApi'
import { useSubjectsQuery } from '@/features/teacher/teacherApi'
import { editor } from './content'
import FieldStatus from './FieldStatus'
import { card, field, textarea } from './styles'
import { useAutosave } from './useAutosave'

const GRADES = Array.from({ length: 11 }, (_, i) => i + 1)

/** Одне поле уроку з автозбереженням (PATCH лише цього поля). */
function useLessonField<K extends keyof LessonFields>(lesson: LessonOut, key: K, readOnly: boolean, delay?: number) {
  const [update] = useUpdateLessonMutation()
  return useAutosave<LessonFields[K]>({
    draftKey: `lesson:${lesson.id}:${key}`,
    server: lesson[key],
    disabled: readOnly,
    delay,
    isValid: key === 'title' ? (v) => String(v).trim() !== '' : undefined,
    save: (value) =>
      update({
        id: lesson.id,
        patch: { [key]: typeof value === 'string' && key === 'title' ? value.trim() : value } as Partial<LessonFields>,
      }).unwrap(),
  })
}

/** Назва, предмет, клас і тексти уроку. Усе зберігається саме, без кнопки. */
export default function LessonDetails({ lesson, readOnly }: { lesson: LessonOut; readOnly: boolean }) {
  const t = editor.details
  const { data: subjects } = useSubjectsQuery()
  const title = useLessonField(lesson, 'title', readOnly)
  const subject = useLessonField(lesson, 'subject_id', readOnly, 0)
  const grade = useLessonField(lesson, 'grade', readOnly, 0)
  const shelter = useLessonField(lesson, 'shelter_part', readOnly)
  const main = useLessonField(lesson, 'main_part', readOnly)

  return (
    <section className={card}>
      <h2 className="font-heading text-xl leading-7 text-parchment">{t.title}</h2>
      <fieldset disabled={readOnly} className="flex flex-col gap-4">
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.name}
          <input
            maxLength={200}
            value={title.value}
            onChange={(e) => title.set(e.target.value)}
            onBlur={title.flush}
            className={field}
          />
          <FieldStatus status={title.status} error={title.error} />
        </label>
        <div className="grid gap-4 md:grid-cols-2">
          <label className="flex flex-col gap-1 text-sm text-muted">
            {t.subject}
            <select value={subject.value} onChange={(e) => subject.set(e.target.value)} className={field}>
              {(subjects ?? []).map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            <FieldStatus status={subject.status} error={subject.error} />
          </label>
          <label className="flex flex-col gap-1 text-sm text-muted">
            {t.grade}
            <select
              value={grade.value ?? ''}
              onChange={(e) => grade.set(e.target.value ? Number(e.target.value) : null)}
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
        <label id="field-shelter_part" className="flex flex-col gap-1 rounded-[12px] text-sm text-muted">
          {t.shelterPart}
          <span className="text-xs text-dim">{t.shelterHint}</span>
          <textarea
            maxLength={20000}
            value={shelter.value}
            placeholder={t.shelterPlaceholder}
            onChange={(e) => shelter.set(e.target.value)}
            onBlur={shelter.flush}
            className={textarea}
          />
          <FieldStatus status={shelter.status} error={shelter.error} />
        </label>
        <label className="flex flex-col gap-1 text-sm text-muted">
          {t.mainPart}
          <span className="text-xs text-dim">{t.mainHint}</span>
          <textarea
            maxLength={20000}
            value={main.value}
            onChange={(e) => main.set(e.target.value)}
            onBlur={main.flush}
            className={textarea}
          />
          <FieldStatus status={main.status} error={main.error} />
        </label>
      </fieldset>
    </section>
  )
}
