import { useMemo, useSyncExternalStore } from "react";
import { db } from "@/shared/db/db";
import type { PendingCreate, PendingKind } from "@/shared/db/types";
import { saveStatus } from "@/pages/teacher/lessons/saveStatus";
import type {
  CardOut,
  LessonOut,
  ModuleOut,
  QuestionOut,
  TestOut,
} from "./lessonEditorApi";

// Створення модуля, картки, тесту й питання без мережі (offline-first). Запит, що впав через
// мережу, лягає в IndexedDB (id клієнт створив заздалегідь, тож повтор ідемпотентний), а редактор
// показує елемент одразу з позначкою «Чекає мережі». Правки такого елемента зливаються в його
// тіло запиту (текст не губиться). Коли мережа зʼявилась, черга відправляється в порядку
// створення: батько перед дітьми.

type Args = Record<string, unknown>;
type Result = { data: unknown } | { error: unknown };

const entries = new Map<string, PendingCreate>();
const listeners = new Set<() => void>();
let version = 0;
let seqCounter = 0;
/** Id, які відправляє черга просто зараз: їхні запити йдуть напряму. */
const bypass = new Set<string>();
/** Відправка в польоті: правки цього елемента чекають її завершення. */
const inflight = new Map<string, Promise<unknown>>();

const SAVE_KEY = "pending-creates";

function emit() {
  version++;
  if (entries.size > 0) saveStatus.fail(SAVE_KEY);
  else saveStatus.clear(SAVE_KEY);
  for (const l of listeners) l();
}

const persist = (entry: PendingCreate) =>
  void db.pendingCreates.put(entry).catch(() => undefined);

function remove(id: string) {
  if (!entries.delete(id)) return;
  void db.pendingCreates.delete(id).catch(() => undefined);
}

/** Завантажити чергу з IndexedDB (після перезапуску вкладки). */
export async function loadPending(): Promise<void> {
  try {
    for (const e of await db.pendingCreates.toArray()) {
      if (!entries.has(e.id)) entries.set(e.id, e);
      seqCounter = Math.max(seqCounter, e.seq);
    }
  } catch {
    // Без IndexedDB черга живе лише в памʼяті.
  }
  emit();
}

export function isNetworkFailure(error: unknown): boolean {
  const status = (error as { status?: unknown } | null)?.status;
  return (
    status === "FETCH_ERROR" ||
    status === "TIMEOUT_ERROR" ||
    (typeof status === "number" && status >= 500)
  );
}

interface Route {
  kind: PendingKind;
  parentId: string;
}

function createRoute(url: string): Route | null {
  let m = /^\/lessons\/([^/]+)\/modules$/.exec(url);
  if (m) return { kind: "module", parentId: m[1] };
  m = /^\/modules\/([^/]+)\/cards$/.exec(url);
  if (m) return { kind: "card", parentId: m[1] };
  m = /^\/lessons\/([^/]+)\/tests$/.exec(url);
  if (m) return { kind: "test", parentId: m[1] };
  m = /^\/tests\/([^/]+)\/questions$/.exec(url);
  if (m) return { kind: "question", parentId: m[1] };
  return null;
}

const ITEM_URL = /^\/(modules|cards|tests|questions)\/([^/]+)$/;

/** Елемент для відповіді «створено» й для показу в редакторі. */
function materialize(
  e: PendingCreate,
): ModuleOut | CardOut | TestOut | QuestionOut {
  const b = e.body;
  switch (e.kind) {
    case "module":
      return {
        cards: [],
        ...b,
        id: e.id,
        lesson_id: e.parentId,
      } as unknown as ModuleOut;
    case "card":
      return {
        media: null,
        ...b,
        id: e.id,
        module_id: e.parentId,
      } as unknown as CardOut;
    case "test":
      return {
        questions: [],
        ...b,
        id: e.id,
        lesson_id: e.parentId,
      } as unknown as TestOut;
    case "question":
      return { ...b, id: e.id, test_id: e.parentId } as unknown as QuestionOut;
  }
}

function descendants(id: string): string[] {
  const out: string[] = [];
  for (const e of entries.values())
    if (e.parentId === id) out.push(e.id, ...descendants(e.id));
  return out;
}

type Query = string | { url: string; method?: string; body?: unknown };

/**
 * Обгортка над мережевим запитом редактора: створення, що впало через мережу, ставить у чергу
 * й відповідає «успіхом»; правки й видалення ще не створеного елемента лишаються в черзі.
 */
