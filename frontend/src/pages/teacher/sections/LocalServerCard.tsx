import iconServer from '@/assets/teacher/server-wifi.svg'
import iconRefresh from '@/assets/teacher/refresh.svg'
import { localServer } from '../content'

export default function LocalServerCard() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:flex-row md:items-center md:p-6">
      <div className="flex min-w-0 flex-1 items-center gap-4">
        <span className="flex size-12 shrink-0 items-center justify-center rounded-xl bg-surface-2">
          <img src={iconServer} alt="" width={24} height={24} />
        </span>
        <div className="min-w-0">
          <h2 className="text-[17px] leading-[25.5px] font-semibold text-parchment">{localServer.title}</h2>
          <p className="text-sm leading-5 text-muted">
            {localServer.textBefore}
            <span className="font-semibold text-parchment">{localServer.address}</span>
          </p>
        </div>
      </div>
      {/* TODO: запускати синхронізацію з хмарою, коли зʼявиться модуль sync */}
      <button
        type="button"
        className="flex h-12 shrink-0 items-center justify-center gap-3 rounded-[10px] border border-line-strong px-6 text-[15px] font-semibold whitespace-nowrap text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconRefresh} alt="" width={18} height={18} />
        {localServer.sync}
      </button>
    </section>
  )
}
