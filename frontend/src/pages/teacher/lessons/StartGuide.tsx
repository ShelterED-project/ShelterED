import { useState } from 'react'
import { useNavigate } from 'react-router'
import {
  errorMessage,
  useCopyLessonMutation,
  useCreateModuleMutation,
  useCreateTestMutation,
  useDeleteLessonMutation,
} from '@/features/teacher/lessonEditorApi'
import type { LessonOut } from '@/features/teacher/lessonEditorApi'
import { useLessonsQuery } from '@/features/teacher/teacherApi'
import { generateId } from '@/shared/lib/uuid'
import Spinner from '@/shared/ui/Spinner'
import { editor, guideSteps } from './content'
import { focusOnMount, jumpTo } from './jump'
import { tracked } from './saveStatus'
import { card, field, primaryButton, secondaryButton } from './styles'

/** Порожній урок: три кроки з кнопками й старт з копії існуючого уроку. */
export default function StartGuide({ lesson }: { lesson: LessonOut }) {
  const g = editor.guide
  const navigate = useNavigate()
  const lessons = useLessonsQuery()
  const [createModule] = useCreateModuleMutation()
  const [createTest] = useCreateTestMutation()
  const [copy] = useCopyLessonMutation()
  const [remove] = useDeleteLessonMutation()
  const [source, setSource] = useState('')
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [ids] = useState(() => ({ module: generateId(), test: generateId(), copy: generateId() }))
  const others = (lessons.data ?? []).filter((l) => l.id !== lesson.id)

  const run = async (key: string, action: () => Promise<unknown>) => {
    setBusy(key)
    setError(null)
    try {
      await tracked(`guide:${key}`, action)
    } catch (err) {
      setError(errorMessage(err))
    } finally {
      setBusy(null)
    }
  }

  const addModule = () =>
    run('module', async () => {
      focusOnMount(ids.module)
      await createModule({
        lessonId: lesson.id,
        id: ids.module,
        part: 'shelter',
        position: 1,
        title: editor.modules.defaultTitle(1),
        duration_min: 4,
      }).unwrap()
    })
  const addTest = () =>
    run('test', async () => {
      focusOnMount(ids.test)
      await createTest({ lessonId: lesson.id, id: ids.test, title: editor.tests.defaultTitle, window_enabled: false, window_hours: null }).unwrap()
    })
  const fromCopy = () =>
    run('copy', async () => {
      const original = others.find((l) => l.id === source)
      const copyId = ids.copy
      await copy({ sourceId: source, id: copyId, title: lesson.title || original?.title }).unwrap()
      // Порожня чернетка більше не потрібна.
      await remove(lesson.id)
        .unwrap()
        .catch(() => undefined)
      navigate(`/teacher/lessons/${copyId}`, { replace: true })
    })

  const actions = [
    { label: g.writeIntro, done: lesson.shelter_part.trim() !== '', onClick: () => jumpTo('field-shelter_part'), key: 'intro' },
    { label: g.addModule, done: lesson.modules.length > 0, onClick: () => void addModule(), key: 'module' },
    { label: g.addTest, done: lesson.tests.length > 0, onClick: () => void addTest(), key: 'test' },
  ]

  return (
    <section className={`${card} border-accent/40`}>
      <h2 className="font-heading text-xl leading-7 text-parchment">{g.title}</h2>
      <ol className="grid gap-3 md:grid-cols-3">
        {guideSteps.map((step, i) => {
          const action = actions[i]
          return (
            <li key={step.title} className="flex flex-col gap-2 rounded-2xl border border-line-soft bg-surface-2 p-4">
              <p className="text-xs font-semibold tracking-[0.96px] text-accent uppercase">{g.step(i + 1)}</p>
              <p className="text-[17px] font-semibold text-parchment">{step.title}</p>
              <p className="flex-1 text-sm text-muted">{step.text}</p>
              {action &&
                (action.done ? (
                  <p className="text-sm font-semibold text-safe">✓ {g.done}</p>
                ) : (
                  <button type="button" disabled={busy !== null} onClick={action.onClick} className={i === 0 ? primaryButton : secondaryButton}>
                    {busy === action.key && <Spinner />}
                    {action.label}
                  </button>
                ))}
            </li>
          )
        })}
      </ol>
      {others.length > 0 && (
        <div className="flex flex-col gap-2 border-t border-line-soft pt-4">
          <p className="text-sm font-semibold text-parchment">{g.fromCopy}</p>
          <div className="flex flex-col gap-2 md:flex-row">
            <select aria-label={g.chooseLesson} value={source} onChange={(e) => setSource(e.target.value)} className={`${field} md:flex-1`}>
              <option value="">{g.chooseLesson}</option>
              {others.map((l) => (
                <option key={l.id} value={l.id}>
                  {l.title}
                </option>
              ))}
            </select>
            <button type="button" disabled={!source || busy !== null} onClick={() => void fromCopy()} className={secondaryButton}>
              {busy === 'copy' && <Spinner />}
              {g.copyHere}
            </button>
          </div>
          <p className="text-xs text-dim">{g.copyHint}</p>
        </div>
      )}
      {error && (
        <p role="alert" className="text-sm font-semibold text-accent">
          {error}
        </p>
      )}
    </section>
  )
}
