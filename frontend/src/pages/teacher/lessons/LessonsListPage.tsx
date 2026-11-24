import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { errorMessage, useCreateLessonMutation } from '@/features/teacher/lessonEditorApi'
import { useLessonsQuery, useSchoolLessonsQuery, useSubjectsQuery } from '@/features/teacher/teacherApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import TeacherHeader from '../sections/TeacherHeader'
import TeacherSidebar from '../sections/TeacherSidebar'
import TeacherTabs from '../sections/TeacherTabs'
import { guideSteps, lessonsList, lessonStatus, newLesson } from './content'
import { field, primaryButton, secondaryButton } from './styles'
import { useCopyLesson } from './useCopyLesson'

const LAST_SUBJECT = 'teacher.lastSubject'

function lastSubject(): string {
  try {
    return localStorage.getItem(LAST_SUBJECT) ?? ''
  } catch {
    return ''
  }
}

function NewLessonForm({ onCancel }: { onCancel: () => void }) {
  const { data: subjects } = useSubjectsQuery()
  const [create, { isLoading }] = useCreateLessonMutation()
  const navigate = useNavigate()
  // Предмет за замовчуванням — останній обраний (або єдиний): на один вибір менше.
  const [picked, setPicked] = useState(lastSubject)
  const list = subjects ?? []
  const subjectId = list.some((s) => s.id === picked) ? picked : list.length === 1 ? (list[0]?.id ?? '') : ''
  const setSubjectId = setPicked
  const [title, setTitle] = useState('')
  const [error, setError] = useState<string | null>(null)
  // id уроку створюємо один раз на форму: повторне натискання після обриву мережі не дасть дубля.
  const [id] = useState(generateId)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await create({ id, subject_id: subjectId, title: title.trim(), shelter_part: '', main_part: '', grade: null }).unwrap()
      try {
        localStorage.setItem(LAST_SUBJECT, subjectId)
      } catch {
        // Без сховища просто не запамʼятаємо.
      }
      navigate(`/teacher/lessons/${id}`)
    } catch (err) {
      setError(errorMessage(err))
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="flex flex-col gap-4 rounded-[22px] border border-accent/40 bg-surface-2 p-5 md:p-6">
      <h2 className="font-heading text-xl leading-7 text-parchment">{newLesson.title}</h2>
      <label className="flex flex-col gap-1 text-sm text-muted">
        {newLesson.subject}
        <select required value={subjectId} onChange={(e) => setSubjectId(e.target.value)} className={field}>
          <option value="" disabled>
            {newLesson.chooseSubject}
          </option>
          {(subjects ?? []).map((s) => (
            <option key={s.id} value={s.id}>
              {s.name}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-sm text-muted">
        {newLesson.name}
        <input
          required
          autoFocus
          maxLength={200}
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          placeholder={newLesson.namePlaceholder}
          className={field}
        />
      </label>
      {error && (
        <p role="alert" className="text-sm font-semibold text-accent">
          {error}
        </p>
      )}
      <div className="flex flex-col gap-2 md:flex-row">
        <button type="submit" disabled={isLoading || !subjectId || !title.trim()} className={primaryButton}>
          {isLoading && <Spinner />}
          {isLoading ? newLesson.creating : newLesson.submit}
        </button>
        <button type="button" onClick={onCancel} disabled={isLoading} className={secondaryButton}>
          {newLesson.cancel}
        </button>
      </div>
    </form>
  )
}

export default function LessonsListPage() {
  const lessons = useLessonsQuery()
  const { data: subjects } = useSubjectsQuery()
  const { data: colleagues } = useSchoolLessonsQuery()
  const [creating, setCreating] = useState(false)
  const copy = useCopyLesson()
  const subjectName = new Map((subjects ?? []).map((s) => [s.id, s.name]))

  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="lessons" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <div className="flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="flex flex-col gap-1">
              <h1 className="font-heading text-2xl leading-[30px] text-parchment">{lessonsList.title}</h1>
              <p className="text-sm text-dim">{lessonsList.subtitle}</p>
            </div>
            {!creating && (
              <button type="button" onClick={() => setCreating(true)} className={primaryButton}>
                {lessonsList.create}
              </button>
            )}
          </div>

          {creating && <NewLessonForm onCancel={() => setCreating(false)} />}

          {lessons.data && lessons.data.length === 0 && !creating ? (
            <section className="flex flex-col gap-4 rounded-[22px] border border-accent/40 bg-surface p-5 md:p-6">
              <h2 className="font-heading text-xl leading-7 text-parchment">{lessonsList.emptyTitle}</h2>
              <p className="text-sm text-muted">{lessonsList.emptyText}</p>
              {colleagues && colleagues.length > 0 && <p className="text-sm text-muted">{lessonsList.emptyColleagues}</p>}
              <ol className="grid gap-3 md:grid-cols-3">
                {guideSteps.map((step, i) => (
                  <li key={step.title} className="flex flex-col gap-1 rounded-2xl border border-line-soft bg-surface-2 p-4">
                    <p className="text-xs font-semibold tracking-[0.96px] text-accent uppercase">{i + 1}</p>
                    <p className="text-[17px] font-semibold text-parchment">{step.title}</p>
                    <p className="text-sm text-muted">{step.text}</p>
                  </li>
                ))}
              </ol>
              <button type="button" onClick={() => setCreating(true)} className={`${primaryButton} self-start`}>
                {lessonsList.create}
              </button>
            </section>
          ) : !lessons.data || lessons.data.length === 0 ? (
            <p role="status" className="text-sm text-muted">
              {lessons.isLoading ? lessonsList.loading : lessons.isError ? lessonsList.offline : ''}
            </p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {lessons.data.map((lesson) => (
                <li key={lesson.id} className="flex flex-col rounded-2xl border border-line bg-surface hover:bg-surface-2">
                  <Link
                    to={`/teacher/lessons/${lesson.id}`}
                    className="flex flex-1 flex-col gap-2 rounded-t-2xl p-4 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
                  >
                    <span className="flex items-center justify-between gap-2 text-xs text-dim">
                      <span className="truncate">{subjectName.get(lesson.subject_id) ?? '—'}</span>
                      <span
                        className={`shrink-0 rounded-md px-2 py-0.5 font-semibold ${
                          lesson.status === 'published' ? 'bg-safe/15 text-safe' : 'bg-accent-soft text-accent'
                        }`}
                      >
                        {lessonStatus[lesson.status]}
                      </span>
                    </span>
                    <span className="text-[15px] leading-[22.5px] font-semibold text-parchment">{lesson.title}</span>
                    <span className="text-xs text-dim">
                      {lessonsList.updated(new Date(lesson.updated_at).toLocaleDateString('uk-UA'))} ·{' '}
                      {lessonsList.version(lesson.version)}
                    </span>
                  </Link>
                  <div className="flex items-center justify-end gap-2 border-t border-line-soft px-2 py-1">
                    {copy.error?.id === lesson.id && (
                      <p role="alert" className="flex-1 px-2 text-xs font-semibold text-accent">
                        {copy.error.message}
                      </p>
                    )}
                    <button
                      type="button"
                      title={lessonsList.copyHint}
                      disabled={copy.busyId !== null}
                      onClick={() => void copy.run(lesson)}
                      className="inline-flex min-h-10 items-center gap-2 rounded-[10px] px-3 text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50"
                    >
                      {copy.busyId === lesson.id && <Spinner />}
                      {copy.busyId === lesson.id ? lessonsList.copying : lessonsList.copy}
                    </button>
                  </div>
                </li>
              ))}
            </ul>
          )}

          {colleagues && colleagues.length > 0 && (
            <section className="flex flex-col gap-3">
              <div className="flex flex-col gap-1">
                <h2 className="font-heading text-xl leading-7 text-parchment">{lessonsList.colleaguesTitle}</h2>
                <p className="text-sm text-dim">{lessonsList.colleaguesHint}</p>
              </div>
              <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
                {colleagues.map((lesson) => (
                  <li key={lesson.id} className="flex flex-col rounded-2xl border border-line bg-surface">
                    <div className="flex flex-1 flex-col gap-2 p-4">
                      <span className="truncate text-xs text-dim">{subjectName.get(lesson.subject_id) ?? '—'}</span>
                      <span className="text-[15px] leading-[22.5px] font-semibold text-parchment">{lesson.title}</span>
                    </div>
                    <div className="flex items-center justify-end gap-2 border-t border-line-soft px-2 py-1">
                      {copy.error?.id === lesson.id && (
                        <p role="alert" className="flex-1 px-2 text-xs font-semibold text-accent">
                          {copy.error.message}
                        </p>
                      )}
                      <button
                        type="button"
                        title={lessonsList.copyHint}
                        disabled={copy.busyId !== null}
                        onClick={() => void copy.run(lesson)}
                        className="inline-flex min-h-10 items-center gap-2 rounded-[10px] px-3 text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50"
                      >
                        {copy.busyId === lesson.id && <Spinner />}
                        {copy.busyId === lesson.id ? lessonsList.copying : lessonsList.copy}
                      </button>
                    </div>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </main>
      </div>
      <TeacherTabs activeId="lessons" />
    </div>
  )
}
