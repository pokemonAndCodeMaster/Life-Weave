import type { AxiosError } from 'axios'
import { http } from '@/shared/api/http'
import type {
  ApiErrorShape,
  LifeWeaveRun,
  Machine,
  WorkspaceKind,
  WorkspaceState,
  WorkItem,
} from '../types'

const root = (workspace: WorkspaceKind) => `/lifeweave/${workspace}`

export async function getLifeWeaveConfig() {
  const { data } = await http.get<{ workspaces: WorkspaceKind[]; defaultWorkspace: WorkspaceKind; identityMode: string }>('/lifeweave/config')
  return data
}

export function apiError(error: unknown): ApiErrorShape {
  if (error && typeof error === 'object' && 'message' in error && 'status' in error) return error as ApiErrorShape
  const candidate = error as AxiosError<{ detail?: unknown; message?: string }>
  const status = candidate.response?.status ?? 0
  const detail = candidate.response?.data?.detail
  const fallback = status === 409
    ? '内容已经被其他更新修改，请刷新后再试。'
    : status === 0
      ? '无法连接 LifeWeave 服务，请确认后端已经启动。'
      : '这次操作没有完成，请稍后重试。'
  return {
    status,
    detail,
    message: candidate.response?.data?.message
      ?? (typeof detail === 'string' ? detail : error instanceof Error ? error.message : fallback),
  }
}

export async function getWorkspaceState(workspace: WorkspaceKind) {
  const { data } = await http.get<WorkspaceState>(`${root(workspace)}/state`)
  return data
}

export async function getItemDetail(workspace: WorkspaceKind, itemId: string) {
  const { data } = await http.get<WorkItem>(`${root(workspace)}/items/${encodeURIComponent(itemId)}`)
  return data
}

export async function getEntityDetail(workspace: WorkspaceKind, entityId: string) {
  const { data } = await http.get(`${root(workspace)}/entities/${encodeURIComponent(entityId)}`)
  return data
}

export async function getKnowledgeList(workspace: WorkspaceKind, query = '') {
  const { data } = await http.get(`${root(workspace)}/knowledge`, { params: { q: query || undefined } })
  return data
}

export async function getKnowledgeDocument(workspace: WorkspaceKind, path: string) {
  const { data } = await http.get(`${root(workspace)}/knowledge/document`, { params: { path } })
  return data
}

export async function createKnowledgeProposal(workspace: WorkspaceKind, payload: Record<string, unknown>) {
  const { data } = await http.post(`${root(workspace)}/knowledge/proposals`, payload)
  return data
}

export async function createCapability(workspace: WorkspaceKind, payload: Record<string, unknown>) {
  const { data } = await http.post(`${root(workspace)}/capabilities`, payload)
  return data
}

export async function listCapabilities(workspace: WorkspaceKind) {
  const { data } = await http.get(`${root(workspace)}/capabilities`)
  return data
}

export async function listMethods(workspace: WorkspaceKind) {
  const { data } = await http.get<{ items: Array<{ id: string; title: string; description: string; path: string }>; unavailable: Array<{ path: string; reason: string }> }>(`${root(workspace)}/methods`)
  return data
}

export interface EvaluationTask {
  id: string
  workspace: WorkspaceKind
  itemId: string
  targetKind: 'system' | 'capability'
  candidateId: string | null
  candidateVersion: string | null
  repeatOf: string | null
  previous?: { id: string; outcome: 'passed' | 'failed' | 'inconclusive' | null; runId: string | null; candidateVersion: string | null; assessment: string | null }
  title: string
  instruction: string
  criteria: string
  state: 'planned' | 'running' | 'assessed'
  runId: string | null
  outcome: 'passed' | 'failed' | 'inconclusive' | null
  assessment: string | null
  evidenceId: string | null
  improvementId?: string | null
  createdAt: string
  run?: { id: string; state: string; engine: string; itemId: string; finishedAt?: string | null;
    repositoryPath?: string | null; repositoryRevision?: string | null;
    selectedInputs?: { methodId?: string | null; knowledgeRefs?: string[] } }
  evidence?: Array<{ id: string; status: string; summary?: string | null }>
}

export async function listEvaluations(workspace: WorkspaceKind, limit = 30, offset = 0) {
  const { data } = await http.get<{ items: EvaluationTask[]; total: number }>(`${root(workspace)}/evaluations`, { params: { limit, offset } })
  return data
}

export async function listCandidateEvaluations(workspace: WorkspaceKind, candidateId: string, limit = 10, offset = 0) {
  const { data } = await http.get<{ items: EvaluationTask[]; total: number; lineage: Array<{ id: string; title: string; version: string }> }>(
    `${root(workspace)}/capabilities/${encodeURIComponent(candidateId)}/evaluations`, { params: { limit, offset } },
  )
  return data
}

export async function createEvaluation(workspace: WorkspaceKind, payload: {
  itemId: string; targetKind: 'system' | 'capability'; candidateId?: string | null; repeatOf?: string | null
  title: string; instruction: string; criteria: string
}) {
  const { data } = await http.post<EvaluationTask>(`${root(workspace)}/evaluations`, payload)
  return data
}

export async function startEvaluation(workspace: WorkspaceKind, id: string, payload: {
  engine: 'codex' | 'opencode'; permission: 'read-only' | 'workspace-write'; model?: string | null
  directory?: string | null; methodId?: string | null; knowledgeRefs?: string[]
}) {
  const { data } = await http.post<EvaluationTask>(`${root(workspace)}/evaluations/${encodeURIComponent(id)}/start`, payload)
  return data
}

