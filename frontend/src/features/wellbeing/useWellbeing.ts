import { useEffect } from 'react'
import { skipToken } from '@reduxjs/toolkit/query/react'
import { useLiveQuery } from 'dexie-react-hooks'
import { useAppSelector } from '@/app/hooks'
import { db } from '@/shared/db/db'
import { addEvent } from '@/shared/db/outbox'
import { useWellbeingSelfQuery, useWellbeingTextsQuery } from './wellbeingApi'
import type { WellbeingSelf, WellbeingTexts, WellbeingValue } from './wellbeingApi'

const TEXTS_KEY = 'wellbeing_texts'
const selfKey = (studentId: string) => `wellbeing_self:${studentId}`
/** Лише дата останньої відповіді (не сама відповідь): щоб не питати двічі за день. */
const answeredKey = (studentId: string) => `wellbeing_answered:${studentId}`

function todayKey(): string {
  return new Date().toLocaleDateString('sv-SE')
}

async function readMeta<T>(key: string): Promise<T | null> {
  const record = await db.meta.get(key)
  return (record?.value as T | undefined) ?? null
}

function useCached<T>(key: string | null, fresh: T | undefined): T | null {
  const cached = useLiveQuery(async () => (key ? readMeta<T>(key) : null), [key])
  useEffect(() => {
    if (key && fresh) void db.meta.put({ key, value: fresh }).catch(() => undefined)
  }, [key, fresh])
  return fresh ?? cached ?? null
}

/**
 * «Як ти зараз?» для учня. Тексти й свої картинки кешуються в IndexedDB, тож сторінка працює
 * офлайн. Відповідь — подія survey_answer в outbox (принцип 4), сама відповідь на пристрої
 * не зберігається, лише дата. Без опитування сервера й без нагадувань.
 */
export function useWellbeing() {
  const studentId = useAppSelector((s) => s.auth.session?.user.id)
  const textsQuery = useWellbeingTextsQuery()
  const selfQuery = useWellbeingSelfQuery(studentId ?? skipToken, { refetchOnMountOrArgChange: true })

  const texts = useCached<WellbeingTexts>(TEXTS_KEY, textsQuery.data)
  const self = useCached<WellbeingSelf>(studentId ? selfKey(studentId) : null, selfQuery.data)
  const answeredOn = useLiveQuery(
    async () => (studentId ? readMeta<string>(answeredKey(studentId)) : null),
    [studentId],
  )

  const answer = async (value: WellbeingValue) => {
    if (!studentId) return
    await db.transaction('rw', db.events, db.meta, async () => {
      await addEvent('survey_answer', studentId, { value })
      await db.meta.put({ key: answeredKey(studentId), value: todayKey() })
    })
  }

  return {
    texts,
    self,
    answeredToday: answeredOn === todayKey(),
    answer,
  }
}
