import type { Alert } from '@/features/alerts/alertsApi'
import { alertMinutes } from './useSchoolOverview'

function cell(value: string | number | boolean | null | undefined): string {
  const text = value === null || value === undefined ? '' : String(value)
  // Формули Excel (=, +, -, @) не виконуємо: префікс «'» (CSV injection).
  const safe = /^[=+\-@]/.test(text) ? `'${text}` : text
  return /[",\n;]/.test(safe) ? `"${safe.replace(/"/g, '""')}"` : safe
}

/**
 * Журнал тривог у CSV для Excel: UTF-8 з BOM (інакше кирилиця ламається), час ISO 8601.
 * Файл формується на пристрої, на сервер нічого не йде.
 */
export function downloadAlertsCsv(alerts: Alert[], classNames: Map<string, string>, fileName: string) {
  const header = ['started_at', 'ended_at', 'duration_min', 'is_drill', 'source', 'class', 'location']
  const rows = alerts.map((a) => [
    a.started_at,
    a.ended_at,
    alertMinutes(a),
    a.is_drill,
    a.source,
    a.class_id ? (classNames.get(a.class_id) ?? a.class_id) : '',
    a.location_title,
  ])
  const csv = [header, ...rows].map((row) => row.map(cell).join(',')).join('\r\n')
  const url = URL.createObjectURL(new Blob(['﻿', csv], { type: 'text/csv;charset=utf-8' }))
  const link = document.createElement('a')
  link.href = url
  link.download = fileName
  link.click()
  URL.revokeObjectURL(url)
}
