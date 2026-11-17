import { Link } from 'react-router'
import iconPlus from '@/assets/admin/plus-16.svg'
import type { SchoolUser } from '@/features/admin/adminApi'
import { userInitials, userName } from '@/features/admin/format'
import type { ClassOut } from '@/features/teacher/teacherApi'
import { navRoutes, users as t } from '../content'

/** Скільки вчителів на огляді; решта — на сторінці «Користувачі». */
const LIMIT = 5

type Props = { teachers: SchoolUser[]; classes: ClassOut[]; className?: string; onInvite: () => void }

export default function UsersCard({ teachers, classes, className = '', onInvite }: Props) {
  const classNames = (teacherId: string) =>
    classes
      .filter((c) => c.teacher_ids.includes(teacherId))
      .map((c) => c.name)
      .join(', ')

  return (
    <section className={`flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 xl:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{t.title}</h2>
        <p className="text-right text-xs leading-4 text-dim">{t.summary(teachers.length)}</p>
      </div>
      {teachers.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <ul className="pt-1">
          {teachers.slice(0, LIMIT).map((user, i) => (
            <li key={user.id} className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
              <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs leading-4 font-semibold text-parchment">
                {userInitials(user)}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-[15px] leading-[22.5px] font-medium text-parchment">{userName(user)}</span>
                <span className="block text-xs leading-4 text-dim">{classNames(user.id) || '—'}</span>
              </span>
            </li>
          ))}
        </ul>
      )}
      <Link
        to={navRoutes.users ?? '/admin'}
        className="rounded text-center text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        {t.all}
      </Link>
      <button
        type="button"
        onClick={onInvite}
        className="flex items-center justify-center gap-2 rounded-[10px] border border-line-strong py-[10.5px] text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconPlus} alt="" width={16} height={16} />
        {t.invite}
      </button>
    </section>
  )
}
