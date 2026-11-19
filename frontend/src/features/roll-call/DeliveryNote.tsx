import type { RollCallStatus } from './types'
import type { RollCallDelivery } from './useRollCall'

const t = {
  pending: (label: string) => `Відмітку «${label}» збережено на пристрої. Відправимо, щойно буде звʼязок.`,
  delivered: (label: string) => `Відмітку «${label}» отримано.`,
  // session_closed: перекличку закрито раніше, ніж відмітка дійшла (docs/sync-protocol.md, розділ 6).
  closed: (label: string) => `Перекличку вже завершено, відмітку «${label}» не враховано. Скажи про це вчителю.`,
  rejected: (label: string) => `Відмітку «${label}» не враховано. Скажи про це вчителю.`,
}

/** Стан останньої відмітки під кнопками переклички: у черзі, отримано або не враховано. */
export default function DeliveryNote({
  status,
  delivery,
  labels,
}: {
  status: RollCallStatus | null
  delivery: RollCallDelivery | null
  labels: Record<RollCallStatus, string>
}) {
  if (!status || !delivery) return null
  const label = labels[status]

  if (delivery.state === 'rejected') {
    return (
      <p role="alert" className="text-sm font-semibold text-accent">
        {delivery.reason === 'session_closed' ? t.closed(label) : t.rejected(label)}
      </p>
    )
  }
  return (
    <p role="status" className={`text-sm font-semibold ${delivery.state === 'delivered' ? 'text-safe' : 'text-muted'}`}>
      {delivery.state === 'delivered' ? t.delivered(label) : t.pending(label)}
    </p>
  )
}
