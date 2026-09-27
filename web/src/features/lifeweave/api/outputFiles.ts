import { http } from '@/shared/api/http'
import type { WorkspaceKind } from '../types'

export type OutputFileCategory = 'document' | 'code' | 'verification' | 'attachment' | 'record'
export type OutputFileStatus = 'added' | 'modified' | 'deleted' | 'renamed' | 'unchanged'

export interface OutputDocumentRef {
  itemId: string
  outputId: string
  path: string
  version: string
}

export interface OutputCatalogFile {
  path: string
  previousPath?: string | null
  category: OutputFileCategory
  status: OutputFileStatus
  additions: number | null
  deletions: number | null
  binary: boolean
  size: number
  contentType: string
  documentRef?: OutputDocumentRef | null
}

export interface OutputCatalog {
  outputId: string
  title: string
  version: string
  files: OutputCatalogFile[]
  warnings?: string[]
  snapshotBoundary?: string | null
}

export interface OutputFileContent {
  path: string
  previousPath?: string | null
  version: string
  binary: boolean
  contentType: string
  before: string | null
  after: string | null
  content: string | null
  diff: string | null
}

const root = (workspace: WorkspaceKind, itemId: string) =>
  `/lifeweave/${workspace}/items/${encodeURIComponent(itemId)}/outputs`

export async function getOutputCatalog(workspace: WorkspaceKind, itemId: string, outputId: string, version?: string | null) {
  return (await http.get<OutputCatalog>(`${root(workspace, itemId)}/catalog`, {
    params: { outputId, ...(version ? { version } : {}) },
  })).data
}

export async function getOutputFile(workspace: WorkspaceKind, itemId: string, outputId: string, path: string, version: string) {
  return (await http.get<OutputFileContent>(`${root(workspace, itemId)}/file`, {
    params: { outputId, path, version },
  })).data
}

export async function getOutputAsset(workspace: WorkspaceKind, itemId: string, outputId: string, path: string, version: string) {
  return (await http.get<Blob>(`${root(workspace, itemId)}/asset`, { params: { outputId, path, version }, responseType: 'blob' })).data
}

export async function downloadOutputFile(workspace: WorkspaceKind, itemId: string, outputId: string, path: string, version: string) {
  return (await http.get<Blob>(`${root(workspace, itemId)}/download`, { params: { outputId, path, version }, responseType: 'blob' })).data
}

export async function downloadOutputBundle(workspace: WorkspaceKind, itemId: string, outputId: string, version: string) {
  return (await http.get<Blob>(`${root(workspace, itemId)}/bundle`, { params: { outputId, version }, responseType: 'blob' })).data
}
