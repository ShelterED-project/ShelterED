import iconBook from '@/assets/parent/kpi-book.svg'
import iconChart from '@/assets/parent/kpi-chart.svg'
import iconClock from '@/assets/parent/kpi-clock.svg'
import iconMap from '@/assets/parent/kpi-map.svg'
import type { KnowledgeMap, StudentProgress } from '@/features/student/studentApi'
import { kpis as t } from '../content'

const WEEK_MS = 7 * 24 * 60 * 60 * 1000

type Kpi = { label: string; value: string; hint: string; icon: string; accent?: boolean }

function buildKpis(progress: StudentProgress | null, map: KnowledgeMap | null): Kpi[] {
  const lessons = progress?.lessons ?? []
  const weekAgo = Date.now() - WEEK_MS
  const doneThisWeek = lessons.filter((l) => l.completed_at && new Date(l.completed_at).getTime() >= weekAgo).length
  const started = lessons.filter((l) => l.modules_done > 0).length
  const scored = (progress?.tests ?? []).filter((test) => test.score !== null)
  const avg = scored.length ? Math.round(scored.reduce((sum, test) => sum + (test.score ?? 0), 0) / scored.length) : null
  const gaps = (map?.subjects ?? []).filter((s) => s.is_gap).length

  return [
    { label: t.lessons.label, value: progress ? String(doneThisWeek) : '—', hint: t.lessons.hint(started), icon: iconBook },
    {
      label: t.time.label,
      value: progress ? t.time.value(progress.study.last_7_days_minutes) : '—',
      hint: t.time.hint(progress?.study.total_minutes ?? 0),
      icon: iconClock,
    },
    { label: t.score.label, value: avg === null ? '—' : `${avg}%`, hint: t.score.hint(scored.length), icon: iconChart },
    { label: t.gaps.label, value: map ? String(gaps) : '—', hint: t.gaps.hint(gaps), icon: iconMap, accent: gaps > 0 },
  ]
}

export default function Kpis({ progress, knowledgeMap }: { progress: StudentProgress | null; knowledgeMap: KnowledgeMap | null }) {
  return (
    <ul className="grid grid-cols-2 gap-3 md:gap-4 lg:grid-cols-4">
      {buildKpis(progress, knowledgeMap).map((kpi) => (
        <li key={kpi.label} className="flex flex-col gap-2 rounded-[18px] border border-line bg-surface p-4 md:p-5">
          <div className="flex items-center justify-between gap-2">
            <p className="text-sm leading-5 text-dim">{kpi.label}</p>
            <img src={kpi.icon} alt="" width={18} height={18} className="shrink-0" />
          </div>
          <p
            className={`font-heading text-2xl leading-6 tracking-[-0.24px] md:text-[28px] md:leading-7 md:tracking-[-0.28px] ${
              kpi.accent ? 'text-accent' : 'text-parchment'
            }`}
          >
            {kpi.value}
          </p>
          <p className="text-xs text-dim">{kpi.hint}</p>
        </li>
      ))}
    </ul>
  )
}
