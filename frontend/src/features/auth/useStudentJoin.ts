import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDispatch } from '@/app/hooks'
import { useFetchMeMutation, useStudentJoinMutation } from './authApi'
import { getErrorMessage } from './errors'
import { homeByRole, saveSession, sessionFromTokens } from './session'
import type { StudentJoinRequest } from './types'

/** Вхід учня: код класу + імʼя + прізвище + PIN. Нового учня бекенд створює сам. */
export function useStudentJoin() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [join] = useStudentJoinMutation()
  const [fetchMe] = useFetchMeMutation()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()

  async function submit(data: StudentJoinRequest) {
    setLoading(true)
    setError(undefined)
    try {
      const tokens = await join(data).unwrap()
      const user = await fetchMe(tokens.access_token).unwrap()
      // Сесію учня зберігаємо завжди: в укритті застосунок має відкриватися без мережі.
      await saveSession(dispatch, sessionFromTokens(tokens, user), true)
      navigate(homeByRole[user.role], { replace: true })
    } catch (e) {
      setError(getErrorMessage(e as Parameters<typeof getErrorMessage>[0]))
    } finally {
      setLoading(false)
    }
  }

  return { submit, loading, error }
}
