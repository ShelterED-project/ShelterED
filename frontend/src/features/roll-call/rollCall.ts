import { addEvent } from '@/shared/db/outbox'
import type { RollCallStatus } from './types'

export function markStatus(status: RollCallStatus) {
  return addEvent('roll_call.marked', { status })
}
