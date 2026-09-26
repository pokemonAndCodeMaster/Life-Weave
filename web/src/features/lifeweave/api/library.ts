import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'
export interface Source { id: string; title: string; root: string; writable: boolean; includedPaths?: string[]; archiveBaseUrl?: string | null }
export interface ReferenceMap { links: Record<string,string>; images: Record<string,string>; warnings: string[] }
export interface Document { path: string; sourceId: string; title: string; content: string; version: string; writable: boolean; sourceTitle: string; references?: ReferenceMap|null }
export interface Revision { id: string; source_id: string; path: string; content: string; before_content: string; diff: string; reason: string; status: 'draft'|'accepted'|'rejected'; created_at: string; references?: ReferenceMap|null }
export interface KnowledgeRelations {
  sourceId: string; path: string; version: string; scannedDocuments: number
  outgoing: Array<{ sourceId: string; path: string | null; label: string; href: string; status: 'valid' | 'missing' | 'blocked' | 'archived'; externalUrl?: string | null; count: number }>
  backlinks: Array<{ sourceId: string; path: string; title: string; label: string; count: number }>
  unavailableSources: string[]; unavailableDocuments: Array<{ path: string; reason: string }>
}
export interface SemanticRelations {
  sourceId: string; path: string; version: string
  items: Array<{ relation: 'implemented_by' | 'verified_by'; targetPath: string;
    sourceVersion: string; targetVersion: string; currentSourceVersion: string;
    currentTargetVersion: string | null; evidenceQuote: string; status: 'current' | 'stale' | 'missing';
    targetUrl: string | null }>
}
const root = (ws: WorkspaceKind) => `/lifeweave/${ws}/library`
export async function documents(ws: WorkspaceKind,q='',sourceId?:string) { return (await http.get<{items:Document[];unavailableSources:string[]}>(`${root(ws)}/documents`,{params:{q,sourceId}})).data }
export async function document(ws: WorkspaceKind,path:string,sourceId='local') { return (await http.get<Document>(`${root(ws)}/document`,{params:{path,sourceId}})).data }
export async function links(ws: WorkspaceKind,path:string,sourceId='local') { return (await http.get<KnowledgeRelations>(`${root(ws)}/links`,{params:{path,sourceId}})).data }
export async function semanticRelations(ws: WorkspaceKind,path:string,sourceId='local') { return (await http.get<SemanticRelations>(`${root(ws)}/relations`,{params:{path,sourceId}})).data }
export async function sources(ws: WorkspaceKind) { return (await http.get<Source[]>(`${root(ws)}/sources`)).data }
export async function revisions(ws: WorkspaceKind) { return (await http.get<Revision[]>(`${root(ws)}/revisions`)).data }
export async function propose(ws: WorkspaceKind,body: {sourceId:string;path:string;content:string;baseVersion:string;reason:string}) { return (await http.post<Revision>(`${root(ws)}/revisions`,body)).data }
export async function decide(ws: WorkspaceKind,id:string,accept:boolean) { return (await http.post<Revision>(`${root(ws)}/revisions/${id}/decision`,{accept})).data }
