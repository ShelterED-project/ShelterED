import { useCurrentUser } from '@/features/auth/useCurrentUser'
import { useTeacherRollCall } from '@/features/teacher/useTeacherRollCall'
import { greeting, greetingSubtitle } from '../content'

export default function MobileGreeting() {
  const user = useCurrentUser()
  const { teacherClass } = useTeacherRollCall()
  return (
    <div className="md:hidden">
      <p className="text-sm text-dim">{greetingSubtitle(teacherClass?.name)}</p>
      <h1 className="font-heading text-[28px] leading-[35px] text-parchment">{greeting.hello}, {user?.fullName}</h1>
    </div>
  )
}
