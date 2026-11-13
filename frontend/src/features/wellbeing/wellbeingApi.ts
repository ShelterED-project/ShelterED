import { baseApi } from '@/shared/api/baseApi'

// «Як ти зараз?» (docs/wellbeing-checkin.md). Усі тексти — з сервера (backend/app/services/
// wellbeing_texts.py), щоб фахівець правив їх в одному місці. Це не тест і не діагноз.

export type WeatherPicture = 'storm' | 'rain' | 'cloud' | 'sun_cloud' | 'sun'
export type WellbeingValue = 1 | 2 | 3 | 4 | 5

export interface Hotline {
  name: string
  phone: string
  note: string
}

export interface WellbeingChildTexts {
  question: string
  hint: string
  skip: string
  scale: { value: WellbeingValue; picture: WeatherPicture; label: string }[]
  reply: string
  reply_low_extra: {
    text: string
    breathing: { title: string; steps: string[]; start: string; later: string }
    trusted_adult: string
  }
  support: { title: string; text: string; hotlines: Hotline[] }
  history_title: string
}

export interface WellbeingTexts {
  /** Змінюється разом з будь-яким текстом */
  version: string
  child: WellbeingChildTexts
  disclaimer: string
}

/** Свої картинки учня за 14 днів (бачить лише сам учень і в такому вигляді) */
export interface WellbeingSelf {
  view: 'self'
  student_id: string
  days: { date: string; picture: WeatherPicture }[]
  /** Кілька непростих днів поспіль: м'яко показати блок «Якщо хочеш поговорити» */
  show_support: boolean
}

export const wellbeingApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    wellbeingTexts: build.query<WellbeingTexts, void>({
      query: () => '/wellbeing/texts',
    }),
    wellbeingSelf: build.query<WellbeingSelf, string>({
      query: (studentId) => `/students/${studentId}/wellbeing`,
    }),
  }),
})

export const { useWellbeingTextsQuery, useWellbeingSelfQuery } = wellbeingApi
