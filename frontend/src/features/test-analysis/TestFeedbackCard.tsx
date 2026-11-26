import { skipToken } from '@reduxjs/toolkit/query/react'
import { shortDateLabel } from '@/shared/lib/date'
import Markdown from '@/shared/ui/Markdown'
import { feedbackText as t } from './content'
import { useTestFeedbackQuery } from './testAnalysisApi'

const card = 'flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6'
const heading = 'font-heading text-xl leading-7 text-parchment xl:text-[22px]'

/**
 * Опубліковані вчителем розбори тестів (B5). Учню — його текст (studentId = свій id),
 * батькам — текст для батьків (studentId = id дитини). Лише онлайн, без кешу.
 */
export default function TestFeedbackCard({ studentId, audience }: { studentId: string | null; audience: 'student' | 'parent' }) {
  const query = useTestFeedbackQuery(studentId ?? skipToken, { refetchOnMountOrArgChange: true })
  const items = query.data?.items ?? []

  return (
    <section className={card}>
      <h2 className={heading}>📝 {t.title}</h2>
      {query.isError ? (
        <p className="text-sm text-muted">{t.offline}</p>
      ) : query.isLoading ? null : items.length === 0 ? (
        <p className="text-sm text-muted">{audience === 'parent' ? t.emptyParent : t.empty}</p>
      ) : (
        <ul className="flex flex-col">
          {items.map((item, i) => (
            <li key={item.analysis_id} className={`flex flex-col gap-3 py-4 ${i > 0 ? 'border-t border-line-soft' : 'pt-0'}`}>
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[15px] leading-[22.5px] font-medium text-parchment">{item.test_title}</p>
                  <p className="text-xs text-dim">
                    {[item.subject, item.lesson_title].filter(Boolean).join(' · ')} · {shortDateLabel(item.published_at)}
                  </p>
                </div>
                {item.questions_total > 0 && (
                  <p className="shrink-0 rounded-full bg-surface-2 px-3 py-1 text-sm font-semibold text-accent">
                    {t.score(item.correct_count, item.questions_total)}
                  </p>
                )}
              </div>
              <Markdown text={item.text} className="text-sm leading-6 text-muted" />
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
