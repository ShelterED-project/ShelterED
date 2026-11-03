import LogoutButton from '@/features/auth/LogoutButton'

export default function TeacherPage() {
  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-6">
      <h1 className="text-3xl font-bold">Кабінет вчителя</h1>
      <LogoutButton className="h-11 rounded-[10px] border border-line px-5" />
    </main>
  )
}
