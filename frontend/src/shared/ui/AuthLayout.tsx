import type { ReactNode } from 'react'
import asideBgDesktop from '@/assets/auth/aside-bg-desktop.svg'
import asideBgMobile from '@/assets/auth/aside-bg-mobile.svg'
import mole from '@/assets/landing/mole.svg'
import Brand from './Brand'

type Props = {
  bubble: string
  children: ReactNode
}

export default function AuthLayout({ bubble, children }: Props) {
  return (
    <div className="flex min-h-screen flex-col bg-oil font-sans text-parchment lg:flex-row">
      <aside className="relative overflow-hidden border-b border-line bg-surface lg:flex-1 lg:border-r lg:border-b-0">
        <img src={asideBgMobile} alt="" className="absolute inset-0 size-full max-w-none lg:hidden" />
        <img src={asideBgDesktop} alt="" className="absolute inset-0 hidden size-full max-w-none lg:block" />
        <div className="relative flex flex-col px-5 py-6 md:px-8 lg:min-h-screen lg:justify-between lg:px-16 lg:py-12">
          <Brand size="header" />
          <div className="flex items-center gap-4 pt-6 lg:flex-col lg:items-start lg:gap-6 lg:pt-0">
            <img
              src={mole}
              alt="Кріт — маскот ShelterED"
              width={224}
              height={224}
              className="size-24 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)] lg:size-56"
            />
            <p className="rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[19px] leading-tight font-semibold text-parchment lg:max-w-[420px] lg:px-6 lg:py-4 lg:text-[30px] lg:leading-tight">
              {bubble}
            </p>
          </div>
          <p className="hidden max-w-[420px] text-sm leading-5 text-dim lg:block">
            Офлайн-вхід працює на пристроях, де ви вже входили з інтернетом.
          </p>
        </div>
      </aside>

      <main className="flex flex-1 items-center justify-center px-5 py-8 md:px-8 lg:p-16">
        <div className="w-full max-w-[460px]">{children}</div>
      </main>
    </div>
  )
}
