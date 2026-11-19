import { useLiveQuery } from 'dexie-react-hooks'
import { useAppSelector } from '@/app/hooks'
import { useLogout } from '@/features/auth/useLogout'
import { db } from '@/shared/db/db'
import { signOut as t } from '../content'
import { card, heading, outlineButton } from './styles'

/** Вихід з акаунта. Невідправлені записи не губляться: черга лишається на пристрої до наступного входу. */
export default function SignOutCard() {
  const logout = useLogout()
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  const pending = useLiveQuery(async () => (userId ? db.events.where('user_id').equals(userId).count() : 0), [userId], 0)

  return (
    <section className={card}>
      <h2 className={heading}>{t.title}</h2>
      <p className="text-sm text-muted">{t.text}</p>
      {pending > 0 && (
        <p role="status" className="text-sm text-accent">
          {t.pending(pending)}
        </p>
      )}
      <button type="button" onClick={() => void logout()} className={`${outlineButton} text-danger`}>
        {t.button}
      </button>
    </section>
  )
}
