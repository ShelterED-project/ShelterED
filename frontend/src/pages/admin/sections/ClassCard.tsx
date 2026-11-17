import { useState } from 'react'
import {
  useDeleteClassMutation,
  useNewJoinCodeMutation,
  useSetClassTeacherMutation,
  useUpdateClassMutation,
} from '@/features/admin/adminApi'
import type { SchoolUser } from '@/features/admin/adminApi'
import { userName } from '@/features/admin/format'
import { getErrorMessage } from '@/features/auth/errors'
import ClassStudents from '@/features/school/ClassStudents'
import type { ClassOut } from '@/features/teacher/teacherApi'
import { dateTimeLabel } from '@/shared/lib/date'
import { classesPage as t } from '../content'
import ClassForm from './ClassForm'

const smallButton =
  'h-9 rounded-lg border border-line-strong px-3 text-xs font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-60'

type Props = { klass: ClassOut; teachers: SchoolUser[] }

export default function ClassCard({ klass, teachers }: Props) {
  const [editing, setEditing] = useState(false)
  const [showStudents, setShowStudents] = useState(false)
  const [update, updateState] = useUpdateClassMutation()
  const [remove, removeState] = useDeleteClassMutation()
  const [newCode, codeState] = useNewJoinCodeMutation()
  const [setTeacher, teacherState] = useSetClassTeacherMutation()

  const assigned = teachers.filter((u) => klass.teacher_ids.includes(u.id))
  const available = teachers.filter((u) => !klass.teacher_ids.includes(u.id))
  const error = removeState.error ?? codeState.error ?? teacherState.error

  if (editing) {
    return (
      <section className="flex flex-col gap-4 rounded-[22px] border border-accent/40 bg-surface p-5 xl:p-6">
        <h2 className="font-heading text-xl leading-7 text-parchment">{klass.name}</h2>
        <ClassForm
          initial={{ name: klass.name, grade: klass.grade, academic_year: klass.academic_year }}
          submitLabel={t.form.save}
          busy={updateState.isLoading}
          error={updateState.error ? getErrorMessage(updateState.error) : undefined}
          onCancel={() => setEditing(false)}
          onSubmit={async (fields) => {
            try {
              await update({ classId: klass.id, ...fields }).unwrap()
              setEditing(false)
            } catch {
              // Текст помилки у формі.
            }
          }}
        />
      </section>
    )
  }

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{klass.name}</h2>
          <p className="text-sm text-dim">{t.grade(klass.grade, klass.academic_year)}</p>
        </div>
        <div className="flex gap-2">
          <button type="button" onClick={() => setEditing(true)} className={smallButton}>
            {t.edit}
          </button>
          <button
            type="button"
            disabled={removeState.isLoading}
            onClick={() => window.confirm(t.confirmRemove(klass.name)) && void remove(klass.id)}
            className={smallButton}
          >
            {t.remove}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-3 rounded-[14px] border border-line bg-surface-2/60 p-3">
        <div className="min-w-0 flex-1">
          <p className="text-xs text-dim">{t.joinCode}</p>
          <p className="font-heading text-xl tracking-[2px] text-accent select-all">{klass.join_code}</p>
          {klass.join_code_expires_at && (
            <p className="text-xs text-dim">{t.joinCodeUntil(dateTimeLabel(klass.join_code_expires_at))}</p>
          )}
        </div>
        <button
          type="button"
          disabled={codeState.isLoading}
          onClick={() => window.confirm(t.confirmNewCode) && void newCode({ classId: klass.id })}
          className={smallButton}
        >
          {t.newCode}
        </button>
      </div>

      <div className="flex flex-col gap-2">
        <h3 className="text-sm font-semibold text-parchment">{t.teachers}</h3>
        {assigned.length === 0 && <p className="text-sm text-muted">{t.noTeachers}</p>}
        <ul className="flex flex-wrap gap-2">
          {assigned.map((teacher) => (
            <li key={teacher.id} className="flex items-center gap-1 rounded-full border border-line bg-surface-2 py-1 pr-1 pl-3 text-sm text-parchment">
              {userName(teacher)}
              <button
                type="button"
                aria-label={t.removeTeacher(userName(teacher))}
                disabled={teacherState.isLoading}
                onClick={() => void setTeacher({ classId: klass.id, teacherId: teacher.id, assigned: false })}
                className="flex size-7 items-center justify-center rounded-full text-muted hover:bg-surface hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
              >
                ✕
              </button>
            </li>
          ))}
        </ul>
        {available.length > 0 && (
          <select
            aria-label={t.addTeacher}
            value=""
            disabled={teacherState.isLoading}
            onChange={(e) => e.target.value && void setTeacher({ classId: klass.id, teacherId: e.target.value, assigned: true })}
            className="h-11 max-w-xs rounded-[10px] border border-line bg-surface px-3 text-sm text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
          >
            <option value="">{t.addTeacher}</option>
            {available.map((teacher) => (
              <option key={teacher.id} value={teacher.id}>
                {userName(teacher)}
              </option>
            ))}
          </select>
        )}
      </div>

      {error && (
        <p role="alert" className="text-sm text-danger">
          {getErrorMessage(error)}
        </p>
      )}

      <div className="flex flex-col gap-2">
        <button
          type="button"
          aria-expanded={showStudents}
          onClick={() => setShowStudents((v) => !v)}
          className="self-start rounded text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {showStudents ? t.hideStudents : t.showStudents}
        </button>
        {showStudents && <ClassStudents classId={klass.id} />}
      </div>
    </section>
  )
}
