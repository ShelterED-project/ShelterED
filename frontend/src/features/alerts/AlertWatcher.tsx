import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router'
import { useActiveAlert } from './useActiveAlert'

const SEEN_KEY = 'shelter:seen-alerts'
export const SHELTER_PATH = '/shelter'

function readSeen(): string[] {
  try {
    const raw = sessionStorage.getItem(SEEN_KEY)
    return raw ? (JSON.parse(raw) as string[]) : []
  } catch {
    // sessionStorage недоступний (приватний режим): без памʼяті перенаправимо на кожне оновлення.
    return []
  }
}

function markSeen(id: string) {
  try {
    sessionStorage.setItem(SEEN_KEY, JSON.stringify([...readSeen(), id]))
  } catch {
    // Нічого страшного: найгірше, учня ще раз перекине в режим укриття.
  }
}

/**
 * Обгортка маршрутів учня: коли зʼявляється тривога, яку учень ще не бачив, один раз
 * відкриває режим укриття. Повторно не перекидає, щоб учень міг вийти на головну.
 */
export default function AlertWatcher() {
  const { alert } = useActiveAlert()
  const navigate = useNavigate()
  const { pathname } = useLocation()

  useEffect(() => {
    if (!alert || readSeen().includes(alert.id)) return
    markSeen(alert.id)
    if (pathname !== SHELTER_PATH) navigate(SHELTER_PATH)
  }, [alert, pathname, navigate])

  return <Outlet />
}
