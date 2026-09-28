import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export interface OrganizationItem { id: string; title: string; status: string; version: number; topicIds: string[]; domainIds: string[]; parentId: string | null; organizationReason?: string }
export interface OrganizationEntity { id: string; title: string; entityType: string }
export interface OrganizationRule { id: string; title: string; terms: string[]; topicIds: string[]; domainIds: string[]; enabled: boolean }
export interface OrganizationChange { itemId: string; itemVersion: number; topicIds?: string[]; domainIds?: string[]; parentId?: string | null; reason: string }
export interface OrganizationGroup { key: string; title: string; goal: string; itemIds: string[] }
export interface OrganizationProposal {
  id: string; status: 'proposed' | 'applied' | 'undone'; reason: string
  changes: Array<{ itemId: string; title: string; before: {topicIds:string[];domainIds:string[];parentId:string|null}; after: {topicIds:string[];domainIds:string[];parentId:string|null}; reason: string }>
  groups: OrganizationGroup[]; createdAt: string; appliedAt?: string; warnings: string[]
}
export interface OrganizationCatalog {
  workspace: WorkspaceKind; topics: OrganizationEntity[]; domains: OrganizationEntity[]
  items: OrganizationItem[]; unorganizedItems: OrganizationItem[]
  rules: OrganizationRule[]; rulesVersion: number | null; proposals: OrganizationProposal[]
}
const root = (workspace: WorkspaceKind) => `/lifeweave/${workspace}/item-organization`
export async function getOrganizationCatalog(workspace: WorkspaceKind) { return (await http.get<OrganizationCatalog>(`${root(workspace)}/catalog`)).data }
export async function createOrganizationProposal(workspace: WorkspaceKind, input: {requestId:string;itemIds?:string[];changes?:OrganizationChange[];groups?:OrganizationGroup[];reason?:string}) { return (await http.post<OrganizationProposal>(`${root(workspace)}/proposals`, input)).data }
export async function getOrganizationProposal(workspace: WorkspaceKind, id: string) { return (await http.get<OrganizationProposal>(`${root(workspace)}/proposals/${encodeURIComponent(id)}`)).data }
export async function applyOrganizationProposal(workspace: WorkspaceKind, id: string) { return (await http.post<OrganizationProposal>(`${root(workspace)}/proposals/${encodeURIComponent(id)}/apply`, {requestId:crypto.randomUUID()})).data }
export async function undoOrganizationProposal(workspace: WorkspaceKind, id: string) { return (await http.post<OrganizationProposal>(`${root(workspace)}/proposals/${encodeURIComponent(id)}/undo`, {requestId:crypto.randomUUID()})).data }
export async function saveOrganizationRules(workspace: WorkspaceKind, input: {version?:number;rules:OrganizationRule[]}) { return (await http.put<{version:number;rules:OrganizationRule[]}>(`${root(workspace)}/rules`, input)).data }
