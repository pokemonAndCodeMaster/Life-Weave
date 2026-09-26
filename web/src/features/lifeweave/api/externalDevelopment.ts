import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export interface ExternalActivity {
  id: string
  kind: 'external_development_start' | 'external_development_event' | 'external_development_binding' | 'external_development_hook'
  body: string
  createdAt: string
  payload: {
    sessionId: string
    phase: string
    source?: string
    nativeSessionId?: string | null
    agentId?: string | null
    methodId?: string | null
    observedGit?: {
      repositoryPath: string; revision: string; changedCount: number; untrackedCount: number
      changedPaths: string[]; untrackedPaths: string[]
    }
    declaredInputs?: Array<{ id: string; title: string; version: string; sourcePath: string }>
    reportedChecks?: string[]
    toolName?: string | null
    model?: string | null
    turnId?: string | null
    exitCode?: number | null
    inputHash?: string | null
  }
}

const root = (workspace: WorkspaceKind, itemId: string) =>
  `/lifeweave/${workspace}/items/${encodeURIComponent(itemId)}/external-development/sessions`

export async function listExternalSessions(workspace: WorkspaceKind, itemId: string): Promise<ExternalActivity[]> {
  return (await http.get<{ items: ExternalActivity[] }>(root(workspace, itemId))).data.items
}

export interface ExternalDiff { patch: string; fileCount: number; truncated: boolean; scope: string }
export async function getExternalDiff(workspace: WorkspaceKind, itemId: string, sessionId: string): Promise<ExternalDiff> {
  return (await http.get<ExternalDiff>(`${root(workspace, itemId)}/${encodeURIComponent(sessionId)}/diff`)).data
}