export async function assessEvaluation(workspace: WorkspaceKind, id: string, payload: {
  outcome: 'passed' | 'failed' | 'inconclusive'; assessment: string; evidenceId?: string | null
}) {
  const { data } = await http.post<EvaluationTask>(`${root(workspace)}/evaluations/${encodeURIComponent(id)}/assess`, payload)
  return data
}

export async function createEvaluationImprovement(workspace: WorkspaceKind, id: string, payload: {
  targetKind: 'knowledge' | 'skill' | 'agent' | 'harness'
  problem: string; desiredBehavior: string; validationPlan: string
}) {
  const { data } = await http.post<EvaluationTask>(`${root(workspace)}/evaluations/${encodeURIComponent(id)}/improvement`, payload)
  return data
}

export async function getCapability(workspace: WorkspaceKind, id: string) {
  const { data } = await http.get(`${root(workspace)}/capabilities/${encodeURIComponent(id)}`)
  return data
}

export async function getMeetingMarkdown(workspace: WorkspaceKind, snapshotId?: string) {
  const response = await http.get(`${root(workspace)}/meeting/markdown`, { responseType: 'text', params: { snapshotId } })
  return String(response.data)
}

export async function getMeetingPreview(workspace: WorkspaceKind) {
  const { data } = await http.get(`${root(workspace)}/meeting/preview`)
  return data
}

export async function getMeetingSnapshot(workspace: WorkspaceKind, snapshotId: string) {
  const { data } = await http.get(`${root(workspace)}/meeting/snapshots/${encodeURIComponent(snapshotId)}`)
  return data
}

export async function getContextHistory(workspace: WorkspaceKind, itemId: string) {
  const { data } = await http.get(`${root(workspace)}/items/${encodeURIComponent(itemId)}/context/history`)
  return data
}

export async function verifyCapability(workspace: WorkspaceKind, id: string, payload: Record<string, unknown>) {
  const { data } = await http.post(`${root(workspace)}/capabilities/${encodeURIComponent(id)}/verify`, payload)
  return data
}

export async function publishCapability(workspace: WorkspaceKind, id: string, version: string) {
  const { data } = await http.post(`${root(workspace)}/capabilities/${encodeURIComponent(id)}/publish`, { version })
  return data
}

export async function mutateWorkspace<T>(
  workspace: WorkspaceKind,
  path: string,
  method: 'post' | 'put' | 'patch' | 'delete',
  payload?: unknown,
) {
  const { data } = await http.request<T>({
    url: `${root(workspace)}${path}`,
    method,
    data: payload,
  })
  return data
}

export async function listRuns(workspace: WorkspaceKind, params: {itemId?:string;limit?:number} = {}) {
  const { data } = await http.get<LifeWeaveRun[] | { items: LifeWeaveRun[] }>(`${root(workspace)}/runs`,{params})
  return Array.isArray(data) ? data : data.items
}

export async function listCandidateRuns(workspace: WorkspaceKind, candidateId: string, limit = 10, offset = 0) {
  const { data } = await http.get<{ items: LifeWeaveRun[]; total: number }>(
    `${root(workspace)}/runs`, { params: { candidateId, limit, offset } },
  )
  return data
}

export async function getRun(workspace: WorkspaceKind, runId: string) {
  const { data } = await http.get<LifeWeaveRun>(`${root(workspace)}/runs/${encodeURIComponent(runId)}`)
  return data
}

export async function getRunEvents(workspace: WorkspaceKind, runId: string) {
  const data = await getRunEventsPage(workspace, runId)
  return data.items ?? []
}

export async function getRunEventsPage(workspace: WorkspaceKind, runId: string, afterSequence = 0) {
  const { data } = await http.get<{ items?: LifeWeaveRun['events']; nextSequence: number }>(`${root(workspace)}/runs/${encodeURIComponent(runId)}/events`, { params: { afterSequence, limit: 200 } })
  return { items: data.items ?? [], nextSequence: data.nextSequence }
}

export async function getRunArtifactResult(workspace: WorkspaceKind, runId: string) {
  const response = await http.get<string>(`${root(workspace)}/runs/${encodeURIComponent(runId)}/artifacts/result`, { responseType: 'text' })
  return { content: String(response.data), version: String(response.headers['x-artifact-version'] ?? response.headers.etag ?? '') }
}

export async function createRun(
  workspace: WorkspaceKind,
  payload: {
    itemId: string
    instruction: string
    engine: 'codex' | 'opencode'
    runtime: 'native' | 'docker'
    image?: string
    directory?: string
    branch?: string
    model?: string
    permission?: 'read-only' | 'workspace-write'
    capabilityCandidateId?: string
  },
) {
  const { data } = await http.post<LifeWeaveRun>(`${root(workspace)}/runs`, payload)
  return data
}

export async function runAction(workspace: WorkspaceKind, runId: string, action: 'pause' | 'cancel' | 'retry', payload: Record<string, unknown> = {}) {
  const { data } = await http.post<LifeWeaveRun>(`${root(workspace)}/runs/${encodeURIComponent(runId)}/${action}`, action === 'retry' ? { syncContext: true, ...payload } : payload)
  return data
}

export async function listMachines(workspace: WorkspaceKind) {
  const { data } = await http.get<Machine[] | { items: Machine[] }>(`${root(workspace)}/machines`)
  return Array.isArray(data) ? data : data.items
}

export async function machineAction(workspace: WorkspaceKind, machineId: string, action: 'enable' | 'pause' | 'drain') {
  const { data } = await http.post<Machine>(`${root(workspace)}/machines/${encodeURIComponent(machineId)}/state`, { action })
  return data
}
