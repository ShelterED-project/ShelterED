import { Link, useNavigate, useParams } from 'react-router'
import { skipToken } from '@reduxjs/toolkit/query/react'
import {
  useDeleteLessonMutation,
  useLessonQuery,
  usePublishLessonMutation,
  useUnpublishLessonMutation,
} from '@/features/teacher/lessonEditorApi'
import Spinner from '@/shared/ui/Spinner'
import TeacherHeader from '../sections/TeacherHeader'
import TeacherSidebar from '../sections/TeacherSidebar'
import TeacherTabs from '../sections/TeacherTabs'
import AssignSection from './AssignSection'
import { editor, lessonStatus } from './content'
import LessonDetails from './LessonDetails'
import ModulesSection from './ModulesSection'
import { dangerButton, primaryButton, secondaryButton } from './styles'
import TestsSection from './TestsSection'
import { useAction } from './useAction'

/**
 * Редактор уроку. Кожна зміна одразу йде на сервер (авторинг — онлайн), id створює клієнт.
 * Опублікований урок лише для перегляду: сервер не дає його змінювати.
 */
export default function LessonEditorPage() {
  const { lessonId } = useParams()
  const lesson = useLessonQuery(lessonId ?? skipToken)
  const [remove] = useDeleteLessonMutation()
  const [publish] = usePublishLessonMutation()
  const [unpublish] = useUnpublishLessonMutation()
  const del = useAction()
  const status = useAction()
  const navigate = useNavigate()
  const data = lesson.data
  const readOnly = data?.status === 'published'

  const deleteLesson = async () => {
    if (!data || !window.confirm(editor.confirmDelete)) return
    if (await del.run(() => remove(data.id).unwrap())) navigate('/teacher/lessons')
  }

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
            <p role="status" className="text-sm text-muted">
              {lesson.isLoading ? editor.loading : editor.notFound}
            </p>
          ) : (
            <>
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="flex min-w-0 flex-col gap-1">
                  <span
                    className={`self-start rounded-md px-2 py-0.5 text-xs font-semibold ${
                      readOnly ? 'bg-safe/15 text-safe' : 'bg-accent-soft text-accent'
                    }`}
                  >
                    {lessonStatus[data.status]}
                  </span>
                  <h1 className="font-heading text-2xl leading-[30px] text-parchment">{data.title}</h1>
                </div>
                <div className="flex flex-col gap-2 md:flex-row md:items-center">
                  {readOnly ? (
                    <button
                      type="button"
                      disabled={status.busy}
                      onClick={() => void status.run(() => unpublish(data.id).unwrap())}
                      className={secondaryButton}
                    >
                      {status.busy && <Spinner />}
                      {status.busy ? editor.unpublishing : editor.unpublish}
                    </button>
                  ) : (
                    <>
                      <button
                        type="button"
                        disabled={status.busy || del.busy}
                        onClick={() => void status.run(() => publish(data.id).unwrap())}
                        className={primaryButton}
                      >
                        {status.busy && <Spinner />}
                        {status.busy ? editor.publishing : editor.publish}
                      </button>
                      <button type="button" disabled={del.busy || status.busy} onClick={() => void deleteLesson()} className={dangerButton}>
                        {del.busy && <Spinner />}
                        {editor.deleteLesson}
                      </button>
                    </>
                  )}
                </div>
              </div>
              {(status.error ?? del.error) && (
                <p role="alert" className="text-sm font-semibold text-accent">
                  {status.error ?? del.error}
                </p>
              )}
              {!readOnly && <p className="text-sm text-dim">{editor.publishHint}</p>}
              {readOnly && (
                <p role="status" className="rounded-2xl border border-line bg-surface-2 p-4 text-sm text-muted">
                  {editor.readOnly}
                </p>
              )}

              <div className="flex flex-col gap-5 xl:flex-row xl:items-start xl:gap-6">
                <div className="flex flex-col gap-5 xl:w-[440px] xl:shrink-0 xl:gap-6">
                  <LessonDetails lesson={data} readOnly={readOnly} />
                  <AssignSection lesson={data} />
                </div>
                <div className="flex flex-col gap-5 xl:min-w-0 xl:flex-1 xl:gap-6">
                  <ModulesSection lesson={data} part="shelter" readOnly={readOnly} />
                  <ModulesSection lesson={data} part="main" readOnly={readOnly} />
                  <TestsSection lesson={data} readOnly={readOnly} />
                </div>
              </div>
            </>
          )}
        </main>
      </div>
      <TeacherTabs activeId="lessons" />
    </div>
  )
}
