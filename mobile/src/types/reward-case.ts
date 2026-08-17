export type RewardCountry = 'US' | 'Canada' | 'China';
export type RewardCurrency = 'USD' | 'CAD' | 'CNY';

export type OfficialSourceRecord = {
  caseId: string;
  url: string;
  title?: string | null;
  author: string;
  reward: number | null;
  rewardCurrency?: RewardCurrency | null;
  rewardText?: string | null;
  sourceUpdatedDate?: string | null;
};

export type RewardCase = {
  id: string;
  title: string;
  agency: string;
  country: RewardCountry;
  regions?: string[];
  caseType?: string | null;
  description?: string | null;
  reward: number | null;
  rewardCurrency?: RewardCurrency | null;
  rewardText?: string | null;
  status: string;
  summary: string;
  warningMessage?: string | null;
  aliases?: string[];
  age?: string | null;
  dateOfBirth?: string | null;
  placeOfBirth?: string | null;
  sex?: string | null;
  race?: string | null;
  nationality?: string | null;
  hair?: string | null;
  eyes?: string | null;
  height?: string | null;
  weight?: string | null;
  locations?: string | null;
  distinguishingFeatures?: string | null;
  fieldOffice?: string | null;
  publishedDate: string;
  lastVerified: string;
  sourceUpdatedDate?: string | null;
  sourceUrl: string;
  sourceTitle?: string | null;
  sourceAuthor?: string | null;
  sourceKind?: 'official' | 'publisher';
  sourceRecords?: OfficialSourceRecord[];
  imageUrl: string | null;
  imageUrls?: string[];
};

export type CaseFacetOption = {
  value: string;
  count: number;
};

export type CaseFacets = {
  statuses: CaseFacetOption[];
  regions: CaseFacetOption[];
  sources: CaseFacetOption[];
};

export type CaseListResponse = {
  items: RewardCase[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
  facets: CaseFacets;
};
