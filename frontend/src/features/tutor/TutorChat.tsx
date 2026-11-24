import { useEffect, useRef, useState } from "react";
import { useLiveQuery } from "dexie-react-hooks";
import { db } from "@/shared/db/db";
import { generateId } from "@/shared/lib/uuid";
import Markdown from "@/shared/ui/Markdown";
import { tutor as t } from "./content";
import { photoToBase64 } from "./image";
import { useAskTutorMutation } from "./tutorApi";
import type {
  TutorAction,
  TutorAskBody,
  TutorError,
  TutorReply,
  TutorTask,
} from "./tutorApi";

interface Line {
  id: string;
  role: "you" | "tutor";
  text: string;
  /** Службова відповідь (помилка, результат): без Markdown-розмітки репетитора */
  note?: boolean;
}

interface Props {
  lessonId: string;
  moduleId: string;
  cardId?: string;
}

const bigButton =
  "flex min-h-14 items-center justify-center rounded-[10px] px-5 text-base font-semibold focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:opacity-50";
const outline = `${bigButton} border border-line-strong text-parchment hover:bg-surface-2`;
const primary = `${bigButton} bg-accent font-bold text-oil focus-visible:ring-parchment/60`;

/** Один чат на модуль: id розмови живе в sessionStorage, текст чату лише в памʼяті. */
function conversationFor(moduleId: string): string {
  const key = `tutor-conv:${moduleId}`;
  try {
    const saved = sessionStorage.getItem(key);
    if (saved) return saved;
    const fresh = generateId();
    sessionStorage.setItem(key, fresh);
    return fresh;
  } catch {
    return generateId();
  }
}

/** Пояснення модуля з Рюкзака (пакет на пристрої). */
function useCachedExplanation(
  lessonId: string,
  moduleId: string,
): string | null {
  return (
    useLiveQuery(async () => {
      const packs = await db.packs.toArray();
      let lessonLevel: string | null = null;
      for (const pack of packs) {
        for (const e of pack.explanations ?? []) {
          if (e.lesson_id !== lessonId) continue;
          if (e.module_id === moduleId) return e.text;
          if (e.module_id === null) lessonLevel = e.text;
        }
      }
      return lessonLevel;
    }, [lessonId, moduleId]) ?? null
  );
}

