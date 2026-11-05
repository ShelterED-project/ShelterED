import iconLantern from '@/assets/student/banner-lantern.svg'
import { lessonBanner } from '../content'

export default function LessonBanner() {
  return (
    <section
      aria-labelledby="lesson-title"
      className="flex flex-col gap-4 overflow-clip rounded-[22px] border border-accent/40 bg-surface-2 p-5 md:flex-row md:items-center md:gap-6 xl:p-6"
    >
      <div className="relative flex size-14 shrink-0 items-center justify-center rounded-full bg-accent-soft">
        <span className="absolute inset-0 rounded-full shadow-[0_0_44px_10px_rgba(242,178,92,0.3)]" />
        <img src={iconLantern} alt="" width={28} height={28} className="relative" />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-1 pt-[5.5px] md:pt-0">
        <p className="text-xs font-semibold tracking-[1.5px] text-accent uppercase">{lessonBanner.eyebrow}</p>
        <h2
          id="lesson-title"
          className="pt-[2.5px] font-heading text-2xl leading-[30px] text-parchment xl:pt-[1.5px] xl:text-[26px] xl:leading-[32.5px]"
        >
          {lessonBanner.title}
        </h2>
        <p className="text-sm leading-5 text-muted">{lessonBanner.text}</p>
      </div>
      {/* TODO: підключити перехід до уроку й вправи для дихання, коли зʼявляться відповідні сторінки */}
      <div className="flex gap-2 md:shrink-0">
        <button
          type="button"
          className="h-12 flex-1 rounded-[10px] bg-accent px-6 text-[15px] font-semibold whitespace-nowrap text-oil focus-visible:ring-2 focus-visible:ring-parchment/60 focus-visible:outline-none md:flex-none"
        >
          {lessonBanner.open}
        </button>
        <button
          type="button"
          className="h-12 shrink-0 rounded-[10px] border border-line-strong px-5 text-[15px] font-semibold whitespace-nowrap text-parchment hover:bg-surface focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
        >
          {lessonBanner.breathe}
        </button>
      </div>
    </section>
  )
}
