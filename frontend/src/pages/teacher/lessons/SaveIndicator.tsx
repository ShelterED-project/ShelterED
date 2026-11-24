import { save } from './content'
import { useOverallSave } from './saveStatus'

/** Тихий загальний стан автозбереження в шапці редактора. */
export default function SaveIndicator() {
  const state = useOverallSave()
  if (state === 'idle') return null
  const text = state === 'saving' ? save.saving : state === 'failed' ? save.failed : save.saved
  const tone = state === 'failed' ? 'text-accent' : state === 'saved' ? 'text-safe' : 'text-dim'
  return (
    <p role="status" aria-live="polite" className={`text-sm font-semibold ${tone}`}>
      {text}
    </p>
  )
}
