import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export type ConversationMode = 'auto' | 'record' | 'discuss' | 'execute'
export interface ConversationInputContext { itemId: string | null; runId: string | null; anchor: string | null; researchItemIds?: string[]; repositoryPath?: string | null; acknowledgeExcludedChanges?: boolean }
export interface ConversationReceipt { kind: string; id: string; title: string; itemId?: string; runId?: string }
export interface ConversationTurn {
  id: string; body: string; mode: ConversationMode
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled'
  reply: string; receipts: ConversationReceipt[]; itemId: string | null; runId: string | null
  error: string | null; createdAt: string; updatedAt: string
  inputContext?: ConversationInputContext
  sources: Array<{ title?: string; path?: string; ref?: string; [key: string]: unknown }>
}
export interface ConversationSummary { id: string; title: string; itemId: string | null; createdAt: string; updatedAt: string }
export interface Conversation extends ConversationSummary { turns: ConversationTurn[] }
export interface TurnInput { requestId: string; body: string; mode: ConversationMode; itemId?: string | null; runId?: string | null; anchor?: string | null; researchItemIds?: string[]; repositoryPath?: string | null; acknowledgeExcludedChanges?: boolean }
export interface PersonalModel { version: number; goals: string; preferences: string; updatedAt: string | null }
const root = (workspace: WorkspaceKind) => `/lifeweave/${workspace}`
const path = (workspace: WorkspaceKind, id: string) => `${root(workspace)}/conversations/${encodeURIComponent(id)}`
export async function listConversations(workspace: WorkspaceKind, itemId?: string) {
  return (await http.get<{ items: ConversationSummary[]; total: number }>(`${root(workspace)}/conversations`, { params: { itemId } })).data
}
export async function createConversation(workspace: WorkspaceKind, input: { requestId: string; title?: string; itemId?: string | null }) {
  return (await http.post<ConversationSummary>(`${root(workspace)}/conversations`, input)).data
}
export async function getConversation(workspace: WorkspaceKind, id: string) { return (await http.get<Conversation>(path(workspace, id))).data }
export async function sendConversationTurn(workspace: WorkspaceKind, id: string, input: TurnInput) {
  return (await http.post<ConversationTurn>(`${path(workspace, id)}/turns`, input)).data
}
export async function cancelConversationTurn(workspace: WorkspaceKind, id: string, turnId: string) {
  return (await http.post<ConversationTurn>(`${path(workspace, id)}/turns/${encodeURIComponent(turnId)}/cancel`, {})).data
}
export async function getPersonalModel(workspace: WorkspaceKind) { return (await http.get<PersonalModel>(`${root(workspace)}/personal-model`)).data }
export async function savePersonalModel(workspace: WorkspaceKind, input: Pick<PersonalModel, 'version' | 'goals' | 'preferences'>) {
  return (await http.put<PersonalModel>(`${root(workspace)}/personal-model`, input)).data
}
