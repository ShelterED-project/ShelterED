import { useState } from 'react'
import { getErrorCode } from '@/features/auth/errors'
import type { ClassTest } from '@/features/teacher/teacherApi'
import { dateTimeLabel } from '@/shared/lib/date'
import Markdown from '@/shared/ui/Markdown'
import Spinner from '@/shared/ui/Spinner'
import { MIN_ATTEMPTS, analysisText as t } from './content'
import {
  testAnalysisApi,
  useEditTestFeedbackMutation,
  usePublishTestAnalysisMutation,
  useStartTestAnalysisMutation,
  useTestAnalysisQuery,
} from './testAnalysisApi'
import type { AnalysisResult, AnalysisStudent, FeedbackEdit, SkillStatus, StudentLevel, TestAnalysis } from './testAnalysisApi'

/** Поки аналіз processing, питаємо backend (B2) раз на 2 с. */
const POLL_MS = 2_000

const primaryBtn =
  'inline-flex h-9 items-center justify-center gap-2 rounded-[10px] bg-accent px-4 text-sm font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50'
const outlineBtn =
  'inline-flex h-9 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-4 text-sm font-semibold text-parchment hover:border-accent focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none disabled:cursor-not-allowed disabled:opacity-50'
const ghostBtn = 'text-sm font-semibold text-muted underline-offset-4 hover:text-parchment hover:underline disabled:opacity-50'
const subheading = 'text-sm font-semibold text-parchment'

const skillColor: Record<SkillStatus, { text: string; bar: string }> = {
  ok: { text: 'text-safe', bar: 'bg-safe' },
  attention: { text: 'text-accent', bar: 'bg-accent' },
  critical: { text: 'text-danger', bar: 'bg-danger' },
}

const levelColor: Record<StudentLevel, string> = {
  strong: 'text-safe',
  ok: 'text-muted',
  needs_support: 'text-danger',
}

type Names = Map<string, string>

function Bar({ pct, color }: { pct: number; color: string }) {
  return (
    <span className="block h-2 w-full rounded-full bg-line-soft">
      <span className={`block h-2 rounded-full ${color}`} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
    </span>
  )
}

function Kpi({ label, value, accent }: { label: string; value: string; accent?: boolean }) {
  return (
    <div className="rounded-2xl bg-surface-2 p-3">
      <dt className="text-xs text-dim">{label}</dt>
      <dd className={`font-heading text-2xl leading-8 ${accent ? 'text-accent' : 'text-parchment'}`}>{value}</dd>
    </div>
  )
}

function FeedbackEditor({
  label,
  value,
  onChange,
}: {
  label: string
  value: string
  onChange: (value: string) => void
}) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-xs font-semibold text-dim">{label}</span>
      <textarea
        value={value}
        onChange={(e) => onChange(e.target.value)}
        rows={5}
        maxLength={3000}
        className="w-full rounded-xl border border-line bg-oil p-3 text-sm leading-5 text-parchment focus-visible:border-accent focus-visible:outline-none"
      />
    </label>
  )
}

