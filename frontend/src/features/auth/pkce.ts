/** client_id PWA, дозволений на бекенді (settings.oauth_client_ids). */
export const OAUTH_CLIENT_ID = 'sheltered-pwa'

function base64Url(bytes: Uint8Array): string {
  let binary = ''
  for (const b of bytes) binary += String.fromCharCode(b)
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** 32 випадкові байти → 43 символи base64url (мінімум за RFC 7636). */
export function createCodeVerifier(): string {
  return base64Url(crypto.getRandomValues(new Uint8Array(32)))
}

/**
 * S256-challenge. crypto.subtle доступний лише в безпечному контексті (HTTPS або localhost),
 * тому вхід дорослих на http://192.168.x.x без HTTPS не спрацює.
 */
export async function createCodeChallenge(verifier: string): Promise<string> {
  if (!crypto.subtle) {
    throw new Error('PKCE потребує безпечного контексту (HTTPS)')
  }
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(verifier))
  return base64Url(new Uint8Array(digest))
}
