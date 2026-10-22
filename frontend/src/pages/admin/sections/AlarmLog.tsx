import { alarms } from '../content'

export default function AlarmLog() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 xl:p-6">
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{alarms.title}</h2>
        {/* TODO: експортувати журнал у CSV, коли зʼявиться API */}
        <button
          type="button"
          className="h-10 shrink-0 rounded-[10px] border border-line-strong px-4 text-sm font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {alarms.export}
        </button>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="text-xs text-dim">
              <th scope="col" className="pb-2 font-semibold">Дата</th>
              <th scope="col" className="pb-2 font-semibold">Початок</th>
              <th scope="col" className="hidden pb-2 font-semibold md:table-cell">Відбій</th>
              <th scope="col" className="pb-2 font-semibold">Тривалість</th>
              <th scope="col" className="hidden pb-2 font-semibold md:table-cell">Зачепило</th>
            </tr>
          </thead>
          <tbody>
            {alarms.rows.map((row) => (
              <tr key={`${row.date}-${row.start}`} className="border-t border-line-soft text-sm leading-5">
                <td className="py-3 pr-3 whitespace-nowrap text-parchment">{row.date}</td>
                <td className="py-3 pr-3 whitespace-nowrap text-parchment">{row.start}</td>
                <td className="hidden py-3 pr-3 whitespace-nowrap text-parchment md:table-cell">{row.end}</td>
                <td className={`py-3 pr-3 font-semibold whitespace-nowrap ${row.ongoing ? 'text-accent' : 'text-parchment'}`}>
                  {row.duration}
                </td>
                <td className="hidden py-3 whitespace-nowrap text-dim md:table-cell">{row.affected}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  )
}
