import { useState } from 'react'
import iconSearch from '@/assets/admin/search.svg'
import { useSchoolUsersQuery } from '@/features/admin/adminApi'
import type { ListedRole } from '@/features/admin/adminApi'
import { userInitials, userName } from '@/features/admin/format'
import { useClassesQuery } from '@/features/teacher/teacherApi'
import { loading, offline, roleLabels, usersPage as t } from './content'
import AdminHeader from './sections/AdminHeader'
import AdminSidebar from './sections/AdminSidebar'
import AdminTabs from './sections/AdminTabs'
import CreateUserDialog from './sections/CreateUserDialog'
import MobileGreeting from './sections/MobileGreeting'

const filters: (ListedRole | 'all')[] = ['all', 'teacher', 'admin', 'student']

/** Пошук без урахування регістру й апострофів (ʼ, ’, ' пишуть по-різному). */
function normalize(text: string): string {
  return text.toLocaleLowerCase('uk').replace(/[ʼ’'`]/g, '')
}

export default function AdminUsersPage() {
  const [creating, setCreating] = useState(false)
  const [role, setRole] = useState<ListedRole | 'all'>('all')
  const [search, setSearch] = useState('')
  const users = useSchoolUsersQuery(role === 'all' ? undefined : role, { refetchOnMountOrArgChange: true })
  const classes = useClassesQuery()

  const teacherClasses = (id: string) =>
    (classes.data ?? [])
      .filter((c) => c.teacher_ids.includes(id))
      .map((c) => c.name)
      .join(', ')

  const query = normalize(search.trim())
  const list = (users.data ?? []).filter((u) => !query || normalize(userName(u)).includes(query))

  return (
    <div className="flex min-h-screen">
      <AdminSidebar activeId="users" />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader
          onAddUser={() => setCreating(true)}
          title={t.title}
          search={{ value: search, onChange: setSearch, placeholder: t.search }}
        />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting title={t.title} />
          <p className="text-sm text-dim">{t.subtitle}</p>

          <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div role="group" aria-label="Роль" className="flex flex-wrap gap-1 rounded-xl border border-line bg-surface p-1">
              {filters.map((value) => (
                <button
                  key={value}
                  type="button"
                  aria-pressed={role === value}
                  onClick={() => setRole(value)}
                  className={`h-10 rounded-lg px-4 text-sm font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none ${
                    role === value ? 'bg-surface-2 text-accent shadow-[inset_0_0_0_1px_var(--color-line-strong)]' : 'text-muted'
                  }`}
                >
                  {value === 'all' ? t.filterAll : roleLabels[value]}
                </button>
              ))}
            </div>
            <div className="relative xl:hidden">
              <img
                src={iconSearch}
                alt=""
                width={18}
                height={18}
                className="pointer-events-none absolute top-1/2 left-3.5 -translate-y-1/2"
              />
              <input
                type="search"
                aria-label={t.search}
                placeholder={t.search}
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                className="h-12 w-full rounded-[10px] border border-line bg-surface pr-3 pl-10 text-sm text-parchment placeholder:text-dim focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none md:w-[260px]"
              />
            </div>
          </div>

          {users.isLoading && (
            <p role="status" className="text-sm text-muted">
              {loading}
            </p>
          )}
          {users.isError && (
            <p role="status" className="text-sm text-muted">
              {offline}
            </p>
          )}

          <section className="flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
            <p className="text-xs text-dim">{t.count(list.length)}</p>
            {list.length === 0 ? (
              <p className="text-sm text-muted">{t.empty}</p>
            ) : (
              <ul>
                {list.map((user, i) => (
                  <li key={user.id} className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
                    <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs leading-4 font-semibold text-parchment">
                      {userInitials(user)}
                    </span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate text-[15px] leading-[22.5px] font-medium text-parchment">{userName(user)}</span>
                      <span className="block text-xs leading-4 text-dim">
                        {roleLabels[user.role]}
                        {user.role === 'teacher' && teacherClasses(user.id) && ` · ${teacherClasses(user.id)}`}
                      </span>
                    </span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <p className="text-xs text-dim">{t.parentsNote}</p>
        </main>
      </div>
      <AdminTabs activeId="more" />
      <CreateUserDialog open={creating} onClose={() => setCreating(false)} />
    </div>
  )
}
