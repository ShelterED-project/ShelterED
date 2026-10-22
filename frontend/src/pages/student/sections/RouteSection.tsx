import iconCheck from '@/assets/landing/icon-check.svg'
import mole from '@/assets/landing/mole.svg'
import iconPin from '@/assets/student/pin-sm.svg'
import mapDesktop from '@/assets/student/route-map.svg'
import mapMobile from '@/assets/student/route-map-mobile.svg'
import { route } from '../content'
import type { RouteNodeId } from '../content'

// Позиції вузлів у відсотках від розмірів мапи (мобільна → від md)
const positions: Record<RouteNodeId, string> = {
  natural: 'left-[5.8%] top-[80.06%] md:left-[5.9%] md:top-[80.05%]',
  fractions: 'left-[22.18%] top-[54.54%] md:left-[22.09%] md:top-[54.43%]',
  decimals: 'left-[46.02%] top-[32.95%] md:left-[46.01%] md:top-[32.76%]',
  percent: 'left-[36.09%] top-[8.41%] md:left-[36.04%] md:top-[8.13%]',
}

const label = 'text-sm font-semibold whitespace-nowrap text-parchment'

function RouteNode({ node }: { node: (typeof route.nodes)[number] }) {
  const pos = `absolute ${positions[node.id]}`

  if (node.kind === 'done') {
    return (
      <li className={`${pos} flex items-center gap-2`}>
        <span className="flex size-10 shrink-0 items-center justify-center rounded-full bg-accent">
          <img src={iconCheck} alt="" width={16} height={16} />
        </span>
        <span className={label}>
          <span className="sr-only">Пройдено: </span>
          {node.label}
        </span>
      </li>
    )
  }

  if (node.kind === 'todo') {
    return (
      <li className={`${pos} flex items-center gap-2`}>
        <span className="size-10 shrink-0 rounded-full border-2 border-dashed border-muted bg-surface" />
        <span className="flex flex-col items-start gap-1 md:flex-row md:items-center md:gap-2">
          <span className={label}>{node.label}</span>
          <span className="rounded-md bg-parchment px-2 py-0.5 text-xs font-semibold whitespace-nowrap text-oil">
            {node.badge}
          </span>
        </span>
      </li>
    )
  }

  return (
    <li aria-current="step" className={`${pos} flex h-10 items-center gap-1`}>
      <span className="-ml-1 flex size-12 shrink-0 items-center justify-center rounded-full border-4 border-parchment bg-oil">
        <span className="size-10 rounded-full shadow-[0_0_24px_5px_rgba(242,178,92,0.35)]" />
      </span>
      <span className={label}>{node.label}</span>
    </li>
  )
}

export default function RouteSection({ className = '' }: { className?: string }) {
  return (
    <section className={`flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 xl:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{route.title}</h2>
        <p className="shrink-0 text-xs text-dim">{route.range}</p>
      </div>

      <div className="relative h-[324px] overflow-clip rounded-[18px] border border-line bg-oil/40 md:h-[364px] xl:h-[404px]">
        <img src={mapMobile} alt="" width={306} height={318} className="absolute inset-x-0 top-1 bottom-0 size-full md:hidden" />
        <img src={mapDesktop} alt="" width={644} height={398} className="absolute inset-x-0 top-1 bottom-0 hidden size-full md:block" />
        <ol>
          {route.nodes.map((node) => (
            <RouteNode key={node.id} node={node} />
          ))}
        </ol>
      </div>

      <div className="flex items-end gap-3 pt-1">
        <img
          src={mole}
          alt="Кріт — маскот ShelterED"
          width={80}
          height={80}
          className="size-20 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]"
        />
        <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[22px] leading-[1.15] font-semibold text-parchment">
          {route.moleSays}
        </p>
      </div>

      {/* TODO: підключити перехід до модуля й вправи для дихання, коли зʼявляться відповідні сторінки */}
      <div className="flex flex-wrap gap-2 md:pl-[92px]">
        <button
          type="button"
          className="h-11 rounded-[10px] bg-accent px-5 text-sm font-semibold text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none"
        >
          {route.go}
        </button>
        <button
          type="button"
          className="flex h-11 items-center justify-center gap-2 rounded-[10px] border border-line-strong px-5 text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          <img src={iconPin} alt="" width={16} height={16} />
          {route.breatheFirst}
        </button>
      </div>
    </section>
  )
}