function StudentRow({
  analysis,
  entry,
  name,
  editable,
}: {
  analysis: TestAnalysis
  entry: AnalysisStudent
  name: string
  editable: boolean
}) {
  const [editing, setEditing] = useState(false)
  const [studentText, setStudentText] = useState('')
  const [parentText, setParentText] = useState('')
  const [edit, { isLoading: saving, isError: saveError, reset }] = useEditTestFeedbackMutation()

  function startEdit() {
    setStudentText(entry.feedback.student)
    setParentText(entry.feedback.parent)
    reset()
    setEditing(true)
  }

  async function save(body: FeedbackEdit) {
    const result = await edit({
      classId: analysis.class_id,
      testId: analysis.test_id,
      analysisId: analysis.id,
      studentId: entry.student_id,
      body,
    })
    if ('data' in result) setEditing(false)
  }

  function saveChanges() {
    const body: FeedbackEdit = {}
    if (studentText.trim() !== entry.feedback.student) body.student = studentText.trim()
    if (parentText.trim() !== entry.feedback.parent) body.parent = parentText.trim()
    if (Object.keys(body).length === 0) setEditing(false)
    else void save(body)
  }

  return (
    <details className="group border-t border-line-soft py-3 first:border-t-0">
      <summary className="flex cursor-pointer list-none items-center justify-between gap-3 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none">
        <span className="min-w-0 text-sm text-parchment">
          <span className="mr-1 inline-block text-dim transition-transform group-open:rotate-90">›</span>
          {name}
          {entry.feedback_edited && <span className="ml-2 text-xs text-accent">✍️ {t.edited}</span>}
        </span>
        <span className="shrink-0 text-right text-sm">
          <span className="font-semibold text-parchment">{Math.round(entry.score_pct)}%</span>
          <span className={`block text-xs ${levelColor[entry.status]}`}>{t.level[entry.status]}</span>
        </span>
      </summary>

      <div className="mt-3 flex flex-col gap-3 rounded-2xl bg-surface-2 p-4">
        <div>
          <p className="text-xs font-semibold text-dim">{t.forTeacher}</p>
          <Markdown text={entry.feedback.teacher} className="text-sm leading-5 text-muted" />
        </div>
        {editing ? (
          <>
            <FeedbackEditor label={t.forStudent} value={studentText} onChange={setStudentText} />
            <FeedbackEditor label={t.forParent} value={parentText} onChange={setParentText} />
            {saveError && <p className="text-sm text-danger">{t.saveError}</p>}
            <div className="flex flex-wrap items-center gap-3">
              <button type="button" className={primaryBtn} onClick={saveChanges} disabled={saving}>
                {saving && <Spinner />}
                {t.save}
              </button>
              <button type="button" className={ghostBtn} onClick={() => setEditing(false)} disabled={saving}>
                {t.cancel}
              </button>
            </div>
          </>
        ) : (
          <>
            <div>
              <p className="text-xs font-semibold text-dim">{t.forStudent}</p>
              <Markdown text={entry.feedback.student} className="text-sm leading-5 text-parchment" />
            </div>
            <div>
              <p className="text-xs font-semibold text-dim">{t.forParent}</p>
              <Markdown text={entry.feedback.parent} className="text-sm leading-5 text-parchment" />
            </div>
            {editable && (
              <div className="flex flex-wrap items-center gap-3">
                <button type="button" className={outlineBtn} onClick={startEdit}>
                  ✏️ {t.edit}
                </button>
                {entry.feedback_edited && (
                  <button
                    type="button"
                    className={ghostBtn}
                    onClick={() => void save({ student: null, parent: null })}
                    disabled={saving}
                  >
                    {t.resetToAi}
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </details>
  )
}

function ResultView({ analysis, result, names }: { analysis: TestAnalysis; result: AnalysisResult; names: Names }) {
  const summary = result.class_summary
  const nameOf = (id: string) => names.get(id) ?? t.unknownStudent
  const students = [...result.students].sort((a, b) => a.score_pct - b.score_pct)
  const editable = analysis.status === 'draft'

  return (
    <div className="flex flex-col gap-5">
      <dl className="grid grid-cols-3 gap-2">
        <Kpi label={t.kpiAverage} value={`${Math.round(summary.average_score_pct)}%`} accent />
        <Kpi label={t.kpiPassed} value={t.of(summary.passed_count, summary.students_total)} />
        <Kpi label={t.kpiSupport} value={String(summary.needs_support_ids.length)} />
      </dl>

      <section className="flex flex-col gap-2">
        <h3 className={subheading}>{t.overviewTitle}</h3>
        <Markdown text={summary.overview} className="text-[15px] leading-6 text-parchment" />
        {!result.llm_used && <p className="text-xs text-dim">ℹ️ {t.templateNote}</p>}
      </section>

      {summary.recommendations.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className={subheading}>{t.recommendationsTitle}</h3>
          <ul className="flex list-disc flex-col gap-1.5 pl-5 text-sm leading-5 text-muted marker:text-accent">
            {summary.recommendations.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        </section>
      )}

      {result.skills.length > 0 && (
        <section className="flex flex-col gap-3">
          <h3 className={subheading}>{t.skillsTitle}</h3>
          <ul className="flex flex-col gap-3">
            {result.skills.map((skill) => (
              <li key={skill.skill} className="flex flex-col gap-1.5">
                <div className="flex items-baseline justify-between gap-3 text-sm">
                  <span className="min-w-0 text-parchment">{skill.skill}</span>
                  <span className={`shrink-0 text-xs font-semibold ${skillColor[skill.status].text}`}>
                    {Math.round(skill.correct_pct)}% · {t.skillStatus[skill.status]}
                  </span>
                </div>
                <Bar pct={skill.correct_pct} color={skillColor[skill.status].bar} />
              </li>
            ))}
          </ul>
        </section>
      )}

      {result.misconceptions.length > 0 && (
        <section className="flex flex-col gap-2">
          <h3 className={subheading}>{t.misconceptionsTitle}</h3>
          <ul className="flex flex-col gap-2">
            {result.misconceptions.map((m) => (
              <li key={m.id} className="rounded-2xl border border-line-soft p-3">
                <p className="text-sm font-semibold text-parchment">{m.title}</p>
                <p className="mt-1 text-sm leading-5 text-muted">{m.explanation}</p>
                <p className="mt-2 text-xs text-dim">
                  {t.misconceptionWho(m.student_ids.length, m.share_pct)}: {m.student_ids.map(nameOf).join(', ')}
                </p>
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="flex flex-col gap-1">
        <h3 className={subheading}>{t.studentsTitle}</h3>
        {editable && <p className="text-xs text-dim">{t.studentsHint}</p>}
        <div className="mt-1 flex flex-col">
          {students.map((entry) => (
            <StudentRow
              key={entry.student_id}
              analysis={analysis}
              entry={entry}
              name={nameOf(entry.student_id)}
              editable={editable}
            />
          ))}
        </div>
      </section>
    </div>
  )
}

/**
 * AI-аналіз тесту в розгорнутій картці «Мапи класу» (контракт B1–B4).
 * Монтуйте лише коли картка відкрита: при монтуванні робиться запит B2.
 */
export default function TestAnalysisPanel({ classId, test }: { classId: string; test: ClassTest }) {
  const ref = { classId, testId: test.test_id }
  const submitted = test.counts.passed + test.counts.not_passed
  const names: Names = new Map(
    test.students.map((s) => [s.student_id, [s.display_name, s.last_name].filter(Boolean).join(' ')]),
  )

  const cached = testAnalysisApi.endpoints.testAnalysis.useQueryState(ref)
  const query = useTestAnalysisQuery(ref, {
    pollingInterval: cached.data?.status === 'processing' ? POLL_MS : 0,
    refetchOnMountOrArgChange: true,
  })
  const [start, startState] = useStartTestAnalysisMutation()
  const [publish, publishState] = usePublishTestAnalysisMutation()
  const [confirming, setConfirming] = useState<'publish' | 'rerun' | null>(null)

  const analysis = query.data
  const notFound = query.isError && getErrorCode(query.error) === 'ANALYSIS_NOT_FOUND'
  const startCode = startState.isError ? getErrorCode(startState.error) : undefined

  function run() {
    setConfirming(null)
    void start(ref)
  }

  const shell = 'mt-4 flex flex-col gap-4 rounded-2xl border border-accent/40 bg-accent-soft/40 p-4 md:p-5'

  if (query.isLoading) {
    return (
      <div className="mt-4 flex items-center gap-2 text-sm text-dim">
        <Spinner /> {t.loading}
      </div>
    )
  }

  if (query.isError && !notFound && !analysis) {
    return <p className="mt-4 text-sm text-danger">{t.loadError}</p>
  }

  const startError = startState.isError && (
    <p className="text-sm text-danger">
      {t.startError[startCode ?? ''] ?? t.startError.default}
      {startCode === 'NOT_ENOUGH_ATTEMPTS' && ` ${t.needAttempts(submitted)}`}
    </p>
  )

  // Ще не аналізували: кнопка запуску.
  if (!analysis || notFound) {
    const canRun = submitted >= MIN_ATTEMPTS
    return (
      <div className={shell}>
        <p className="text-sm leading-5 text-muted">{t.intro}</p>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={run} disabled={!canRun || startState.isLoading} className={primaryBtn}>
            {startState.isLoading && <Spinner />}
            {t.run}
          </button>
          {!canRun && <span className="text-xs text-dim">{t.needAttempts(submitted)}</span>}
        </div>
        {startError}
      </div>
    )
  }

  if (analysis.status === 'processing') {
    return (
      <div className={shell} role="status">
        <p className="flex items-center gap-2 text-[15px] font-semibold text-accent">
          <Spinner /> {t.processing}
        </p>
        <p className="text-xs text-dim">{t.processingHint}</p>
      </div>
    )
  }

  if (analysis.status === 'failed' || !analysis.result) {
    const code = analysis.error?.code ?? ''
    return (
      <div className={shell}>
        <p className="text-sm text-danger">⚠️ {t.failed[code] ?? t.failed.default}</p>
        <div>
          <button type="button" onClick={run} disabled={startState.isLoading} className={primaryBtn}>
            {startState.isLoading && <Spinner />}
            {t.retry}
          </button>
        </div>
        {startError}
      </div>
    )
  }

  const isDraft = analysis.status === 'draft'
  return (
    <div className={shell}>
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[15px] font-semibold text-accent">🤖 AI-аналіз тесту</p>
        <span
          className={`rounded-full px-3 py-1 text-xs font-semibold ${isDraft ? 'bg-surface-2 text-muted' : 'bg-safe/15 text-safe'}`}
        >
          {isDraft ? t.draftBadge : t.publishedBadge(dateTimeLabel(analysis.published_at ?? analysis.created_at))}
        </span>
      </div>
      <p className="-mt-2 text-xs text-dim">
        {t.basedOn(analysis.attempts_count, dateTimeLabel(analysis.completed_at ?? analysis.created_at))}
      </p>

      <ResultView analysis={analysis} result={analysis.result} names={names} />

      <div className="flex flex-col gap-3 border-t border-line-soft pt-4">
        {!isDraft && <p className="text-sm text-safe">✅ {t.publishedNote}</p>}
        {confirming && (
          <p className="text-sm text-parchment">{confirming === 'publish' ? t.publishConfirm : t.rerunConfirm}</p>
        )}
        {publishState.isError && <p className="text-sm text-danger">{t.publishError}</p>}
        {startError}
        <div className="flex flex-wrap items-center gap-3">
          {confirming === 'publish' ? (
            <>
              <button
                type="button"
                className={primaryBtn}
                disabled={publishState.isLoading}
                onClick={() => {
                  void publish({ ...ref, analysisId: analysis.id }).then(() => setConfirming(null))
                }}
              >
                {publishState.isLoading && <Spinner />}
                {t.confirm}
              </button>
              <button type="button" className={ghostBtn} onClick={() => setConfirming(null)}>
                {t.cancel}
              </button>
            </>
          ) : confirming === 'rerun' ? (
            <>
              <button type="button" className={primaryBtn} onClick={run}>
                {t.rerun}
              </button>
              <button type="button" className={ghostBtn} onClick={() => setConfirming(null)}>
                {t.cancel}
              </button>
            </>
          ) : (
            <>
              {isDraft && (
                <button type="button" className={primaryBtn} onClick={() => setConfirming('publish')}>
                  📣 {t.publish}
                </button>
              )}
              <button
                type="button"
                className={isDraft ? ghostBtn : outlineBtn}
                disabled={startState.isLoading || submitted < MIN_ATTEMPTS}
                onClick={() => (isDraft ? setConfirming('rerun') : run())}
              >
                {startState.isLoading && <Spinner />}
                {t.rerun}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  )
}
