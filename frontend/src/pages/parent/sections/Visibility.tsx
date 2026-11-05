import iconCheck from '@/assets/parent/check.svg'
import iconCross from '@/assets/parent/cross.svg'
import { visibility } from '../content'

export default function Visibility() {
  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <h2 className="font-heading text-xl leading-7 tracking-[-0.2px] text-parchment md:text-[22px] md:tracking-[-0.22px]">
        {visibility.title}
      </h2>
      <ul className="flex flex-col gap-[9.5px]">
        {visibility.items.map((item) => (
          <li key={item.text} className="flex items-center gap-3 text-sm leading-5 text-parchment">
            <img src={item.visible ? iconCheck : iconCross} alt={item.visible ? 'Бачите' : 'Не бачите'} width={16} height={16} />
            {item.text}
          </li>
        ))}
      </ul>
    </section>
  )
}
