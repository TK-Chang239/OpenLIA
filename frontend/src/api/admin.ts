import { ApiError, request } from './_request';
export { ApiError };

export interface InviteSummary {
  id: string;
  label: string | null;
  expires_at: string | null;
  max_uses: number | null;
  use_count: number;
  revoked_at: string | null;
  created_at: string;
}

export interface InviteCreated {
  id: string;
  token: string;
  label: string | null;
}

export interface AdminUserRow {
  id: string;
  email: string;
  display_name: string;
  is_admin: boolean;
  is_disabled: boolean;
  must_change_password: boolean;
  last_login_at: string | null;
}

export interface ResetRequestRow {
  id: string;
  user_id: string;
  requested_at: string;
  requested_ip: string | null;
  status: 'pending' | 'approved' | 'rejected';
}

export const listInvites = () => request<InviteSummary[]>('/api/admin/invites');

export const createInvite = (body: {
  label?: string | null;
  max_uses?: number | null;
  expires_at?: string | null;
}) => request<InviteCreated>('/api/admin/invites', { method: 'POST', body: JSON.stringify(body) });

export const revokeInvite = (id: string) =>
  request<void>(`/api/admin/invites/${id}/revoke`, { method: 'POST' });

export const listAdminUsers = () => request<AdminUserRow[]>('/api/admin/users');

export const disableUser = (id: string) =>
  request<void>(`/api/admin/users/${id}/disable`, { method: 'POST' });

export const enableUser = (id: string) =>
  request<void>(`/api/admin/users/${id}/enable`, { method: 'POST' });

export interface AdminResetPasswordResponse {
  temporary_password: string;
}

export const adminResetPassword = (id: string) =>
  request<AdminResetPasswordResponse>(`/api/admin/users/${id}/reset-password`, {
    method: 'POST',
    body: JSON.stringify({}),
  });

export const listResetRequests = () =>
  request<ResetRequestRow[]>('/api/admin/password-reset-requests');

export const approveResetRequest = (id: string) =>
  request<{ reset_token: string }>(
    `/api/admin/password-reset-requests/${id}/approve`,
    { method: 'POST' },
  );

export const rejectResetRequest = (id: string) =>
  request<void>(`/api/admin/password-reset-requests/${id}/reject`, { method: 'POST' });
