import { useCurrentUser } from '@/features/auth/useCurrentUser'
import { greeting } from '../content'

export default function MobileGreeting() {
  const user = useCurrentUser()
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{greeting.date}</p>
      <h1 className="font-heading text-[28px] leading-[35px] text-parchment">{greeting.hello}, {user?.display_name}!</h1>
    </div>
  )
}
