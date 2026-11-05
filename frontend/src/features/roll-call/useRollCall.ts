import { useState } from 'react'
import { markStatus } from './rollCall'
import type { RollCallStatus } from './types'

/** Відмітка в перекличці: пише подію в outbox і памʼятає останній вибраний статус. */
export function useRollCall() {
  const [lastStatus, setLastStatus] = useState<RollCallStatus | null>(null)

  const mark = async (status: RollCallStatus) => {
    await markStatus(status)
    setLastStatus(status)
  }

  return { lastStatus, mark }
}
