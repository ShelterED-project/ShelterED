import { useState } from 'react'
import { getErrorMessage } from '@/features/auth/errors'
import { dateTimeLabel } from '@/shared/lib/date'
import { useClassStudentsQuery, useCreateParentLinkCodeMutation, useResetStudentPinMutation } from './schoolApi'
import type { ClassStudent } from './schoolApi'

const t = {
  loading: 'Завантажуємо учнів…',
  offline: 'Немає звʼязку: список учнів недоступний.',
  empty: 'У класі ще немає учнів. Вони приєднуються самі за кодом класу.',
  parentCode: 'Код для батьків',
  resetPin: 'Скинути PIN',
  confirmReset: (name: string) => `Скинути PIN для ${name}? Учень задасть новий при наступному вході.`,
  pinReset: 'PIN скинуто: учень задасть новий при вході.',
  code: (code: string, until: string) => `Код ${code}, діє до ${until}. Передайте його батькам: вони введуть код у своєму кабінеті.`,
}

const action =
  'h-9 rounded-lg border border-line-strong px-3 text-xs font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60'

function name(student: ClassStudent): string {
  return [student.display_name, student.last_name].filter(Boolean).join(' ')
}

function StudentRow({ classId, student }: { classId: string; student: ClassStudent }) {
  const [createCode, codeState] = useCreateParentLinkCodeMutation()
  const [resetPin, pinState] = useResetStudentPinMutation()
  const [note, setNote] = useState<string>()

  async function onCode() {
    setNote(undefined)
    try {
      const result = await createCode(student.student_id).unwrap()
      setNote(t.code(result.code, dateTimeLabel(result.expires_at)))
    } catch {
      // Текст помилки нижче.
    }
  }

  async function onReset() {
    if (!window.confirm(t.confirmReset(name(student)))) return
    setNote(undefined)
    try {
      await resetPin({ classId, studentId: student.student_id }).unwrap()
      setNote(t.pinReset)
    } catch {
      // Текст помилки нижче.
    }
  }

  const error = codeState.error ?? pinState.error
  return (
    <li className="flex flex-col gap-2 border-t border-line-soft py-3 first:border-t-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="min-w-0 text-[15px] font-medium text-parchment">{name(student)}</p>
        <div className="flex gap-2">
          <button type="button" onClick={onCode} disabled={codeState.isLoading} className={action}>
            {t.parentCode}
          </button>
          <button type="button" onClick={onReset} disabled={pinState.isLoading} className={action}>
            {t.resetPin}
          </button>
        </div>
      </div>
      {note && (
        <p role="status" className="rounded-lg bg-surface-2 px-3 py-2 text-sm text-parchment select-all">
          {note}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-danger">
          {getErrorMessage(error)}
        </p>
      )}
    </li>
  )
}

/** Учні класу з діями «Код для батьків» і «Скинути PIN» (вчитель класу й адмін школи). */
export default function ClassStudents({ classId }: { classId: string }) {
  const { data, isLoading, isError } = useClassStudentsQuery(classId, { refetchOnMountOrArgChange: true })
  if (isLoading)
    return (
      <p role="status" className="text-sm text-muted">
        {t.loading}
      </p>
    )
  if (isError && !data) return <p className="text-sm text-muted">{t.offline}</p>
  if (!data || data.length === 0) return <p className="text-sm text-muted">{t.empty}</p>
  return (
    <ul className="flex flex-col">
      {data.map((student) => (
        <StudentRow key={student.student_id} classId={classId} student={student} />
      ))}
    </ul>
  )
}
