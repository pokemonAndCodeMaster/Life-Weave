export function safeWorkLink(uri: string | null | undefined): string | null {
  if (!uri) return null
  try {
    const url = new URL(uri, window.location.origin)
    if (url.username || url.password) return null
    if (url.protocol === 'https:') return url.href
    if (url.origin === window.location.origin && (url.pathname.startsWith('/api/lifeweave/') || url.pathname.startsWith('/lifeweave/'))) return url.href
  } catch { /* Malformed or unsupported address. */ }
  return null
}
