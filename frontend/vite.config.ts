import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Як у nginx.conf: префікс /api зрізається, бекенд слухає :8000.
const apiProxy = {
  '/api': {
    target: 'http://localhost:8000',
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
}

/** Колір тла застосунку (--color-oil): заставка при запуску й рядок стану на телефоні. */
const background = '#17120d'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // Service Worker: застосунок відкривається без мережі після першого завантаження.
    // Дані (уроки, події, перекличка) живуть в IndexedDB, SW кешує лише сам застосунок і медіа.
    VitePWA({
      // Нова версія не перезавантажує сторінку сама: учень може бути посеред уроку.
      // Показуємо запит «Оновити» (src/app/UpdatePrompt.tsx).
      registerType: 'prompt',
      injectRegister: false,
      includeAssets: ['favicon.svg', 'favicon.ico', 'apple-touch-icon-180x180.png'],
      manifest: {
        name: 'ShelterED',
        short_name: 'ShelterED',
        description: 'Уроки, тести й перекличка класу в укритті, навіть без інтернету',
        lang: 'uk',
        start_url: '/',
        scope: '/',
        display: 'standalone',
        background_color: background,
        theme_color: background,
        icons: [
          { src: 'pwa-64x64.png', sizes: '64x64', type: 'image/png' },
          { src: 'pwa-192x192.png', sizes: '192x192', type: 'image/png' },
          { src: 'pwa-512x512.png', sizes: '512x512', type: 'image/png' },
          { src: 'maskable-icon-512x512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      workbox: {
        // Застосунок цілком (HTML, JS, CSS, іконки) і шрифти лише кирилиці й латиниці у woff2:
        // решту підмножин (ієрогліфи, грецька тощо) браузер просить, тільки якщо трапиться такий
        // символ, а старі .woff цільовим браузерам не потрібні. Версія кешу змінюється з кожною
        // збіркою (хеш файлів).
        globPatterns: ['**/*.{js,css,html,svg,png,ico}', '**/*-{cyrillic,cyrillic-ext,latin,latin-ext}-[0-9]*.woff2'],
        cleanupOutdatedCaches: true,
        // Будь-яка сторінка без мережі відкривається з index.html, але не API й медіа.
        navigateFallback: 'index.html',
        navigateFallbackDenylist: [/^\/api\//, /^\/media\//],
        runtimeCaching: [
          {
            // Медіа уроків незмінні (новий вміст — новий URL), тож їх можна брати з кешу.
            // Кеш оновлюється разом з пакетами знань: новий пакет посилається на нові URL.
            urlPattern: ({ url, sameOrigin }) => sameOrigin && url.pathname.startsWith('/media/'),
            handler: 'CacheFirst',
            options: {
              cacheName: 'lesson-media',
              expiration: { maxEntries: 300, maxAgeSeconds: 30 * 24 * 60 * 60 },
              cacheableResponse: { statuses: [0, 200] },
              // Відео віддається частинами (Range): докачування після обриву мережі.
              rangeRequests: true,
            },
          },
        ],
      },
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: { proxy: apiProxy },
  // Перевірка офлайн-режиму: npm run build && npm run preview (SW працює лише у збірці).
  preview: { proxy: apiProxy },
})
