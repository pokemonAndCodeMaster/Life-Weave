import { http } from '@/shared/api/http'
import type { Revision } from './library'
export interface ResearchOutput {
 id:string;kind:'run'|'manual';title:string;content:string;version:string;runId:string|null
 state:string;createdAt:string;sourceBase:string|null;assetBase:string|null;downloadUrl:string|null
}
export interface ResearchOutputs {current:ResearchOutput|null;versions:ResearchOutput[]}
export interface KnowledgeCandidate extends Revision {itemId:string;runId:string;runVersion:string;sourceUrl:string;base_version:string}
export interface CandidateInput {runId:string;path:string;content:string;baseVersion:string;reason:string;requestId:string}
const path=(workspace:string,itemId:string)=>`/lifeweave/${workspace}/items/${encodeURIComponent(itemId)}`
export async function getResearchOutput(workspace:string,itemId:string){return (await http.get<ResearchOutputs>(path(workspace,itemId)+'/research-output')).data}
export async function getKnowledgeCandidates(workspace:string,itemId:string){return (await http.get<KnowledgeCandidate[]>(path(workspace,itemId)+'/knowledge-candidates')).data}
export async function proposeKnowledge(workspace:string,itemId:string,body:CandidateInput){return (await http.post<KnowledgeCandidate>(path(workspace,itemId)+'/knowledge-candidates',body)).data}
export async function saveOutputFeedback(workspace:string,itemId:string,body:{body:string;runId:string|null;requestId:string;anchor:string}){return (await http.post(path(workspace,itemId)+'/feedback',body)).data}
