import { Platform } from 'react-native';

import type { CaseListResponse, RewardCase, RewardCountry } from '@/types/reward-case';
import type { HomeSettings } from '@/lib/admin-api';

const fallbackApiBaseUrl = Platform.select({
  web: 'http://127.0.0.1:8000',
  default: 'http://127.0.0.1:8000',
});

export const API_BASE_URL =
  process.env.EXPO_PUBLIC_API_BASE_URL?.replace(/\/$/, '') ?? fallbackApiBaseUrl;

export function resolveApiAssetUrl(url: string): string {
  if (/^(?:[a-z][a-z\d+.-]*:|\/\/)/i.test(url)) {
    return url;
  }

  return `${API_BASE_URL}/${url.replace(/^\/+/, '')}`;
}

export type CaseSortMode = 'published_desc' | 'reward_desc' | 'reward_asc' | 'title_asc';

export type CaseQuery = {
  q?: string;
  country?: RewardCountry;
  region?: string;
  status?: string;
  source?: string;
  rewardMin?: number;
  rewardMax?: number;
  sort?: CaseSortMode;
  page?: number;
  pageSize?: number;
};

function buildCaseQuery(query: CaseQuery) {
  const params = new URLSearchParams();

  if (query.q?.trim()) params.set('q', query.q.trim());
  if (query.country) params.set('country', query.country);
  if (query.region) params.set('region', query.region);
  if (query.status) params.set('status', query.status);
  if (query.source) params.set('source', query.source);
  if (query.rewardMin !== undefined) params.set('reward_min', String(query.rewardMin));
  if (query.rewardMax !== undefined) params.set('reward_max', String(query.rewardMax));
  if (query.sort) params.set('sort', query.sort);
  if (query.page) params.set('page', String(query.page));
  if (query.pageSize) params.set('page_size', String(query.pageSize));

  return params.toString();
}

export async function fetchCasePage(
  query: CaseQuery = {},
  signal?: AbortSignal
): Promise<CaseListResponse> {
  const queryString = buildCaseQuery(query);
  const response = await fetch(`${API_BASE_URL}/cases${queryString ? `?${queryString}` : ''}`, {
    signal,
  });

  if (!response.ok) {
    throw new Error(`Cases request failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchCase(id: string): Promise<RewardCase> {
  const response = await fetch(`${API_BASE_URL}/cases/${encodeURIComponent(id)}`);

  if (!response.ok) {
    throw new Error(`Case request failed with status ${response.status}`);
  }

  return response.json();
}

export async function fetchHomeSettings(): Promise<HomeSettings> {
  const response = await fetch(`${API_BASE_URL}/settings/home`);

  if (!response.ok) {
    throw new Error(`Home settings request failed with status ${response.status}`);
  }

  return response.json();
}