export default function TutorChat({ lessonId, moduleId, cardId }: Props) {
  const [open, setOpen] = useState(false);
  const [lines, setLines] = useState<Line[]>([]);
  const [task, setTask] = useState<TutorTask | null>(null);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [safety, setSafety] = useState(false);
  const [answer, setAnswer] = useState("");
  const [busy, setBusy] = useState(false);
  const [failed, setFailed] = useState<TutorAskBody | null>(null);
  const [waitLeft, setWaitLeft] = useState(0);
  const [conversationId] = useState(() => conversationFor(moduleId));
  const [ask] = useAskTutorMutation();
  const cached = useCachedExplanation(lessonId, moduleId);
  const endRef = useRef<HTMLDivElement>(null);
  const photoRef = useRef<HTMLInputElement>(null);

  const locked = busy || waitLeft > 0;

  useEffect(() => {
    if (waitLeft <= 0) return;
    const id = setTimeout(() => setWaitLeft((n) => n - 1), 1000);
    return () => clearTimeout(id);
  }, [waitLeft]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [lines, busy, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  const push = (line: Omit<Line, "id">) =>
    setLines((prev) => [...prev, { ...line, id: generateId() }]);

  const apply = (reply: TutorReply) => {
    push({ role: "tutor", text: reply.reply });
    setSuggestions(reply.suggestions);
    if (reply.intent === "safety") {
      setSafety(true);
      setTask(null);
      return;
    }
    setSafety(false);
    if (reply.check_result) {
      push({
        role: "tutor",
        text: reply.check_result.correct ? t.correct : t.wrong,
        note: true,
      });
      if (reply.check_result.correct) setTask(null);
    } else if (reply.task) {
      setTask(reply.task);
      setAnswer("");
    }
  };

  const fallback = (error: TutorError | null) => {
    if (error?.status === 429) {
      const seconds = error.retryAfter;
      setWaitLeft(seconds ?? 10);
      push({ role: "tutor", text: t.tooMany(seconds), note: true });
      return;
    }
    // Мережі немає або ШІ недоступний: пояснення з Рюкзака, без лякаючих помилок.
    if (cached) {
      push({ role: "tutor", text: `**${t.cachedLabel}**\n\n${cached}` });
    } else {
      push({ role: "tutor", text: t.unavailable, note: true });
    }
  };

  const send = async (body: TutorAskBody, shown?: string) => {
    if (locked) return;
    if (shown) push({ role: "you", text: shown });
    setBusy(true);
    setFailed(null);
    setSuggestions([]);
    try {
      if (!navigator.onLine)
        throw { status: "FETCH_ERROR", retryAfter: null } satisfies TutorError;
      apply(await ask(body).unwrap());
    } catch (e) {
      const error = (
        e && typeof e === "object" && "status" in e ? e : null
      ) as TutorError | null;
      if (error?.status !== 429) setFailed(body);
      fallback(error);
    } finally {
      setBusy(false);
    }
  };

  const base = (
    action: TutorAction | undefined,
    extra: Partial<TutorAskBody> = {},
  ): TutorAskBody => ({
    request_id: generateId(),
    conversation_id: conversationId,
    action,
    lesson_id: lessonId,
    module_id: moduleId,
    card_id: cardId,
    ...extra,
  });

  const sendAnswer = (text: string) => {
    const message = text.trim();
    if (!message) return;
    setAnswer("");
    void send(base("check", { message }), message);
  };

  const onPhoto = async (file: File | undefined) => {
    if (!file) return;
    try {
      const image = await photoToBase64(file);
      void send(base("check", { image_base64: image }), t.photoSent);
    } catch {
      push({ role: "tutor", text: t.photoFailed, note: true });
    }
  };

  const options = task?.options ?? [];

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={`${outline} w-full gap-2`}
      >
        <span aria-hidden="true">💡</span>
        {t.open}
      </button>

      {open && (
        <div
          className="fixed inset-0 z-50 flex items-end bg-oil/70 md:justify-end"
          onClick={() => setOpen(false)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={t.title}
            onClick={(e) => e.stopPropagation()}
            className="flex max-h-[90dvh] w-full flex-col rounded-t-3xl border border-line bg-surface md:h-full md:max-h-none md:max-w-[440px] md:rounded-none"
          >
            <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-3">
              <h2 className="font-heading text-xl text-parchment">{t.title}</h2>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className={`${outline} min-h-12`}
              >
                {t.close}
              </button>
            </div>

            <div className="flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-5 py-4">
              <p className="text-base leading-6 text-muted">{t.hello}</p>
              {lines.map((line) => (
                <div
                  key={line.id}
                  className={
                    line.role === "you"
                      ? "ml-8 self-end rounded-2xl bg-accent-soft px-4 py-3 text-base text-parchment"
                      : `mr-4 rounded-2xl bg-surface-2 px-4 py-3 text-base leading-6 ${line.note ? "text-muted" : "text-parchment"}`
                  }
                >
                  {line.role === "you" || line.note ? (
                    line.text
                  ) : (
                    <Markdown text={line.text} />
                  )}
                </div>
              ))}
              {busy && <p className="text-sm text-dim">{t.thinking}</p>}
              {waitLeft > 0 && (
                <p className="text-sm text-dim">{t.tooMany(waitLeft)}</p>
              )}

              {task && !safety && (
                <div className="rounded-2xl border border-accent/40 p-4">
                  <p className="text-xs font-semibold tracking-wide text-accent uppercase">
                    {t.taskLabel}
                  </p>
                  <p className="mt-1 text-base leading-6 text-parchment">
                    {task.question}
                  </p>
                </div>
              )}

              {safety && (
                <p className="rounded-2xl bg-surface-2 px-4 py-3 text-base leading-6 text-muted">
                  {t.safety}
                </p>
              )}

              {failed && !busy && waitLeft === 0 && (
                <button
                  type="button"
                  className={outline}
                  onClick={() => void send(failed)}
                >
                  {t.retry}
                </button>
              )}
              <div ref={endRef} />
            </div>

            {!safety && (
              <div className="flex max-h-[55dvh] shrink-0 flex-col gap-3 overflow-y-auto border-t border-line px-5 py-4">
                <div className="grid grid-cols-2 gap-3">
                  <button
                    type="button"
                    disabled={locked}
                    onClick={() => void send(base("explain"))}
                    className={outline}
                  >
                    {t.explain}
                  </button>
                  <button
                    type="button"
                    disabled={locked}
                    onClick={() => void send(base("practice"))}
                    className={outline}
                  >
                    {t.practice}
                  </button>
                </div>
                {suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {suggestions.map((s) => (
                      <button
                        key={s}
                        type="button"
                        disabled={locked}
                        onClick={() =>
                          void send(base(undefined, { message: s }), s)
                        }
                        className="min-h-11 rounded-full border border-line-strong px-4 text-sm text-parchment hover:bg-surface-2 disabled:opacity-50"
                      >
                        {s}
                      </button>
                    ))}
                  </div>
                )}

                {task && (
                  <>
                    {options.length > 0 ? (
                      <div className="flex flex-col gap-2">
                        {options.map((o) => (
                          <button
                            key={o}
                            type="button"
                            disabled={locked}
                            onClick={() => sendAnswer(o)}
                            className={outline}
                          >
                            {o}
                          </button>
                        ))}
                      </div>
                    ) : (
                      <form
                        className="flex flex-col gap-2"
                        onSubmit={(e) => {
                          e.preventDefault();
                          sendAnswer(answer);
                        }}
                      >
                        <input
                          value={answer}
                          onChange={(e) => setAnswer(e.target.value)}
                          aria-label={t.answerLabel}
                          placeholder={t.answerPlaceholder}
                          maxLength={2000}
                          className="h-14 rounded-[10px] border border-line-strong bg-oil px-4 text-base text-parchment placeholder:text-dim focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
                        />
                        <button
                          type="submit"
                          disabled={locked || answer.trim() === ""}
                          className={primary}
                        >
                          {t.check}
                        </button>
                      </form>
                    )}
                    <input
                      ref={photoRef}
                      type="file"
                      accept="image/*"
                      capture="environment"
                      className="hidden"
                      onChange={(e) => {
                        void onPhoto(e.target.files?.[0]);
                        e.target.value = "";
                      }}
                    />
                    <button
                      type="button"
                      disabled={locked}
                      onClick={() => photoRef.current?.click()}
                      className={outline}
                    >
                      <span aria-hidden="true" className="mr-2">
                        📷
                      </span>
                      {t.photo}
                    </button>
                  </>
                )}
              </div>
            )}
          </div>
        </div>
      )}
    </>
  );
}
