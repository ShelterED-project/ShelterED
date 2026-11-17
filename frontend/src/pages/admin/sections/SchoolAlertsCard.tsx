import { useState } from 'react'
import type { SubmitEvent } from 'react'
import { useAlertLocationsQuery, useSaveAlertLocationsMutation } from '@/features/admin/adminApi'
import type { AlertLocations } from '@/features/admin/adminApi'
import { getErrorMessage } from '@/features/auth/errors'
import { schoolSettings } from '../content'

const t = schoolSettings.alerts

/** Повний список локацій alerts.in.ua (посилання з документації їхнього API). */
const LOCATIONS_URL = 'https://docs.google.com/spreadsheets/d/1XnTOzcPHd1LZUrarR1Fk43FUyl8Ae6a6M7pcwDRjNdA'

const UID = /^[0-9]{1,9}$/

type Field = keyof AlertLocations
const fields: { key: Field; label: string }[] = [
  { key: 'alert_raion_uid', label: t.raion },
  { key: 'alert_hromada_uid', label: t.hromada },
  { key: 'alert_city_uid', label: t.city },
]

type Draft = Record<Field, string>

function toDraft(locations: AlertLocations): Draft {
  return {
    alert_raion_uid: locations.alert_raion_uid ?? '',
    alert_hromada_uid: locations.alert_hromada_uid ?? '',
    alert_city_uid: locations.alert_city_uid ?? '',
  }
}

function LocationsForm({ schoolId, initial }: { schoolId: string; initial: Draft }) {
  const [draft, setDraft] = useState(initial)
  const [saved, setSaved] = useState(false)
  const [save, { isLoading, error }] = useSaveAlertLocationsMutation()

  const invalid = fields.filter(({ key }) => draft[key].trim() !== '' && !UID.test(draft[key].trim())).map((f) => f.key)

  async function onSubmit(e: SubmitEvent<HTMLFormElement>) {
    e.preventDefault()
    if (invalid.length > 0) return
    setSaved(false)
    const value = (key: Field) => draft[key].trim() || null
    try {
      await save({
        schoolId,
        alert_raion_uid: value('alert_raion_uid'),
        alert_hromada_uid: value('alert_hromada_uid'),
        alert_city_uid: value('alert_city_uid'),
      }).unwrap()
      setSaved(true)
    } catch {
      // Текст помилки береться зі стану мутації нижче.
    }
  }

  return (
    <form onSubmit={onSubmit} noValidate className="flex flex-col gap-4">
      <div className="grid gap-3 sm:grid-cols-3">
        {fields.map(({ key, label }) => {
          const bad = invalid.includes(key)
          return (
            <label key={key} className="flex flex-col gap-1 text-sm font-semibold text-parchment">
              {label}
              <input
                value={draft[key]}
                onChange={(e) => {
                  setSaved(false)
                  setDraft((d) => ({ ...d, [key]: e.target.value }))
                }}
                inputMode="numeric"
                maxLength={9}
                autoComplete="off"
                aria-invalid={bad || undefined}
                className={`h-12 rounded-[10px] border bg-oil px-4 text-base font-normal text-parchment outline-none focus:border-accent focus-visible:ring-2 focus-visible:ring-accent/40 ${bad ? 'border-danger' : 'border-line'}`}
              />
              {bad && <span className="text-xs font-normal text-danger">{t.invalid}</span>}
            </label>
          )
        })}
      </div>
      <p className="text-xs text-dim">
        {t.hint}{' '}
        <a href={LOCATIONS_URL} target="_blank" rel="noreferrer" className="text-accent underline underline-offset-2">
          {t.listLink}
        </a>
      </p>
      <div className="flex flex-wrap items-center gap-3">
        <button
          type="submit"
          disabled={isLoading || invalid.length > 0}
          className="flex h-12 items-center justify-center rounded-[10px] bg-accent px-6 font-bold text-oil focus-visible:ring-2 focus-visible:ring-parchment focus-visible:outline-none disabled:opacity-60"
        >
          {isLoading ? t.saving : t.save}
        </button>
        {saved && (
          <p role="status" className="text-sm text-safe">
            {t.saved}
          </p>
        )}
        {error && (
          <p role="alert" className="text-sm text-danger">
            {getErrorMessage(error)}
          </p>
        )}
      </div>
    </form>
  )
}

/** Де шукати тривоги для школи: крім області, район, громада й місто зі словника alerts.in.ua. */
export default function SchoolAlertsCard({ schoolId }: { schoolId: string }) {
  const query = useAlertLocationsQuery(schoolId)

  return (
    <section className="flex flex-col gap-4 rounded-[22px] border border-line bg-surface p-5 md:p-6">
      <div>
        <h2 className="font-heading text-xl leading-7 text-parchment xl:text-[22px]">{t.title}</h2>
        <p className="mt-1 text-sm text-muted">{t.text}</p>
        {query.data && <p className="mt-1 text-sm text-dim">{t.region(query.data.region_code)}</p>}
      </div>
      {query.isError && !query.data && (
        <p role="status" className="text-sm text-muted">
          {t.offline}
        </p>
      )}
      {query.data && <LocationsForm schoolId={schoolId} initial={toDraft(query.data)} />}
    </section>
  )
}
