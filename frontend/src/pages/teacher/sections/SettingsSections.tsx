import { useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import iconLogout from '@/assets/student/settings-logout.svg'
import { useAppSelector } from '@/app/hooks'
import { getErrorMessage } from '@/features/auth/errors'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import { useLogout } from '@/features/auth/useLogout'
import {
  useClassStudentsQuery,
  useCreateParentLinkCodeMutation,
  useResetStudentPinMutation,
} from '@/features/school/schoolApi'
import type { ParentLinkCode } from '@/features/school/schoolApi'
import { requestSync } from '@/features/sync/syncOutbox'
import { useConnection } from '@/features/sync/useConnection'
import type { ClassOut } from '@/features/teacher/teacherApi'
import { device, signOut } from '@/pages/settings/content'
import { Row, Section, smallButton, Status } from '@/pages/settings/sections/rows'
import { db } from '@/shared/db/db'
import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { dateTimeLabel, shortDateLabel } from '@/shared/lib/date'
import Spinner from '@/shared/ui/Spinner'
import { teacherRole, teacherSettings as t } from '../content'

function initials(first: string, last: string | null): string {
  return [first, last]
    .filter((part): part is string => Boolean(part))
    .map((part) => part[0].toUpperCase())
    .join('')
}

/** Копіювання в буфер з коротким «Скопійовано». Без Clipboard API (http у мережі) кнопка нічого не ламає. */
function useCopy() {
  const [copied, setCopied] = useState<string | null>(null)
  const copy = async (key: string, text: string) => {
    try {
      await navigator.clipboard.writeText(text)
      setCopied(key)
      setTimeout(() => setCopied((current) => (current === key ? null : current)), 2000)
    } catch {
      // Буфер недоступний: код і так видно на екрані.
    }
  }
  return { copied, copy }
}

export function ProfileSection({ classes }: { classes: ClassOut[] }) {
  const user = useCurrentUser()
  if (!user) return null
  const note = [teacherRole, ...classes.map((c) => c.name)].join(' · ')
  return (
    <Section title={t.profile.title}>
      <li className="flex flex-col gap-3 py-4">
        <div className="flex items-center gap-4">
          <span className="flex size-14 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-lg font-bold text-parchment">
            {user.initials}
          </span>
          <div className="min-w-0">
            <p className="truncate text-base leading-6 font-semibold text-parchment">{user.fullName}</p>
            <p className="text-xs leading-4 text-dim">{note}</p>
          </div>
        </div>
        <p className="text-xs leading-[16.5px] text-dim">{t.profile.note}</p>
      </li>
    </Section>
  )
}

/** Кількість учнів класу: той самий запит, що й для кодів батьків (RTK Query кешує). */
function StudentsCount({ classId }: { classId: string }) {
  const { data } = useClassStudentsQuery(classId)
  return data ? <>{` · ${t.classes.students(data.length)}`}</> : null
}

export function ClassesSection({
  classes,
  activeId,
  onSelect,
}: {
  classes: ClassOut[]
  activeId: string | null
  onSelect: (id: string) => void
}) {
  const { copied, copy } = useCopy()

  return (
    <Section title={t.classes.title}>
      {classes.length === 0 && (
        <li className="py-4">
          <p className="text-sm text-muted">{t.classes.empty}</p>
        </li>
      )}
      {classes.map((klass) =>
        klass.id === activeId ? (
          <li key={klass.id} className="flex flex-col gap-3 py-4">
            <div className="flex items-center justify-between gap-3">
              <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">
                {klass.name}
                <StudentsCount classId={klass.id} />
              </p>
              <span className="text-xs leading-4 font-semibold text-safe">{t.classes.active}</span>
            </div>
            <p aria-label={t.classes.code(klass.join_code)} className="flex gap-1 md:gap-1.5">
              {[...klass.join_code].map((char, i) => (
                <span
                  key={i}
                  aria-hidden="true"
                  className="flex h-12 w-8 items-center justify-center rounded-[10px] border border-line-strong bg-oil font-heading text-xl leading-8 tracking-[-0.24px] text-parchment md:h-14 md:w-11 md:text-2xl"
                >
                  {char}
                </span>
              ))}
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <button
                type="button"
                onClick={() => void copy(klass.id, klass.join_code)}
                className={`${smallButton} h-11 px-4`}
              >
                {copied === klass.id ? t.classes.copied : t.classes.copy}
              </button>
              <span className="text-xs leading-4 text-dim">{t.classes.newCode}</span>
            </div>
            <p className="text-xs leading-4 text-dim">
              {t.classes.hint}
              {klass.join_code_expires_at && ` ${t.classes.expires(shortDateLabel(klass.join_code_expires_at))}`}
            </p>
          </li>
        ) : (
          <Row key={klass.id} title={klass.name} note={t.classes.code(klass.join_code)}>
            <button type="button" onClick={() => onSelect(klass.id)} className={smallButton}>
              {t.classes.open}
            </button>
          </Row>
        ),
      )}
    </Section>
  )
}

type StudentNote = { kind: 'code'; code: ParentLinkCode } | { kind: 'pin' }

/**
 * Учні обраного класу: код привʼязки батьків і скидання PIN. Сервер видає новий одноразовий код
 * (7 днів), але не показує вже створені й не каже, чи батьки привʼязані, тож тут лише щойно видані.
 */
export function StudentsSection({ klass }: { klass: ClassOut }) {
  const { data: students, isLoading, isError } = useClassStudentsQuery(klass.id, { refetchOnMountOrArgChange: true })
  const [create] = useCreateParentLinkCodeMutation()
  const [resetPin] = useResetStudentPinMutation()
  const [notes, setNotes] = useState<Record<string, StudentNote>>({})
  const [busy, setBusy] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)
  const { copied, copy } = useCopy()

  const run = async (key: string, studentId: string, action: () => Promise<StudentNote>) => {
    setBusy(key)
    setError(null)
    try {
      const note = await action()
      setNotes((current) => ({ ...current, [studentId]: note }))
    } catch (e) {
      setError(getErrorMessage(e as Parameters<typeof getErrorMessage>[0]) || t.students.error)
    } finally {
      setBusy(null)
    }
  }

  const issueCode = (studentId: string) =>
    run(`code:${studentId}`, studentId, async () => ({ kind: 'code', code: await create(studentId).unwrap() }))

  const reset = (studentId: string, name: string) => {
    if (!window.confirm(t.students.confirmReset(name))) return
    void run(`pin:${studentId}`, studentId, async () => {
      await resetPin({ classId: klass.id, studentId }).unwrap()
      return { kind: 'pin' }
    })
  }

  return (
    <section className="flex flex-col rounded-[22px] border border-line bg-surface px-5 pt-2 pb-5 md:px-6 md:pb-6">
      <h2 className="pt-4 pb-1 font-heading text-[22px] leading-7 tracking-[-0.22px] text-parchment">
        {t.students.title(klass.name)}
      </h2>
      <p className="pb-3 text-sm leading-5 text-muted">{t.students.text}</p>
      {isLoading && <Spinner className="my-3 text-accent" />}
      {isError && !students && <p className="text-sm text-muted">{t.students.offline}</p>}
      {students?.length === 0 && <p className="text-sm text-muted">{t.students.empty}</p>}
      <ul className="flex flex-col">
        {(students ?? []).map((student) => {
          const note = notes[student.student_id]
          const name = [student.display_name, student.last_name].filter(Boolean).join(' ')
          const code = note?.kind === 'code' ? note.code : null
          const status = code
            ? t.students.until(code.code, shortDateLabel(code.expires_at))
            : note?.kind === 'pin'
              ? t.students.pinReset
              : null
          return (
            <li
              key={student.student_id}
              className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-line-soft py-3"
            >
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs leading-4 font-bold text-parchment">
                {initials(student.display_name, student.last_name)}
              </span>
              <div className="flex min-w-0 flex-1 flex-col">
                <p className="truncate text-sm leading-5 font-semibold text-parchment">{name}</p>
                {status && (
                  <p role="status" className={`text-xs leading-4 select-all ${code ? 'text-accent' : 'text-safe'}`}>
                    {status}
                  </p>
                )}
              </div>
              {/* На телефоні кнопки переносяться під імʼя, щоб не тиснути його. */}
              <div className="flex w-full gap-2 pl-12 sm:w-auto sm:pl-0">
                {code ? (
                  <button
                    type="button"
                    onClick={() => void copy(student.student_id, code.code)}
                    className={`${smallButton} h-9 text-xs`}
                  >
                    {copied === student.student_id ? t.students.copied : t.students.copy}
                  </button>
                ) : (
                  <button
                    type="button"
                    onClick={() => void issueCode(student.student_id)}
                    disabled={busy !== null}
                    aria-busy={busy === `code:${student.student_id}`}
                    className={`${smallButton} h-9 text-xs`}
                  >
                    {busy === `code:${student.student_id}` && <Spinner />}
                    {t.students.parentCode}
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => reset(student.student_id, name)}
                  disabled={busy !== null}
                  aria-busy={busy === `pin:${student.student_id}`}
                  className={`${smallButton} h-9 text-xs`}
                >
                  {busy === `pin:${student.student_id}` && <Spinner />}
                  {t.students.resetPin}
                </button>
              </div>
            </li>
          )
        })}
      </ul>
      {error && (
        <p role="alert" className="pt-2 text-sm text-danger">
          {error}
        </p>
      )}
      {students && students.length > 0 && <p className="pt-2 text-xs leading-4 text-dim">{t.students.note}</p>}
    </section>
  )
}

/** Ручна тривога живе в шапці; тут лише підказка, де вона (перемикачів без функції не показуємо). */
export function AlarmSection() {
  return (
    <Section title={t.alarm.title}>
      <Row title={t.alarm.manual} note={t.alarm.manualNote} />
    </Section>
  )
}

export function DeviceSection() {
  const { online, lastOkAt } = useConnection()
  const pending = useOutboxCount()
  const [busy, setBusy] = useState(false)

  async function sync() {
    setBusy(true)
    try {
      await requestSync()
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title={device.title}>
      <Row title={device.internet} note={online ? t.device.online : t.device.offline}>
        <button
          type="button"
          onClick={() => void sync()}
          disabled={busy || !online}
          aria-busy={busy}
          className={smallButton}
        >
          {busy && <Spinner />}
          {busy ? device.syncing : device.sync}
        </button>
      </Row>
      <Row title={device.lastSync} note={lastOkAt ? dateTimeLabel(lastOkAt) : device.never} />
      <Row title={device.queue} note={device.queueValue(pending)}>
        <Status ok={pending === 0}>{pending === 0 ? '✓' : pending}</Status>
      </Row>
    </Section>
  )
}

/** Вихід: невідправлені записи лишаються на пристрої до наступного входу. */
export function SignOut() {
  const logout = useLogout()
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  const pending = useLiveQuery(
    async () => (userId ? db.events.where('user_id').equals(userId).count() : 0),
    [userId],
    0,
  )

  return (
    <div className="flex flex-col gap-3">
      {pending > 0 && (
        <p role="status" className="text-sm text-accent">
          {signOut.pending(pending)}
        </p>
      )}
      <button
        type="button"
        onClick={() => void logout()}
        className="flex h-14 w-full items-center justify-center gap-2 rounded-[10px] border border-line-strong px-5 text-[15px] leading-[22.5px] font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconLogout} alt="" width={16} height={16} />
        {signOut.button}
      </button>
    </div>
  )
}
