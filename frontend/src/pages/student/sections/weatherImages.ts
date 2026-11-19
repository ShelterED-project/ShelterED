import cloud from '@/assets/student/weather-cloud.svg'
import rain from '@/assets/student/weather-rain.svg'
import storm from '@/assets/student/weather-storm.svg'
import sunCloud from '@/assets/student/weather-sun-cloud.svg'
import sun from '@/assets/student/weather-sun.svg'
import type { WeatherPicture } from '@/features/wellbeing/wellbeingApi'

/** Картинки погоди для «Як ти зараз?»: малюнки з макета замість емодзі (однакові на всіх телефонах). */
export const weatherImage: Record<WeatherPicture, string> = {
  storm,
  rain,
  cloud,
  sun_cloud: sunCloud,
  sun,
}
