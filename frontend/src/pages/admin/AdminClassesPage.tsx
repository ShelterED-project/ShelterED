import { useState } from 'react'
import { useCreateClassMutation, useSchoolUsersQuery } from '@/features/admin/adminApi'
import { getErrorMessage } from '@/features/auth/errors'
import { useClassesQuery } from '@/features/teacher/teacherApi'
import { classesPage as t, loading, offline } from './content'
import AdminHeader from './sections/AdminHeader'
import AdminSidebar from './sections/AdminSidebar'
import AdminTabs from './sections/AdminTabs'
import ClassCard from './sections/ClassCard'
import ClassForm from './sections/ClassForm'
import CreateUserDialog from './sections/CreateUserDialog'
import MobileGreeting from './sections/MobileGreeting'

export default function AdminClassesPage() {
  const [creatingUser, setCreatingUser] = useState(false)
  const [adding, setAdding] = useState(false)
  const classes = useClassesQuery(undefined, { refetchOnMountOrArgChange: true })
  const teachers = useSchoolUsersQuery('teacher')
  const [createClass, createState] = useCreateClassMutation()

  const sorted = [...(classes.data ?? [])].sort((a, b) => a.grade - b.grade || a.name.localeCompare(b.name, 'uk'))

  return (
    <div className="flex min-h-screen">
      <AdminSidebar activeId="classes" />
      <div className="flex min-w-0 flex-1 flex-col">
        <AdminHeader onAddUser={() => setCreatingUser(true)} title={t.title} />
        <main className="flex flex-col gap-5 px-5 pt-6 pb-24 md:px-8 md:pb-8 xl:gap-6 xl:px-10 xl:py-8">
          <MobileGreeting title={t.title} />
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="text-sm text-dim">{t.subtitle}</p>
            {!adding && (
              <button
                type="button"
                onClick={() => {
                  createState.reset()
                  setAdding(true)
                }}
                className="h-11 rounded-[10px] bg-accent px-5 text-sm font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none"
              >
                {t.add}
              </button>
            )}
          </div>

          {adding && (
            <section className="flex flex-col gap-4 rounded-[22px] border border-accent/40 bg-surface p-5 xl:p-6">
              <h2 className="font-heading text-xl leading-7 text-parchment">{t.add}</h2>
              <ClassForm
                submitLabel={t.form.create}
                busy={createState.isLoading}
                error={createState.error ? getErrorMessage(createState.error) : undefined}
                onCancel={() => setAdding(false)}
                onSubmit={async (fields) => {
                  try {
                    await createClass(fields).unwrap()
                    setAdding(false)
                  } catch {
                    // Текст помилки у формі.
                  }
                }}
              />
            </section>
          )}

          {classes.isLoading && (
            <p role="status" className="text-sm text-muted">
              {loading}
            </p>
          )}
          {classes.isError && (
            <p role="status" className="text-sm text-muted">
              {offline}
            </p>
          )}

          <div className="grid gap-5 xl:grid-cols-2 xl:gap-6">
            {sorted.map((klass) => (
              <ClassCard key={klass.id} klass={klass} teachers={teachers.data ?? []} />
            ))}
          </div>
        </main>
      </div>
      <AdminTabs activeId="classes" />
      <CreateUserDialog open={creatingUser} onClose={() => setCreatingUser(false)} />
    </div>
  )
}
