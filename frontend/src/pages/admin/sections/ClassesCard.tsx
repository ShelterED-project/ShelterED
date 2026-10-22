import { classes } from '../content'

export default function ClassesCard({ className = '' }: { className?: string }) {
  return (
    <section className={`flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{classes.title}</h2>
        {/* TODO: відкривати список усіх класів, коли зʼявиться відповідна сторінка */}
        <button
          type="button"
          className="rounded text-sm font-semibold whitespace-nowrap text-muted hover:text-parchment focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {classes.all}
        </button>
      </div>
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
            {classes.rows.map((row) => {
              const missing = row.total - row.present
              return (
                <tr key={row.name} className="border-t border-line-soft">
                  <th scope="row" className="py-3 pr-3 text-base font-semibold whitespace-nowrap text-parchment">
                    {row.name}
                  </th>
                  <td className="py-3.5">
                    <div className="flex items-center gap-3">
                      <div
                        role="progressbar"
                        aria-label={`Клас ${row.name}`}
                        aria-valuemin={0}
                        aria-valuemax={row.total}
                        aria-valuenow={row.present}
                        className="h-2 min-w-20 flex-1 rounded-full bg-line-soft"
                      >
                        <div className="h-2 rounded-full bg-accent" style={{ width: `${(row.present / row.total) * 100}%` }} />
                      </div>
                      <span className="text-sm whitespace-nowrap text-muted">
                        {row.present} / {row.total}
                      </span>
                    </div>
                  </td>
                  <td className={`hidden py-3.5 pl-3 text-sm whitespace-nowrap md:table-cell ${missing === 0 ? 'text-dim' : 'text-muted'}`}>
                    {missing === 0 ? 'усі відмітились' : `${missing} не відмітились`}
                  </td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </section>
  )
}
