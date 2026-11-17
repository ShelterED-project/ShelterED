import { Link } from 'react-router'
import type { ClassOut, ClassRollCall } from '@/features/teacher/teacherApi'
import { classes as t, navRoutes } from '../content'

type Props = { classes: ClassOut[]; rollCalls: ClassRollCall[]; className?: string }

export default function ClassesCard({ classes, rollCalls, className = '' }: Props) {
  const byClass = new Map(rollCalls.map((r) => [r.class_id, r.session]))
  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{t.title}</h2>
        <Link
          to={navRoutes.classes ?? '/admin'}
          className="rounded text-sm font-semibold whitespace-nowrap text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {t.all}
        </Link>
      </div>
      {classes.length === 0 ? (
        <p className="text-sm text-muted">{t.empty}</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full border-collapse text-left">
            <thead>
              <tr className="text-xs text-dim">
                <th scope="col" className="w-16 pb-2 font-semibold">Клас</th>
                <th scope="col" className="pb-2 font-semibold">Відмітились</th>
                <th scope="col" className="hidden w-44 pb-2 pl-3 font-semibold md:table-cell">Статус</th>
              </tr>
            </thead>
            <tbody>
              {classes.map((klass) => {
                const session = byClass.get(klass.id) ?? null
                const total = session ? session.summary.safe + session.summary.in_shelter + session.summary.no_response : 0
                const present = session ? session.summary.safe + session.summary.in_shelter : 0
                const missing = total - present
                return (
                  <tr key={klass.id} className="border-t border-line-soft">
                    <th scope="row" className="py-3 pr-3 text-base font-semibold whitespace-nowrap text-parchment">
                      {klass.name}
                    </th>
                    <td className="py-3.5">
                      {session ? (
                        <div className="flex items-center gap-3">
                          <div
                            role="progressbar"
                            aria-label={`Клас ${klass.name}`}
                            aria-valuemin={0}
                            aria-valuemax={total}
                            aria-valuenow={present}
                            className="h-2 min-w-20 flex-1 rounded-full bg-line-soft"
                          >
                            <div className="h-2 rounded-full bg-accent" style={{ width: `${total ? (present / total) * 100 : 0}%` }} />
                          </div>
                          <span className="text-sm whitespace-nowrap text-muted">
                            {present} / {total}
                          </span>
                        </div>
                      ) : (
                        <span className="text-sm text-dim">{t.noRollCall}</span>
                      )}
                    </td>
                    <td className={`hidden py-3.5 pl-3 text-sm whitespace-nowrap md:table-cell ${missing === 0 ? 'text-dim' : 'text-muted'}`}>
                      {!session ? '—' : missing === 0 ? t.allMarked : t.missing(missing)}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
