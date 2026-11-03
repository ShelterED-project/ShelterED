import { useState } from 'react'
import { useNavigate } from 'react-router'
import { useAppDispatch } from '@/app/hooks'
import { useAuthorizeMutation, useFetchMeMutation, useTokenMutation } from './authApi'
import { getErrorMessage, OFFLINE_MESSAGE } from './errors'
import { createCodeChallenge, createCodeVerifier, OAUTH_CLIENT_ID } from './pkce'
import { homeByRole, saveSession, sessionFromTokens } from './session'

/** Вхід вчителя, батьків і адміністрації: OAuth 2.0 Authorization Code + PKCE. */
export function useAdultLogin() {
  const dispatch = useAppDispatch()
  const navigate = useNavigate()
  const [authorize] = useAuthorizeMutation()
  const [exchange] = useTokenMutation()
  const [fetchMe] = useFetchMeMutation()
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string>()

  async function login(email: string, password: string, remember: boolean) {
    setLoading(true)
    setError(undefined)
    try {
      const verifier = createCodeVerifier()
      const { code } = await authorize({
        email,
        password,
        code_challenge: await createCodeChallenge(verifier),
        code_challenge_method: 'S256',
        client_id: OAUTH_CLIENT_ID,
      }).unwrap()
      const tokens = await exchange({
        grant_type: 'authorization_code',
        code,
        code_verifier: verifier,
        client_id: OAUTH_CLIENT_ID,
      }).unwrap()
      const user = await fetchMe(tokens.access_token).unwrap()
      await saveSession(dispatch, sessionFromTokens(tokens, user), remember)
      navigate(homeByRole[user.role], { replace: true })
    } catch (e) {
      // Помилки RTK Query мають status/data; усе інше (напр. немає crypto.subtle) — окреме повідомлення.
      setError(
        e instanceof Error
          ? 'Вхід потребує захищеного зʼєднання (HTTPS)'
          : (getErrorMessage(e as Parameters<typeof getErrorMessage>[0]) || OFFLINE_MESSAGE),
      )
    } finally {
      setLoading(false)
    }
  }

  return { login, loading, error }
}
