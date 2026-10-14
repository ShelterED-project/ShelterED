import { useState } from 'react'
import { markStatus } from '@/features/roll-call/rollCall'
import type { RollCallStatus } from '@/features/roll-call/types'
import { useOutboxCount } from '@/shared/db/useOutboxCount'

const STATUS_LABELS: Record<RollCallStatus, string> = {
  safe: 'Я в безпеці',
  shelter: 'Я в укритті',
}

export default function StudentPage() {
  const [lastStatus, setLastStatus] = useState<RollCallStatus | null>(null)
  const pending = useOutboxCount()

  const mark = async (status: RollCallStatus) => {
    await markStatus(status)
    setLastStatus(status)
  }

  return (
    <main className="mx-auto flex min-h-screen max-w-md flex-col justify-center gap-4 p-4">
      <h1 className="text-2xl font-bold">Кабінет учня</h1>

      <button
        className="rounded-2xl bg-green-700 px-6 py-8 text-2xl font-bold"
        onClick={() => mark('safe')}
      >
        {STATUS_LABELS.safe}
      </button>
      <button
        className="rounded-2xl bg-amber-600 px-6 py-8 text-2xl font-bold"
        onClick={() => mark('shelter')}
      >
        {STATUS_LABELS.shelter}
      </button>

      {lastStatus && (
        <p className="text-lg">Відмітку збережено: {STATUS_LABELS[lastStatus]}</p>
      )}
      <p className="text-sm text-slate-400">Очікує відправки: {pending}</p>
    </main>
  )
}
