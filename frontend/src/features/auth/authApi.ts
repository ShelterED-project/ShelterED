import { baseApi } from '@/shared/api/baseApi'
import type {
  AdminCreateUserRequest,
  AuthorizeRequest,
  AuthorizeResponse,
  ParentLinkResponse,
  StudentJoinRequest,
  TokenRequest,
  TokenResponse,
  User,
} from './types'

export const authApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    authorize: build.mutation<AuthorizeResponse, AuthorizeRequest>({
      query: (body) => ({ url: '/auth/authorize', method: 'POST', body }),
    }),
    token: build.mutation<TokenResponse, TokenRequest>({
      query: (body) => ({ url: '/auth/token', method: 'POST', body }),
    }),
    logout: build.mutation<void, { refresh_token: string }>({
      query: (body) => ({ url: '/auth/logout', method: 'POST', body }),
    }),
    me: build.query<User, void>({
      query: () => '/auth/me',
    }),
    // Токен ще не в сторі (вхід у процесі), тому передаємо його явно.
    fetchMe: build.mutation<User, string>({
      query: (accessToken) => ({ url: '/auth/me', headers: { Authorization: `Bearer ${accessToken}` } }),
    }),
    createUser: build.mutation<User, AdminCreateUserRequest>({
      query: (body) => ({ url: '/admin/users', method: 'POST', body }),
    }),
    parentLink: build.mutation<ParentLinkResponse, { code: string }>({
      query: (body) => ({ url: '/parent/link', method: 'POST', body }),
    }),
    studentJoin: build.mutation<TokenResponse, StudentJoinRequest>({
      query: (body) => ({ url: '/auth/student/join', method: 'POST', body }),
    }),
  }),
})

export const {
  useAuthorizeMutation,
  useTokenMutation,
  useLogoutMutation,
  useMeQuery,
  useFetchMeMutation,
  useCreateUserMutation,
  useParentLinkMutation,
  useStudentJoinMutation,
} = authApi
