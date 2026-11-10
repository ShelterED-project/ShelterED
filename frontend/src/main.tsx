import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { Provider } from 'react-redux'
import './index.css'
import App from './app/App'
import { store } from './app/store'
import { restoreSession } from './features/auth/session'
import { startPackSync } from './features/packs/syncPacks'
import { startSync } from './features/sync/syncOutbox'

// Збережений вхід піднімаємо з IndexedDB до першого рендеру, щоб застосунок відкривався без мережі.
void restoreSession(store.dispatch).then(() => {
  startSync()
  startPackSync()
  createRoot(document.getElementById('root')!).render(
    <StrictMode>
      <Provider store={store}>
        <App />
      </Provider>
    </StrictMode>,
  )
})
