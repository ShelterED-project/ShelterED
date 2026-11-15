import { useState } from 'react'
import type { FormEvent } from 'react'
import { Link, useNavigate } from 'react-router'
import { errorMessage, useCreateLessonMutation } from '@/features/teacher/lessonEditorApi'
import { useLessonsQuery, useSubjectsQuery } from '@/features/teacher/teacherApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import TeacherHeader from '../sections/TeacherHeader'
import TeacherSidebar from '../sections/TeacherSidebar'
import TeacherTabs from '../sections/TeacherTabs'
import { lessonsList, lessonStatus, newLesson } from './content'
import { field, primaryButton, secondaryButton } from './styles'

function NewLessonForm({ onCancel }: { onCancel: () => void }) {
  const { data: subjects } = useSubjectsQuery()
  const [create, { isLoading }] = useCreateLessonMutation()
  const navigate = useNavigate()
  const [subjectId, setSubjectId] = useState('')
  const [title, setTitle] = useState('')
  const [error, setError] = useState<string | null>(null)
  // id уроку створюємо один раз на форму: повторне натискання після обриву мережі не дасть дубля.
  const [id] = useState(generateId)

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setError(null)
    try {
      await create({ id, subject_id: subjectId, title: title.trim(), shelter_part: '', main_part: '', grade: null }).unwrap()
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
  const [creating, setCreating] = useState(false)
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

          {!lessons.data || lessons.data.length === 0 ? (
            <p role="status" className="text-sm text-muted">
              {lessons.isLoading ? lessonsList.loading : lessons.isError ? lessonsList.offline : lessonsList.empty}
            </p>
          ) : (
            <ul className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {lessons.data.map((lesson) => (
                <li key={lesson.id}>
                  <Link
                    to={`/teacher/lessons/${lesson.id}`}
                    className="flex h-full flex-col gap-2 rounded-2xl border border-line bg-surface p-4 hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
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
                </li>
              ))}
            </ul>
          )}
        </main>
      </div>
      <TeacherTabs activeId="lessons" />
    </div>
  )
}
