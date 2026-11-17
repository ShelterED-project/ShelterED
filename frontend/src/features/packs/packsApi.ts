import { baseApi } from '@/shared/api/baseApi'
import type { Pack, PackManifest } from '@/shared/db/packTypes'

export const packsApi = baseApi.injectEndpoints({
  endpoints: (build) => ({
    packManifest: build.query<PackManifest, string>({
      query: (classId) => `/packs/manifest?class_id=${classId}`,
    }),
    // ETag і стиснення (br/gzip) обробляє браузер, пакет приходить уже розпакованим.
    pack: build.query<Pack, string>({
      query: (packId) => `/packs/${packId}`,
    }),
  }),
})

export const { usePackManifestQuery } = packsApi
