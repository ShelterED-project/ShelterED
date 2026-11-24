import { useEffect } from "react";
import { useAppDispatch } from "@/app/hooks";
import {
  errorMessage,
  isNetworkError,
  lessonEditorApi,
  lessonQueryApi,
} from "@/features/teacher/lessonEditorApi";
import {
  flushPending,
  hasPending,
  loadPending,
} from "@/features/teacher/pendingCreates";
import type { SendOutcome } from "@/features/teacher/pendingCreates";
import type { PendingCreate } from "@/shared/db/types";

/** Як часто пробуємо, поки в черзі є створення, що чекають мережі. */
const RETRY_MS = 5000;

/**
 * Відправляє створення, що чекали мережі (див. pendingCreates): при відкритті редактора, коли
 * зʼявилась мережа й раз на кілька секунд, доки черга не порожня. Після успіху оновлює урок.
 */
export function usePendingSync() {
  const dispatch = useAppDispatch();

  useEffect(() => {
    const e = lessonEditorApi.endpoints;
    const send = async (entry: PendingCreate): Promise<SendOutcome> => {
      const b = entry.body;
      type Arg<T extends { initiate: (a: never) => unknown }> = Parameters<
        T["initiate"]
      >[0];
      // Поля тіла вже відповідають запиту; lessonId потрібен лише для тегів кешу.
      const action =
        entry.kind === "module"
          ? e.createModule.initiate({ ...b, lessonId: entry.parentId } as Arg<
              typeof e.createModule
            >)
          : entry.kind === "card"
            ? e.createCard.initiate({
                ...b,
                lessonId: "",
                moduleId: entry.parentId,
              } as Arg<typeof e.createCard>)
            : entry.kind === "test"
              ? e.createTest.initiate({ ...b, lessonId: entry.parentId } as Arg<
                  typeof e.createTest
                >)
              : e.createQuestion.initiate({
                  ...b,
                  lessonId: "",
                  testId: entry.parentId,
                } as Arg<typeof e.createQuestion>);
      try {
        await dispatch(
          action as never as ReturnType<typeof e.createModule.initiate>,
        ).unwrap();
        return { ok: true };
      } catch (err) {
        return isNetworkError(err)
          ? { ok: false, network: true }
          : { ok: false, network: false, message: errorMessage(err) };
      }
    };
    const run = () => {
      if (!hasPending()) return;
      void flushPending(send).then(() => {
        dispatch(lessonQueryApi.util.invalidateTags(["Lesson"]));
      });
    };
    void loadPending().then(run);
    window.addEventListener("online", run);
    const timer = window.setInterval(run, RETRY_MS);
    return () => {
      window.removeEventListener("online", run);
      window.clearInterval(timer);
    };
  }, [dispatch]);
}
