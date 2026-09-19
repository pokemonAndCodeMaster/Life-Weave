import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'
export interface Source { id: string; title: string; root: string; writable: boolean }
export interface Document { path: string; sourceId: string; title: string; content: string; version: string; writable: boolean; sourceTitle: string }
export interface Revision { id: string; source_id: string; path: string; content: string; before_content: string; diff: string; reason: string; status: 'draft'|'accepted'|'rejected'; created_at: string }
const root = (ws: WorkspaceKind) => `/lifeweave/${ws}/library`
export async function documents(ws: WorkspaceKind,q='') { return (await http.get<{items:Document[];unavailableSources:string[]}>(`${root(ws)}/documents`,{params:{q}})).data }
export async function document(ws: WorkspaceKind,path:string,sourceId='local') { return (await http.get<Document>(`${root(ws)}/document`,{params:{path,sourceId}})).data }
export async function sources(ws: WorkspaceKind) { return (await http.get<Source[]>(`${root(ws)}/sources`)).data }
export async function revisions(ws: WorkspaceKind) { return (await http.get<Revision[]>(`${root(ws)}/revisions`)).data }
export async function propose(ws: WorkspaceKind,body: {sourceId:string;path:string;content:string;baseVersion:string;reason:string}) { return (await http.post<Revision>(`${root(ws)}/revisions`,body)).data }
export async function decide(ws: WorkspaceKind,id:string,accept:boolean) { return (await http.post<Revision>(`${root(ws)}/revisions/${id}/decision`,{accept})).data }
