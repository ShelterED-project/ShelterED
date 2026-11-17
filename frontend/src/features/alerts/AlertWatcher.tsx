import { useEffect } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router'
import { useActiveAlert } from './useActiveAlert'

const SEEN_KEY = 'shelter:seen-alerts'
export const SHELTER_PATH = '/shelter'
const LESSON_PATH = '/student/lesson'

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
  const { pathname, search } = useLocation()

  useEffect(() => {
    if (!alert || readSeen().includes(alert.id)) return
    markSeen(alert.id)
    // Учень посеред уроку: в режимі укриття відкриваємо той самий урок (?lesson=).
    const lesson = pathname === LESSON_PATH ? new URLSearchParams(search).get('lesson') : null
    if (pathname !== SHELTER_PATH) navigate(lesson ? `${SHELTER_PATH}?lesson=${lesson}` : SHELTER_PATH)
  }, [alert, pathname, search, navigate])

  return <Outlet />
}
