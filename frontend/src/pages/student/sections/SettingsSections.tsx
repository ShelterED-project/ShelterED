import { useState } from 'react'
import { useLiveQuery } from 'dexie-react-hooks'
import mole from '@/assets/landing/mole.svg'
import iconLogout from '@/assets/student/settings-logout.svg'
import { useAppSelector } from '@/app/hooks'
import { useCurrentUser } from '@/features/auth/useCurrentUser'
import { useLogout } from '@/features/auth/useLogout'
import { requestPackSync } from '@/features/packs/syncPacks'
import { useDeviceStorage } from '@/features/settings/useDeviceStorage'
import { requestSync } from '@/features/sync/syncOutbox'
import { useConnection } from '@/features/sync/useConnection'
import { bytesLabel } from '@/pages/settings/content'
import { Row, Section, smallButton, Status } from '@/pages/settings/sections/rows'
import { db } from '@/shared/db/db'
import { useOutboxCount } from '@/shared/db/useOutboxCount'
import { dateTimeLabel } from '@/shared/lib/date'
import Spinner from '@/shared/ui/Spinner'
import { studentSettings as t } from '../content'

export function ProfileSection() {
  const user = useCurrentUser()
  if (!user) return null
  return (
    <Section title={t.profile.title}>
      <li className="flex flex-col gap-3 py-4">
        <div className="flex items-center gap-4">
          <span className="flex size-12 shrink-0 items-center justify-center rounded-full border border-line bg-surface-2 text-base font-bold text-parchment">
            {user.initials}
          </span>
          <div className="min-w-0">
            <p className="truncate text-[15px] leading-[22.5px] font-semibold text-parchment">{user.fullName}</p>
            <p className="text-xs leading-[16.5px] text-dim">{t.profile.role}</p>
          </div>
        </div>
        <p className="text-xs leading-[16.5px] text-dim">{t.pinNote}</p>
      </li>
    </Section>
  )
}

/** Без звуку й із субтитрами — так влаштований увесь застосунок, тож це не перемикачі, а факти. */
export function QuietSection() {
  return (
    <Section title={t.quiet.title}>
      <Row title={t.quiet.sound} note={t.quiet.soundNote}>
        <Status ok>{t.quiet.always}</Status>
      </Row>
      <Row title={t.quiet.subtitles} note={t.quiet.subtitlesNote}>
        <Status ok>{t.quiet.always}</Status>
      </Row>
    </Section>
  )
}

export function OfflineSection() {
  const { packDays, appOffline } = useConnection()
  const loginSaved = useAppSelector((s) => s.auth.persisted)
  const storage = useDeviceStorage()
  const [denied, setDenied] = useState(false)

  return (
    <Section title={t.offline.title}>
      <Row
        title={t.offline.packs}
        note={packDays.length > 0 ? t.offline.packsDays(packDays.length) : t.offline.packsNone}
      >
        <Status ok={packDays.length > 0}>{packDays.length > 0 ? t.offline.ready : t.offline.notYet}</Status>
      </Row>
      <Row title={t.offline.login} note={loginSaved ? t.offline.loginOn : t.offline.loginOff}>
        <Status ok={loginSaved}>{loginSaved ? t.offline.ready : t.offline.notYet}</Status>
      </Row>
      <Row title={t.offline.app} note={appOffline ? t.offline.appOn : t.offline.appOff}>
        <Status ok={appOffline}>{appOffline ? t.offline.ready : t.offline.notYet}</Status>
      </Row>
      {storage.canPersist && (
        <Row
          title={t.offline.persist}
          note={
            denied && !storage.persisted
              ? t.offline.persistDenied
              : storage.persisted
                ? t.offline.persistOn
                : t.offline.persistOff
          }
        >
          {storage.persisted ? (
            <Status ok>{t.offline.ready}</Status>
          ) : (
            <button
              type="button"
              onClick={() => void storage.requestPersist().then((ok) => setDenied(!ok))}
              className={smallButton}
            >
              {t.offline.persistButton}
            </button>
          )}
        </Row>
      )}
    </Section>
  )
}

export function SyncSection() {
  const { online, lastOkAt } = useConnection()
  const pending = useOutboxCount()
  const [busy, setBusy] = useState(false)

  async function sync() {
    setBusy(true)
    try {
      await Promise.allSettled([requestSync(), requestPackSync()])
    } finally {
      setBusy(false)
    }
  }

  return (
    <Section title={t.sync.title}>
      <Row title={t.sync.internet} note={online ? t.sync.online : t.sync.offline}>
        <button
          type="button"
          onClick={() => void sync()}
          disabled={busy || !online}
          aria-busy={busy}
          className={smallButton}
        >
          {busy && <Spinner />}
          {busy ? t.sync.busy : t.sync.button}
        </button>
      </Row>
      <Row title={t.sync.last} note={lastOkAt ? dateTimeLabel(lastOkAt) : t.sync.never} />
      <Row title={t.sync.queue} note={t.sync.queueValue(pending)}>
        <Status ok={pending === 0}>{pending === 0 ? t.offline.ready : pending}</Status>
      </Row>
    </Section>
  )
}

export function DeviceSection() {
  const storage = useDeviceStorage()
  const deviceId = useLiveQuery(async () => (await db.meta.get('device_id'))?.value as string | undefined, [])
  // Застосунок, встановлений на головний екран, відкривається без рядка адреси.
  const [installed] = useState(() => window.matchMedia('(display-mode: standalone)').matches)
  const note = [
    deviceId ? t.device.id(`${deviceId.slice(0, 4)}…${deviceId.slice(-3)}`) : null,
    storage.usage !== null ? t.device.used(bytesLabel(storage.usage)) : null,
  ]
    .filter(Boolean)
    .join(' · ')

  return (
    <Section title={t.device.title}>
      <Row title={t.device.title} note={note || undefined}>
        <span className="shrink-0 text-xs leading-4 text-dim">{installed ? t.device.installed : t.device.browser}</span>
      </Row>
    </Section>
  )
}

export function MoleNote() {
  return (
    <div className="flex items-end gap-3">
      <img
        src={mole}
        alt=""
        width={64}
        height={64}
        className="size-16 shrink-0 drop-shadow-[0_0_7px_rgba(242,178,92,0.35)]"
      />
      <p className="flex-1 rounded-[18px] rounded-bl-[4px] border border-line bg-surface-2 px-4 py-3 font-mole text-[22px] leading-[27.5px] text-parchment">
        {t.mole}
      </p>
    </div>
  )
}

/** Вихід: невідправлені записи лишаються на пристрої до наступного входу. */
export function SignOut() {
  const logout = useLogout()
  const userId = useAppSelector((s) => s.auth.session?.user.id)
  const pending = useLiveQuery(
    async () => (userId ? db.events.where('user_id').equals(userId).count() : 0),
    [userId],
    0,
  )

  return (
    <div className="flex flex-col gap-3">
      {pending > 0 && (
        <p role="status" className="text-sm text-accent">
          {t.signOutPending(pending)}
        </p>
      )}
      <button
        type="button"
        onClick={() => void logout()}
        className="flex h-14 w-full items-center justify-center gap-2 rounded-[10px] border border-line-strong px-5 text-[15px] leading-[22.5px] font-semibold text-parchment hover:bg-surface-2 focus-visible:ring-2 focus-visible:ring-accent/40 focus-visible:outline-none"
      >
        <img src={iconLogout} alt="" width={16} height={16} />
        {t.signOut}
      </button>
    </div>
  )
}
