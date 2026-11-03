import { createSlice } from '@reduxjs/toolkit'
import type { PayloadAction } from '@reduxjs/toolkit'
import type { User } from './types'

export interface Session {
  accessToken: string
  refreshToken: string
  /** Коли спливає access-токен, мс (Date.now()) */
  expiresAt: number
  user: User
}

export interface AuthState {
  session: Session | null
  /** Чи збережено сесію в IndexedDB (для входу без мережі) */
  persisted: boolean
}

const initialState: AuthState = { session: null, persisted: false }

const authSlice = createSlice({
  name: 'auth',
  initialState,
  reducers: {
    sessionSet(state, action: PayloadAction<{ session: Session; persisted: boolean }>) {
      state.session = action.payload.session
      state.persisted = action.payload.persisted
    },
    sessionCleared(state) {
      state.session = null
      state.persisted = false
    },
  },
})

export const { sessionSet, sessionCleared } = authSlice.actions
export default authSlice.reducer
