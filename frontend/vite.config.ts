import tailwindcss from '@tailwindcss/vite'
import react from '@vitejs/plugin-react'
import { createReadStream, statSync } from 'node:fs'
import type { IncomingMessage, ServerResponse } from 'node:http'
import { extname, resolve, sep } from 'node:path'
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import type { Plugin } from 'vite'
import { VitePWA } from 'vite-plugin-pwa'

// Як у nginx.conf: префікс /api зрізається, бекенд слухає :8000.
const apiProxy = {
  '/api': {
    target: 'http://localhost:8000',
    rewrite: (path: string) => path.replace(/^\/api/, ''),
  },
}

/**
 * Медіа уроків (/media/...) у розробці й preview: файли з каталогу медіа бекенду
 * (backend/media, MEDIA_ROOT у бекенді), як їх роздаватиме Nginx. З підтримкою Range,
 * щоб відео перемотувалось. Лише для локальної перевірки, у збірку не потрапляє.
 */
const mediaRoot = resolve(process.env.MEDIA_ROOT ?? fileURLToPath(new URL('../backend/media', import.meta.url)))
const mediaTypes: Record<string, string> = {
  '.mp4': 'video/mp4',
  '.webm': 'video/webm',
  '.webp': 'image/webp',
  '.png': 'image/png',
  '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg',
  '.vtt': 'text/vtt; charset=utf-8',
}

function serveMedia(req: IncomingMessage, res: ServerResponse, next: () => void) {
  const pathname = decodeURIComponent(new URL(req.url ?? '/', 'http://localhost').pathname)
  if (!pathname.startsWith('/media/')) return next()
  const file = resolve(mediaRoot, `.${pathname.slice('/media'.length)}`)
  let size: number
  try {
    if (!file.startsWith(mediaRoot + sep)) throw new Error('outside')
    const stat = statSync(file)
    if (!stat.isFile()) throw new Error('not a file')
    size = stat.size
  } catch {
    res.statusCode = 404
    res.end()
    return
  }
  res.setHeader('Content-Type', mediaTypes[extname(file).toLowerCase()] ?? 'application/octet-stream')
  res.setHeader('Accept-Ranges', 'bytes')
  const range = /^bytes=(\d*)-(\d*)$/.exec(req.headers.range ?? '')
  if (range && (range[1] || range[2])) {
    const start = range[1] ? Number(range[1]) : Math.max(0, size - Number(range[2]))
    const end = range[1] && range[2] ? Math.min(Number(range[2]), size - 1) : size - 1
    if (start > end || start >= size) {
      res.statusCode = 416
      res.setHeader('Content-Range', `bytes */${size}`)
      res.end()
      return
    }
    res.statusCode = 206
    res.setHeader('Content-Range', `bytes ${start}-${end}/${size}`)
    res.setHeader('Content-Length', end - start + 1)
    createReadStream(file, { start, end }).pipe(res)
    return
  }
  res.setHeader('Content-Length', size)
  createReadStream(file).pipe(res)
}

const devMedia: Plugin = {
  name: 'shelter-dev-media',
  configureServer: (server) => void server.middlewares.use(serveMedia),
  configurePreviewServer: (server) => void server.middlewares.use(serveMedia),
}

/** Колір тла застосунку (--color-oil): заставка при запуску й рядок стану на телефоні. */
const background = '#17120d'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    devMedia,
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
        // Важкі бібліотеки редактора вчителя (стискання відео, імпорт PDF) не кешуємо наперед:
        // учням вони не потрібні, а вчитель працює з редактором онлайн.
        globIgnores: ['**/editor-lib-*.js'],
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
              // Відео браузер просить частинами (Range). RangeRequestsPlugin вирізає потрібну частину
              // з повного файла в кеші, тож відео грає й перемотується без мережі. Повні файли кладе
              // в цей кеш наперед src/features/packs/mediaCache.ts (назва кешу там та сама);
              // відповіді 206 з мережі не кешуються (statuses нижче), щоб не зберегти уривок.
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
  build: {
    rolldownOptions: {
      output: {
        chunkFileNames: (chunk) =>
          chunk.moduleIds.some((id) => /node_modules[/\\](mediabunny|pdfjs-dist)[/\\]/.test(id))
            ? 'assets/editor-lib-[name]-[hash].js'
            : 'assets/[name]-[hash].js',
      },
    },
  },
  server: { proxy: apiProxy },
  // Перевірка офлайн-режиму: npm run build && npm run preview (SW працює лише у збірці).
  preview: { proxy: apiProxy },
})
