import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export interface PluginDescriptor {
  id: string; name: string; description: string; kind: string; version: string
  operations: string[]; requires: string[]; composed_of: string[]
  implementationDigest: string; runnable: boolean; verified: boolean; reason: string
  enabled: boolean; configured: boolean; configVersion: number
  observation_boundary: string; configuration_link: string | null
}
export interface PluginStep {
  id: string; stage: string; pluginId: string; operation: string; required: boolean
  condition?: string; observed: boolean; callIds: string[]; observation: string
}
export interface PluginPlan {
  id: string; item_id: string; assignment_id: string; version: number; steps: PluginStep[]
  bindings: Record<string, { version: string; implementationDigest: string }>
}
export interface PluginCall {
  id: string; item_id: string; assignment_id: string | null; run_id: string | null; plan_id: string | null
  step_id: string | null; parent_call_id: string | null; plugin_id: string; plugin_version: string
  implementation_digest: string; operation: string; state: string; observed_by: string
  input_ref: Record<string, unknown>; output_ref: Record<string, unknown>
  has_error: boolean; error_code: string | null
  started_at: string; finished_at: string | null
}
export interface PluginProcess { itemId: string; plans: PluginPlan[]; calls: PluginCall[]; truncated: boolean; boundary: string }
const base = (workspace: WorkspaceKind) => `/lifeweave/${workspace}`
export async function pluginCatalog(workspace: WorkspaceKind) {
  return (await http.get<{ items: PluginDescriptor[]; total: number }>(`${base(workspace)}/plugins`)).data
}
export async function setPluginEnabled(workspace: WorkspaceKind, id: string, enabled: boolean, expectedVersion: number) {
  return (await http.put<PluginDescriptor>(`${base(workspace)}/plugins/${encodeURIComponent(id)}/enabled`,
    { enabled, expectedVersion })).data
}
export async function pluginDetail(workspace: WorkspaceKind, id: string) {
  return (await http.get<PluginDescriptor & { recentCalls: PluginCall[] }>(
    `${base(workspace)}/plugins/${encodeURIComponent(id)}`)).data
}
export async function pluginProcess(workspace: WorkspaceKind, itemId: string) {
  return (await http.get<PluginProcess>(`${base(workspace)}/items/${encodeURIComponent(itemId)}/plugin-process`)).data
}
