import { useShelterLesson } from '@/features/lessons/useShelterLesson'
import { lesson as lessonTexts } from '@/pages/shelter/content'
import { lessonPage as texts } from '../content'

/** Назва уроку й рядок «час · Рюкзак»: у шапці на планшеті й десктопі, у тілі сторінки на телефоні. */
export function useLessonTitle() {
  const { hasPack, lesson } = useShelterLesson()
  if (!lesson) return { title: hasPack ? lessonTexts.noLesson : lessonTexts.noPack, subtitle: '' }
  // Назви предмета й імені вчителя в пакеті немає, тож показуємо час уроку.
  return { title: lesson.lesson.title, subtitle: `${lesson.startsAt}–${lesson.endsAt} · ${texts.backpack}` }
}
