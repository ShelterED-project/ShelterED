import iconChevron from '@/assets/parent/chevron-down.svg'
import iconPlus from '@/assets/admin/plus-16.svg'
import { users } from '../content'

export default function UsersCard({ className = '' }: { className?: string }) {
  return (
    <section className={`flex flex-col gap-3 rounded-[22px] border border-line bg-surface p-5 xl:p-6 ${className}`}>
      <div className="flex items-center justify-between gap-3">
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{users.title}</h2>
        <p className="text-right text-xs leading-4 text-dim">{users.summary}</p>
      </div>
      {/* TODO: відкривати профіль користувача, коли зʼявиться відповідна сторінка */}
      <ul className="pt-1">
        {users.items.map((user, i) => (
          <li key={user.name} className={`flex items-center gap-3 py-3 ${i > 0 ? 'border-t border-line-soft' : ''}`}>
            <span className="flex size-9 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-xs leading-4 font-semibold text-parchment">
              {user.initials}
            </span>
            <span className="min-w-0 flex-1">
              <span className="block truncate text-[15px] leading-[22.5px] font-medium text-parchment">{user.name}</span>
              <span className="block text-xs leading-4 text-dim">{user.role}</span>
            </span>
            <button
              type="button"
              aria-label={`Відкрити: ${user.name}`}
              className="flex size-9 shrink-0 items-center justify-center rounded-lg hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
            >
              <img src={iconChevron} alt="" width={16} height={16} />
            </button>
          </li>
        ))}
      </ul>
      {/* TODO: відкривати форму запрошення вчителя, коли зʼявиться відповідна сторінка */}
      <button
        type="button"
        className="flex items-center justify-center gap-2 rounded-[10px] border border-line-strong py-[10.5px] text-sm font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconPlus} alt="" width={16} height={16} />
        {users.invite}
      </button>
    </section>
  )
}
