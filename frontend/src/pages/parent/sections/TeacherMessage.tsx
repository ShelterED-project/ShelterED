import iconReply from '@/assets/parent/reply.svg'
import { teacherMessage } from '../content'

export default function TeacherMessage() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
        {teacherMessage.title}
      </h2>
      <div className="flex items-start gap-3">
        <div className="flex size-10 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs font-bold text-parchment">
          {teacherMessage.initials}
        </div>
        <div className="flex min-w-0 flex-col gap-[2.75px]">
          <p className="text-sm">
            <span className="font-semibold text-parchment">{teacherMessage.author} </span>
            <span className="text-dim">· {teacherMessage.time}</span>
          </p>
          <p className="text-sm leading-[22.75px] text-muted">{teacherMessage.text}</p>
        </div>
      </div>
      {/* TODO: відкривати чат із вчителем, коли зʼявиться розділ повідомлень */}
      <button
        type="button"
        className="flex items-center justify-center gap-2 rounded-[10px] border border-line-strong py-[10.5px] text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconReply} alt="" width={16} height={16} />
        {teacherMessage.reply}
      </button>
    </section>
  )
}
