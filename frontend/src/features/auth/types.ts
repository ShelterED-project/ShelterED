export type Role = 'student' | 'teacher' | 'parent' | 'admin'

/** Відповідь `GET /auth/me` (backend/app/schemas/auth.py: MeOut; інші ендпоінти віддають UserOut без class_id). */
export interface User {
  id: string
  role: Role
  display_name: string
  last_name: string | null
  school_id: string | null
  /** Клас учня; для інших ролей null. Немає в сесіях, збережених до появи поля: потрібен повторний вхід. */
  class_id?: string | null
}

export interface TokenResponse {
  access_token: string
  refresh_token: string
  token_type: 'bearer'
  /** Час життя access-токена, секунди */
  expires_in: number
}

export interface AuthorizeRequest {
  email: string
  password: string
  code_challenge: string
  code_challenge_method: 'S256'
  client_id: string
  redirect_uri?: string
}

export interface AuthorizeResponse {
  code: string
}

export interface TokenRequest {
  grant_type: 'authorization_code' | 'refresh_token'
  code?: string
  code_verifier?: string
  client_id?: string
  redirect_uri?: string
  refresh_token?: string
}

export interface StudentJoinRequest {
  join_code: string
  display_name: string
  last_name: string
  /** 4–6 цифр */
  pin: string
}

export interface AdminCreateUserRequest {
  email: string
  display_name: string
  last_name?: string
  role: 'teacher' | 'parent' | 'admin'
  /** Початковий пароль, 8–128 символів */
  password: string
}

export interface ParentLinkResponse {
  child_id: string
  display_name: string
  last_name: string | null
}

/** Тіло помилки бекенда (backend/app/schemas/errors.py). */
export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown }
}
