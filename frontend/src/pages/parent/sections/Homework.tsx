import { Link } from 'react-router'
import mole from '@/assets/landing/mole.svg'
import type { KnowledgeMap, StudentProgress } from '@/features/student/studentApi'
import { homework, navRoutes, testStatus } from '../content'

/** Скільки пунктів на огляді; решта — на сторінці «Прогрес». */
const LIMIT = 4

type Props = { progress: StudentProgress | null; knowledgeMap: KnowledgeMap | null; className?: string }

export default function Homework({ progress, knowledgeMap, className = '' }: Props) {
  const gaps = (knowledgeMap?.subjects ?? []).filter((s) => s.is_gap).map((s) => ({ id: s.subject_id, ...homework.gap(s.name) }))
  const tests = (progress?.tests ?? [])
    .filter((test) => test.status === 'not_passed' || test.status === 'closing_soon')
    .map((test) => ({ id: test.test_id, ...homework.test(test.title, testStatus[test.status]) }))
  const items = [...tests, ...gaps]

  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
          {homework.title}
        </h2>
        <Link
          to={navRoutes.progress ?? '/parent'}
          className="rounded text-sm font-semibold text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {homework.all}
        </Link>
      </div>

      {items.length > 0 && (
        <ul className="flex flex-col gap-2">
          {items.slice(0, LIMIT).map((item) => (
            <li key={item.id} className="flex items-center gap-3 rounded-[14px] border border-line bg-surface-2/60 p-3">
              <span className="size-9 shrink-0 rounded-full border-2 border-dashed border-muted" />
              <div className="min-w-0 flex-1">
                <p className="text-[15px] leading-[22.5px] font-semibold text-parchment">{item.title}</p>
                <p className="text-xs text-dim">{item.note}</p>
              </div>
            </li>
          ))}
        </ul>
      )}

      <div className="flex items-end gap-3">
        <img
          src={mole}
          alt="Кріт — маскот ShelterED"
          width={64}
          height={64}
          className="size-16 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]"
        />
        <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[19px] leading-[1.25] font-semibold text-parchment md:text-[22px]">
          {homework.moleSays(items.length)}
        </p>
      </div>
    </section>
  )
}