export async function interceptEditorRequest(
  args: Query,
  send: () => Promise<Result>,
): Promise<Result> {
  if (typeof args === "string") return send();
  const method = (args.method ?? "GET").toUpperCase();
  const body = (args.body ?? null) as Args | null;

  if (method === "POST") {
    const route = createRoute(args.url);
    const id = typeof body?.id === "string" ? body.id : null;
    if (!route || !body || !id) return send();
    if (bypass.has(id)) return send();
    const existing = entries.get(id);
    if (existing) return { data: materialize(existing) };
    // Батько ще в черзі: на сервері його немає, не пробуємо.
    if (!entries.has(route.parentId)) {
      const result = await send();
      if (!("error" in result) || !isNetworkFailure(result.error))
        return result;
    }
    const entry: PendingCreate = {
      id,
      seq: ++seqCounter,
      ...route,
      body,
      error: null,
    };
    entries.set(id, entry);
    persist(entry);
    emit();
    return { data: materialize(entry) };
  }

  if (method === "PATCH" || method === "DELETE") {
    const m = ITEM_URL.exec(args.url);
    if (!m) return send();
    const id = m[2];
    await inflight.get(id)?.catch(() => undefined);
    const entry = entries.get(id);
    if (!entry) return send();
    if (method === "DELETE") {
      for (const x of [id, ...descendants(id)]) remove(x);
      emit();
      return { data: null };
    }
    const next: PendingCreate = {
      ...entry,
      body: { ...entry.body, ...(body ?? {}) },
      error: null,
    };
    entries.set(id, next);
    persist(next);
    emit();
    return { data: materialize(next) };
  }
  return send();
}

const subscribe = (l: () => void) => {
  listeners.add(l);
  return () => listeners.delete(l);
};

/** Стан елемента в черзі: чекає мережі чи відхилений сервером (error). */
export function usePendingEntry(id: string): { error: string | null } | null {
  useSyncExternalStore(subscribe, () => version);
  const e = entries.get(id);
  return e ? { error: e.error } : null;
}

/** Урок разом з елементами, що ще чекають створення на сервері. */
export function usePendingLesson(
  lesson: LessonOut | undefined,
): LessonOut | undefined {
  const v = useSyncExternalStore(subscribe, () => version);
  return useMemo(() => {
    void v;
    if (!lesson || entries.size === 0) return lesson;
    const list = [...entries.values()].sort((a, b) => a.seq - b.seq);
    const ids = new Set(list.map((e) => e.id));
    const modules = lesson.modules
      .filter((m) => !ids.has(m.id))
      .map((m) => ({ ...m, cards: m.cards.filter((c) => !ids.has(c.id)) }));
    const tests = lesson.tests
      .filter((t) => !ids.has(t.id))
      .map((t) => ({
        ...t,
        questions: t.questions.filter((q) => !ids.has(q.id)),
      }));
    for (const e of list) {
      if (e.kind === "module" && e.parentId === lesson.id)
        modules.push(materialize(e) as ModuleOut);
      if (e.kind === "test" && e.parentId === lesson.id)
        tests.push(materialize(e) as TestOut);
    }
    for (const e of list) {
      if (e.kind === "card")
        modules
          .find((m) => m.id === e.parentId)
          ?.cards.push(materialize(e) as CardOut);
      if (e.kind === "question")
        tests
          .find((t) => t.id === e.parentId)
          ?.questions.push(materialize(e) as QuestionOut);
    }
    return { ...lesson, modules, tests };
  }, [lesson, v]);
}

export type SendOutcome =
  | { ok: true }
  | { ok: false; network: true }
  | { ok: false; network: false; message: string };

let flushing: Promise<void> | null = null;

export function hasPending(): boolean {
  return entries.size > 0;
}

/** Відправити чергу по порядку створення; зупиняємось на першій мережевій помилці. */
export function flushPending(
  send: (entry: PendingCreate) => Promise<SendOutcome>,
): Promise<void> {
  flushing ??= (async () => {
    try {
      for (const entry of [...entries.values()].sort((a, b) => a.seq - b.seq)) {
        const current = entries.get(entry.id);
        if (!current || current.error) continue;
        // Батько ще не створений (відхилений): діти чекають.
        if (entries.has(current.parentId)) continue;
        bypass.add(current.id);
        const sending = send(current);
        inflight.set(current.id, sending);
        let outcome: SendOutcome;
        try {
          outcome = await sending;
        } finally {
          bypass.delete(current.id);
          inflight.delete(current.id);
        }
        if (outcome.ok) {
          remove(current.id);
          emit();
        } else if (outcome.network) {
          break;
        } else {
          const failed = {
            ...(entries.get(current.id) ?? current),
            error: outcome.message,
          };
          entries.set(failed.id, failed);
          persist(failed);
          emit();
        }
      }
    } finally {
      flushing = null;
    }
  })();
  return flushing;
}
