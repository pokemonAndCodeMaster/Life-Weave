import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export interface DevelopmentAssignment {
  id: string; itemId: string; instruction: string; agentId: string; agentVersion: string
  engine: string; model: string | null; repositoryPath: string; repositoryRevision: string
  workingTreeExcluded: boolean; contextVersionId: string; methodId: string | null
  knowledgeRefs: string[]; inputVersions: Array<{ id: string; version: string; sourcePath: string }>
  reviewMode: 'independent' | 'self'; reviewDecision: string | null
  status: 'planning' | 'reviewing' | 'implementing' | 'awaiting_acceptance' | 'blocked' | 'failed' | 'cancelled'
  planRunId: string | null; reviewRunId: string | null; implementationRunId: string | null
  plan: string | null; planSha256: string | null; review: string | null; error: string | null
  createdAt: string; updatedAt: string
}
export interface DevelopmentChoices {
  itemId: string; recommendedAgentId: string; recommendedRepositoryPath: string; methodId: string | null; knowledgeRefs: string[]
  agents: Array<{ id: string; title: string; version: string; available: boolean; reason: string }>
  executors: Record<'codex' | 'opencode', { available: boolean; version?: string; reason?: string; verifiedModel?: string | null; lastSucceededAt?: string | null }>
}
export interface DevelopmentInput {
  requestId: string; itemId: string; instruction: string; repositoryPath: string
  agentId: 'development'; engine: 'codex' | 'opencode'; model?: string | null; methodId?: string | null
  knowledgeRefs?: string[]; reviewMode: 'independent' | 'self'; acknowledgeExcludedChanges: boolean
}
const root = (workspace: WorkspaceKind) => `/lifeweave/${workspace}`
export async function developmentChoices(workspace: WorkspaceKind, itemId: string) {
  return (await http.get<DevelopmentChoices>(`${root(workspace)}/items/${encodeURIComponent(itemId)}/development/choices`)).data
}
export async function listDevelopment(workspace: WorkspaceKind, itemId: string) {
  return (await http.get<{ items: DevelopmentAssignment[] }>(`${root(workspace)}/items/${encodeURIComponent(itemId)}/development`)).data.items
}
export async function createDevelopment(workspace: WorkspaceKind, input: DevelopmentInput) {
  return (await http.post<DevelopmentAssignment>(`${root(workspace)}/development`, input)).data
}
export async function cancelDevelopment(workspace: WorkspaceKind, id: string) {
  return (await http.post<DevelopmentAssignment>(`${root(workspace)}/development/${encodeURIComponent(id)}/cancel`, {})).data
}
export interface DevelopmentDiff { runId: string; baseRevision: string; files: string[]; fileCount: number; patch: string; truncated: boolean; generatedInputsExcluded: string[]; generatedArtifactsExcluded: string[] }
export async function getDevelopmentDiff(workspace: WorkspaceKind, id: string) {
  return (await http.get<DevelopmentDiff>(`${root(workspace)}/development/${encodeURIComponent(id)}/diff`)).data
}
