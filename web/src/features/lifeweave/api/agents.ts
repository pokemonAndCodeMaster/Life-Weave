import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export type ExecutionKind = 'managed_development' | 'managed_run' | 'external_session' | 'organization'
export interface AgentDefinition {
  id: string; name: string; description: string; version: number
  capability: 'development' | 'research' | 'general' | 'organization'
  pluginId: string; methodId?: string | null
  engine: 'codex' | 'opencode' | 'builtin'; model?: string | null
  runtime?: 'native' | 'docker'; permission?: 'read-only' | 'workspace-write'
  enabled: boolean; available: boolean; reason?: string; modes: string[]
}
export interface AgentEngine { id: string; label: string; available: boolean; reason?: string; version?: string }
export interface AgentCatalog { items: AgentDefinition[]; engines: AgentEngine[] }
export interface AgentChoices extends AgentCatalog { itemId: string; recommendedAgentId?: string | null; environment?: Record<string, unknown> }
export type AgentCreateInput = Pick<AgentDefinition, 'id' | 'name' | 'description' | 'capability' | 'engine' | 'enabled'> & Partial<Pick<AgentDefinition, 'methodId' | 'model' | 'runtime' | 'permission'>>
export type AgentPatchInput = Pick<AgentDefinition, 'version'> & Partial<Pick<AgentDefinition, 'name' | 'description' | 'methodId' | 'engine' | 'model' | 'runtime' | 'permission' | 'enabled'>>
export interface ExecutionRef {
  kind: ExecutionKind; id: string; itemId: string; agentId: string; agentName?: string
  agentIdentity?: 'registered' | 'inferred'
  agentIds?: string[]
  status: string; createdAt: string; updatedAt?: string; engine?: string; model?: string
  runIds?: string[]; traceCoverage: string; title?: string
}
export interface ExecutionEvent {
  id: string; source: string; observed: 'native' | 'platform' | 'reported'; eventType: string; summary: string
  occurredAt: string; sequence?: number; payload?: Record<string, unknown> | null
}
export interface ExecutionDetail {
  execution: ExecutionRef
  configuration: Record<string, unknown>
  inputs: Record<string, unknown>
  events: ExecutionEvent[]
  outputs: Array<Record<string, unknown>>
  children: Array<{stage:string;kind:'managed_run';id:string;status:string}>
  coverage: { level: string; description: string; missing: string[]; eventCount?: number }
  links: Record<string, unknown>
  launches?: Array<{operation:string;agentId:string;agentName?:string;agentVersion?:number;configuration:Record<string,unknown>;input:Record<string,unknown>;output:Record<string,unknown>;createdAt:string;requestId?:string;itemId:string}>
}
export interface AgentDispatchInput {
  requestId: string; agentId: string; mode: 'managed_development' | 'managed_run' | 'organization'
  engine?: string; model?: string; instruction?: string; repositoryPath?: string
  methodId?: string; knowledgeRefs?: string[]; reviewMode?: string; executionScope?: string
  directory?: string; runtime?: 'native' | 'docker'; permission?: 'read-only' | 'workspace-write'
  image?: string; branch?: string; capabilityCandidateId?: string
  stepId?: string; planVersion?: number; acknowledgeExcludedChanges?: boolean
  organization?: { proposalId?: string; action: 'propose' | 'apply'; itemIds?: string[] }
}
const root = (workspace: WorkspaceKind) => `/lifeweave/${workspace}`
export async function listAgents(workspace: WorkspaceKind) {
  return (await http.get<AgentCatalog>(`${root(workspace)}/agents`)).data
}
export async function createAgent(workspace: WorkspaceKind, input: AgentCreateInput) {
  return (await http.post<AgentDefinition>(`${root(workspace)}/agents`, input)).data
}
export async function updateAgent(workspace: WorkspaceKind, id: string, input: AgentPatchInput) {
  return (await http.patch<AgentDefinition>(`${root(workspace)}/agents/${encodeURIComponent(id)}`, input)).data
}
export async function getAgentChoices(workspace: WorkspaceKind, itemId: string) {
  return (await http.get<AgentChoices>(`${root(workspace)}/items/${encodeURIComponent(itemId)}/agent-choices`)).data
}
export async function dispatchAgent(workspace: WorkspaceKind, itemId: string, input: AgentDispatchInput) {
  return (await http.post<ExecutionRef>(`${root(workspace)}/items/${encodeURIComponent(itemId)}/agent-dispatch`, input)).data
}
export async function listAgentExecutions(workspace: WorkspaceKind, params: {agentId?: string; itemId?: string; status?: string; limit?: number; offset?: number} = {}) {
  return (await http.get<{items: ExecutionRef[]; total: number; limit?: number; offset?: number}>(`${root(workspace)}/agent-executions`, { params })).data
}
export async function getAgentExecution(workspace: WorkspaceKind, kind: ExecutionKind, id: string) {
  return (await http.get<ExecutionDetail>(`${root(workspace)}/agent-executions/${kind}/${encodeURIComponent(id)}`)).data
}
