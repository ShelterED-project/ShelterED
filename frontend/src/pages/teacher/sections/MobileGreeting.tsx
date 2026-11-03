import { useCurrentUser } from '@/features/auth/useCurrentUser'
import { greeting } from '../content'

export default function MobileGreeting() {
  const user = useCurrentUser()
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{greeting.mobileSubtitle}</p>
      <h1 className="font-heading text-[28px] leading-[35px] text-parchment">{greeting.hello}, {user?.fullName}</h1>
    </div>
  )
}
