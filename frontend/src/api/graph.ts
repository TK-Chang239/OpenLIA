/**
 * Typed wrappers for the cross-session graph memory routes (slice 8).
 *
 * Backend file: ``packages/server/src/openlia_server/routes/graph.py``.
 * Routes are mounted under ``/graph``; the dev/prod ``/api`` prefix is
 * stripped by the server middleware so we call ``/api/graph/...`` here.
 */

import { request } from './_request';

export type ProposalStatus = 'pending' | 'accepted' | 'dismissed';
export type ConstructKind = 'position' | 'thesis' | 'concern' | 'watchlist_item' | string;

/** Free-form JSON payload from the LLM extractor. Shape is kind-specific. */
export interface ProposalPayload {
  construct_kind?: string;
  statement?: string;
  entity_kind?: string;
  entity_value?: string;
  source_excerpt?: string;
  artifact_kind?: string;
  artifact_id?: string;
  [key: string]: unknown;
}

export interface Proposal {
  id: string;
  kind: string;
  payload: ProposalPayload;
  status: ProposalStatus;
  created_at: string;
}

export interface ProposalListResponse {
  items: Proposal[];
}

export interface ConstructProvenance {
  source_kind?: string;
  source_id?: string;
  source_excerpt?: string | null;
  [key: string]: unknown;
}

export interface Construct {
  id: string;
  kind: ConstructKind;
  status: string;
  statement: string;
  entity_id: string;
  created_at: string;
  updated_at: string;
  provenance?: ConstructProvenance | null;
}

export interface ConstructListResponse {
  items: Construct[];
}

export const listProposals = (status: ProposalStatus = 'pending') =>
  request<ProposalListResponse>(`/api/graph/proposals?status=${encodeURIComponent(status)}`);

export const acceptProposal = (id: string) =>
  request<Construct | null>(`/api/graph/proposals/${encodeURIComponent(id)}/accept`, {
    method: 'POST',
  });

export const dismissProposal = (id: string) =>
  request<{ ok: boolean }>(`/api/graph/proposals/${encodeURIComponent(id)}/dismiss`, {
    method: 'POST',
  });

export const listConstructs = (entityId?: string) => {
  const qs = entityId ? `?entity_id=${encodeURIComponent(entityId)}` : '';
  return request<ConstructListResponse>(`/api/graph/constructs${qs}`);
};

export const deleteConstruct = (id: string) =>
  request<void>(`/api/graph/constructs/${encodeURIComponent(id)}`, { method: 'DELETE' });
