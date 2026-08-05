import AsyncStorage from '@react-native-async-storage/async-storage';

import { API_BASE_URL, resolveApiAssetUrl } from '@/lib/cases';
import type { RewardCase } from '@/types/reward-case';


const ADMIN_TOKEN_KEY = 'reward-watch:admin-token';

export type AdminDashboard = {
  adminEmail: string;
  counts: { cases: number; hidden: number; drafts: number };
  sync: {
    updatedAt: string;
    allSourcesFresh: boolean;
    totalCount: number;
    sources: {
      id: string;
      name: string;
      country: string;
      success: boolean;
      usedStaleData: boolean;
      count: number;
      error?: string | null;
    }[];
  } | null;
  quality: Record<string, unknown> | null;
  syncRunning: boolean;
};

export type AdminCaseSummary = {
  id: string;
  title: string;
  country: string;
  status: string;
  reward: number | null;
  rewardCurrency?: string | null;
  sourceName: string;
  imageUrl?: string | null;
  publishedDate: string;
  isVisible: boolean;
  reviewStatus: 'draft' | 'published';
  hasOverride: boolean;
};

export type AdminCaseDetail = {
  raw: RewardCase;
  effective: RewardCase;
  override: {
    fields: Partial<RewardCase>;
    isVisible: boolean;
    reviewStatus: 'draft' | 'published';
    note?: string | null;
    updatedBy?: string | null;
    updatedAt: string;
  } | null;
};

export type AuditEntry = {
  id: number;
  adminEmail: string;
  action: string;
  entityType: string;
  entityId: string;
  createdAt: string;
};

export type HomeSettings = {
  brandSubtitle: string;
  safetyMessage: string;
  featuredCaseIds: string[];
  recentCaseLimit: number;
};

async function adminRequest<T>(path: string, token: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
      ...init?.headers,
    },
  });

  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? `Admin request failed with status ${response.status}`);
  }
  return response.json();
}

export async function loadAdminToken() {
  return AsyncStorage.getItem(ADMIN_TOKEN_KEY);
}

export async function saveAdminToken(token: string) {
  await AsyncStorage.setItem(ADMIN_TOKEN_KEY, token);
}

export async function clearAdminToken() {
  await AsyncStorage.removeItem(ADMIN_TOKEN_KEY);
}

export async function loginAdmin(email: string, password: string) {
  const response = await fetch(`${API_BASE_URL}/admin/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email, password }),
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail ?? 'Unable to sign in');
  }
  return response.json() as Promise<{
    accessToken: string;
    expiresIn: number;
    admin: { email: string; role: string };
  }>;
}

export function fetchAdminDashboard(token: string) {
  return adminRequest<AdminDashboard>('/admin/dashboard', token);
}

export function fetchAdminCases(
  token: string,
  query: { q?: string; visibility?: string; reviewStatus?: string; page?: number } = {}
) {
  const params = new URLSearchParams({ page_size: '20' });
  if (query.q) params.set('q', query.q);
  if (query.visibility) params.set('visibility', query.visibility);
  if (query.reviewStatus) params.set('review_status', query.reviewStatus);
  if (query.page) params.set('page', String(query.page));
  return adminRequest<{
    items: AdminCaseSummary[];
    total: number;
    page: number;
    pageSize: number;
  }>(`/admin/cases?${params}`, token);
}

export function fetchAdminCase(token: string, caseId: string) {
  return adminRequest<AdminCaseDetail>(`/admin/cases/${encodeURIComponent(caseId)}`, token);
}

export function updateAdminCase(token: string, caseId: string, body: Record<string, unknown>) {
  return adminRequest(`/admin/cases/${encodeURIComponent(caseId)}`, token, {
    method: 'PATCH',
    body: JSON.stringify(body),
  });
}

export function resetAdminCase(token: string, caseId: string) {
  return adminRequest(`/admin/cases/${encodeURIComponent(caseId)}/override`, token, {
    method: 'DELETE',
  });
}

export function fetchAuditLog(token: string) {
  return adminRequest<AuditEntry[]>('/admin/audit?limit=50', token);
}

export function triggerAdminSync(token: string) {
  return adminRequest<{ accepted: boolean }>('/admin/sync', token, { method: 'POST' });
}

export function fetchAdminHomeSettings(token: string) {
  return adminRequest<{
    published: HomeSettings;
    draft: HomeSettings | null;
    draftUpdatedAt?: string | null;
    draftUpdatedBy?: string | null;
  }>('/admin/settings/home', token);
}

export function saveAdminHomeSettings(token: string, settings: HomeSettings) {
  return adminRequest('/admin/settings/home', token, {
    method: 'PATCH',
    body: JSON.stringify(settings),
  });
}

export function publishAdminHomeSettings(token: string) {
  return adminRequest('/admin/settings/home/publish', token, { method: 'POST' });
}

export function resolveAdminImage(url?: string | null) {
  return url ? resolveApiAssetUrl(url) : null;
}
