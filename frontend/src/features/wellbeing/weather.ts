import type { WeatherPicture } from './wellbeingApi'

/** Картинки погоди: емодзі є на всіх цільових телефонах і не потребують завантаження. */
export const weatherIcon: Record<WeatherPicture, string> = {
  storm: '⛈️',
  rain: '🌧️',
  cloud: '☁️',
  sun_cloud: '⛅',
  sun: '☀️',
}
