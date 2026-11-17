import type { ReactNode } from 'react'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import { profile as t } from '../content'
import { card, heading } from './styles'

/** Хто увійшов. Дані з локальної сесії, тож картка працює без мережі. */
export default function ProfileCard({ note = t.note, children }: { note?: string; children?: ReactNode }) {
  const user = useCurrentUser()
  if (!user) return null
  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      <div className="flex items-center gap-4">
        <span className="flex size-14 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-lg font-bold text-parchment">
          {user.initials}
        </span>
        <dl className="min-w-0">
          <dt className="sr-only">{t.name}</dt>
          <dd className="truncate text-[17px] font-semibold text-parchment">{user.fullName}</dd>
          <dt className="sr-only">{t.role}</dt>
          <dd className="text-sm text-dim">{t.roles[user.role]}</dd>
        </dl>
      </div>
      {children}
      <p className="text-sm text-muted">{note}</p>
    </section>
  )
}
