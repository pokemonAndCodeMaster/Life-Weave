import type { WorkspaceKind } from '../types'
export function safeReadingReturn(value: unknown, workspace: WorkspaceKind): string | null {
  if (typeof value !== 'string' || !value.startsWith(`/lifeweave/${workspace}/items/`) || value.includes('\\')) return null
  const parsed = new URL(value, location.origin)
  return parsed.origin === location.origin && new RegExp(`^/lifeweave/${workspace}/items/[^/]+/(overview|outputs|context|activity|retro|development)$`).test(parsed.pathname) ? value : null
}
