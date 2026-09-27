import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export type WorkStepState = 'planned' | 'running' | 'waiting' | 'succeeded' | 'failed' | 'cancelled' | 'unobserved'
export interface WorkOutputRef {
  id: string
  title: string
  kind: 'research' | 'development' | 'artifact' | 'note'
  summary: string
  state?: string
  createdAt?: string | null
  version?: string | null
  runId?: string | null
  assignmentId?: string | null
  artifactId?: string | null
  uri?: string | null
}
export interface WorkStep {
  id: string
  title: string
  description: string
  state: WorkStepState
  summary: string
  dependsOn: string[]
  outputIds: string[]
  runId?: string | null
  assignmentId?: string | null
  contextRefs?: Array<{ title: string; uri?: string | null }>
  provenance?: string
}
export interface ItemWorkView {
  itemId: string
  itemVersion: number
  current: { state: string; label: string; summary: string; updatedAt?: string | null }
  plan: {
    id: string
    title: string
    provider: string
    source: 'declared' | 'observed' | 'empty'
    version: number
    editable: boolean
    nodes: WorkStep[]
  }
  outputs: WorkOutputRef[]
  warnings: string[]
}
export interface WorkPlanInput {
  version: number
  title: string
  provider: string
  nodes: WorkStep[]
}
const root = (workspace: WorkspaceKind, itemId: string) => `/lifeweave/${workspace}/items/${encodeURIComponent(itemId)}`
export async function getWorkView(workspace: WorkspaceKind, itemId: string) {
  return (await http.get<ItemWorkView>(`${root(workspace, itemId)}/work-view`)).data
}
export async function saveWorkPlan(workspace: WorkspaceKind, itemId: string, input: WorkPlanInput) {
  return (await http.put<ItemWorkView>(`${root(workspace, itemId)}/work-plan`, input)).data
}
