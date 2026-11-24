import { baseApi } from "@/shared/api/baseApi";

// Контракт POST /tutor/ask (бекенд ще дороблюється): усі імена полів зібрано тут.

export type TutorAction = "explain" | "practice" | "check";
export type TutorIntent = TutorAction | "safety";

export interface TutorAskBody {
  /** Новий на кожне надсилання; повтор того самого надсилання бере той самий id (ідемпотентність) */
  request_id: string;
  /** Один на чат модуля */
  conversation_id: string;
  action?: TutorAction;
  lesson_id?: string;
  module_id?: string;
  card_id?: string;
  message?: string;
  /** JPEG/PNG без префікса data:, до 4 МБ */
  image_base64?: string;
}

export interface TutorTask {
  question: string;
  answer_type: string;
  options?: string[] | null;
}

export interface TutorReply {
  request_id: string;
  conversation_id: string;
  /** Markdown */
  reply: string;
  intent: TutorIntent;
  task: TutorTask | null;
  hints_used: number;
  suggestions: string[];
  check_result: { correct: boolean; score: number } | null;
  cached: boolean;
}

/** Помилка після transformErrorResponse: retryAfter — секунди з заголовка Retry-After. */
export interface TutorError {
  status: number | string;
  retryAfter: number | null;
}

export const tutorApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    askTutor: build.mutation<TutorReply, TutorAskBody>({
      query: (body) => ({ url: "/tutor/ask", method: "POST", body }),
      transformErrorResponse: (response, meta): TutorError => {
        const header = (
          meta as { response?: Response } | undefined
        )?.response?.headers.get("Retry-After");
        const seconds = header ? Number.parseInt(header, 10) : NaN;
        return {
          status: response.status,
          retryAfter: Number.isFinite(seconds) ? seconds : null,
        };
      },
    }),
  }),
});

export const { useAskTutorMutation } = tutorApi;
