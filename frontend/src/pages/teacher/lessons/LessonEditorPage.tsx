import { useCallback, useEffect, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router'
import { skipToken } from '@reduxjs/toolkit/query/react'
import {
  errorMessage,
  publishChecks,
  useDeleteLessonMutation,
  useLessonQuery,
  usePublishLessonMutation,
  useUnpublishLessonMutation,
} from '@/features/teacher/lessonEditorApi'
import type { LessonCheck } from '@/features/teacher/lessonEditorApi'
import { usePendingLesson } from '@/features/teacher/pendingCreates'
import Spinner from '@/shared/ui/Spinner'
import TeacherHeader from '../sections/TeacherHeader'
import TeacherSidebar from '../sections/TeacherSidebar'
import TeacherTabs from '../sections/TeacherTabs'
import AssignSection from './AssignSection'
import { editor, lessonStatus, save } from './content'
import LessonDetails from './LessonDetails'
import LessonPreview from './LessonPreview'
import ModulesSection from './ModulesSection'
import PublishPanel from './PublishPanel'
import SaveIndicator from './SaveIndicator'
import { hasUnsaved } from './saveStatus'
import StartGuide from './StartGuide'
import { dangerButton, primaryButton, secondaryButton } from './styles'
import TestsSection from './TestsSection'
import { useAction } from './useAction'
import { useCopyLesson } from './useCopyLesson'
import { usePendingSync } from './usePendingSync'

/**
 * Редактор уроку. Усе зберігається саме (автозбереження), id створює клієнт.
 * Опублікований урок лише для перегляду: сервер не дає його змінювати.
 */
export default function LessonEditorPage() {
  const { lessonId } = useParams()
  const lesson = useLessonQuery(lessonId ?? skipToken)
  const [remove] = useDeleteLessonMutation()
  const [publish] = usePublishLessonMutation()
  const [unpublish] = useUnpublishLessonMutation()
  const del = useAction()
  const copy = useCopyLesson()
  const [publishing, setPublishing] = useState(false)
  const [statusError, setStatusError] = useState<string | null>(null)
  const [checks, setChecks] = useState<LessonCheck[]>([])
  const [preview, setPreview] = useState(false)
  const navigate = useNavigate()
  // currentData — лише урок з цієї адреси: при переході до іншого уроку не показуємо попередній.
  const data = usePendingLesson(lesson.currentData)
  usePendingSync()
  const readOnly = data?.status === 'published'
  const closePreview = useCallback(() => setPreview(false), [])

  // Не губимо незбережене при закритті вкладки (чернетки й так у IndexedDB, але попередимо).
  useEffect(() => {
    const onUnload = (e: BeforeUnloadEvent) => {
      if (hasUnsaved()) {
        e.preventDefault()
        e.returnValue = save.leaveWarning
      }
    }
    window.addEventListener('beforeunload', onUnload)
    return () => window.removeEventListener('beforeunload', onUnload)
  }, [])

  const deleteLesson = async () => {
    if (!data || !window.confirm(editor.confirmDelete)) return
    if (await del.run(() => remove(data.id).unwrap())) navigate('/teacher/lessons')
  }

  const toggle = async () => {
    if (!data) return
    setPublishing(true)
    setStatusError(null)
    setChecks([])
    try {
      if (readOnly) await unpublish(data.id).unwrap()
      else await publish(data.id).unwrap()
    } catch (err) {
      const list = publishChecks(err)
      setChecks(list)
      setStatusError(list.length > 0 ? null : errorMessage(err))
    } finally {
      setPublishing(false)
    }
  }

  const empty = data && data.modules.length === 0 && data.tests.length === 0

  return (
    <div className="flex min-h-screen">
      <TeacherSidebar activeId="lessons" />
      <div className="flex min-w-0 flex-1 flex-col">
        <TeacherHeader />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <Link
            to="/teacher/lessons"
            className="self-start rounded text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            {editor.back}
          </Link>

          {!data ? (
            lesson.isFetching ? (
              <div
                role="status"
                aria-live="polite"
                className="flex items-center gap-3 rounded-[22px] border border-line bg-surface p-6 text-[15px] text-muted"
              >
                <Spinner large className="text-accent" />
                {editor.loading}
              </div>
            ) : (
              <p role="alert" className="text-sm text-muted">
                {editor.notFound}
              </p>
            )
          ) : (
            <>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex min-w-0 flex-col gap-1">
                  <div className="flex flex-wrap items-center gap-3">
                    <span
                      className={`rounded-md px-2 py-0.5 text-xs font-semibold ${
                        readOnly ? 'bg-safe/15 text-safe' : 'bg-accent-soft text-accent'
                      }`}
                    >
                      {lessonStatus[data.status]}
                    </span>
                    <SaveIndicator />
                  </div>
                  <h1 className="font-heading text-2xl leading-[30px] break-words text-parchment">{data.title}</h1>
                </div>
                <div className="flex flex-wrap gap-2 md:justify-end">
                  <button type="button" onClick={() => setPreview(true)} className={secondaryButton}>
                    {editor.previewButton}
                  </button>
                  <button
                    type="button"
                    disabled={copy.busyId !== null}
                    onClick={() => void copy.run(data)}
                    className={secondaryButton}
                  >
                    {copy.busyId && <Spinner />}
                    {copy.busyId ? editor.copying : editor.copy}
                  </button>
                  <button
                    type="button"
                    disabled={publishing || del.busy}
                    onClick={() => void toggle()}
                    className={readOnly ? secondaryButton : primaryButton}
                  >
                    {publishing && <Spinner />}
                    {readOnly
                      ? publishing
                        ? editor.unpublishing
                        : editor.unpublish
                      : publishing
                        ? editor.publishing
                        : editor.publish}
                  </button>
                  {!readOnly && (
                    <button type="button" disabled={del.busy || publishing} onClick={() => void deleteLesson()} className={dangerButton}>
                      {del.busy && <Spinner />}
                      {editor.deleteLesson}
                    </button>
                  )}
                </div>
              </div>
              {(statusError ?? del.error ?? copy.error?.message) && (
                <p role="alert" className="text-sm font-semibold text-accent">
                  {statusError ?? del.error ?? copy.error?.message}
                </p>
              )}
              <PublishPanel lesson={data} errors={checks} />
              {!readOnly && <p className="text-sm text-dim">{editor.publishHint}</p>}
              {readOnly && (
                <p role="status" className="rounded-2xl border border-line bg-surface-2 p-4 text-sm text-muted">
                  {editor.readOnly}
                </p>
              )}

              {empty && !readOnly && <StartGuide lesson={data} />}

              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
                <div className="flex flex-col gap-5 xl:w-[440px] xl:shrink-0 xl:gap-6">
                  <LessonDetails key={data.id} lesson={data} readOnly={readOnly} />
                  <AssignSection lesson={data} />
                </div>
                <div className="flex flex-col gap-5 xl:min-w-0 xl:flex-1 xl:gap-6">
                  <ModulesSection lesson={data} part="shelter" readOnly={readOnly} />
                  <ModulesSection lesson={data} part="main" readOnly={readOnly} />
                  <TestsSection lesson={data} readOnly={readOnly} />
                </div>
              </div>
              {preview && <LessonPreview lesson={data} onClose={closePreview} />}
            </>
          )}
        </main>
      </div>
      <TeacherTabs activeId="lessons" />
    </div>
  )
}
