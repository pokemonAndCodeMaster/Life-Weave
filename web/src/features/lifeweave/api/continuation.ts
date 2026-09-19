import { http } from '@/shared/api/http'

export interface InputRecommendations {
  methods: Array<{ id: string; title: string; description: string; version: string; reason: string }>
  documents: Array<{ ref: string; sourceId: string; title: string; sourceTitle: string; path: string; version: string; reason: string }>
  suggested: { methodId: string | null; knowledgeRefs: string[] }
  unavailable: Array<{ path: string; reason: string }>
  boundary: string
}

export interface Continuation {
  readAt: string
  context: { revisionNo: number; content: Record<string, unknown> }
  feedback: Array<{ id: string; body: string; runId?: string | null }>
  runs: Array<{ id: string; state: string; result: string | null; error: string | null }>
  nextStep: { declared: string | null; openProposalCount: number; note: string }
}

const path = (workspace: string, itemId: string) => `/lifeweave/${workspace}/items/${encodeURIComponent(itemId)}`
export async function getContinuation(workspace: string, itemId: string) {
  return (await http.get<Continuation>(path(workspace, itemId) + '/continuation')).data
}
export async function getRecommendations(workspace: string, itemId: string, query = '') {
  return (await http.get<InputRecommendations>(path(workspace, itemId) + '/input-recommendations', { params: { query } })).data
}
export async function saveFeedback(workspace: string, itemId: string, body: string, runId: string | null, requestId: string) {
  return (await http.post(path(workspace, itemId) + '/feedback', { body, runId, requestId })).data
}
