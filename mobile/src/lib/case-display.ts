import type {
  OfficialSourceRecord,
  RewardCase,
  RewardCountry,
  RewardCurrency,
} from '@/types/reward-case';

export function getCaseSourceName(rewardCase: RewardCase) {
  return rewardCase.sourceAuthor?.trim() || rewardCase.agency;
}

export function isPublisherNotice(rewardCase: RewardCase) {
  return rewardCase.sourceKind === 'publisher' || rewardCase.id.startsWith('manual-');
}

export function getCaseRegions(rewardCase: RewardCase) {
  return rewardCase.regions?.filter(Boolean) ?? [];
}

export function getCaseRegionLabel(rewardCase: RewardCase) {
  return getCaseRegions(rewardCase).join(' / ');
}

export function formatCaseReward(rewardCase: RewardCase) {
  return formatRewardAmount(
    rewardCase.reward,
    rewardCase.rewardCurrency,
    rewardCase.country
  );
}

export function formatRewardAmount(
  value: number | null | undefined,
  currency: RewardCurrency | null | undefined,
  country: RewardCountry
) {
  if (value === null || value === undefined) {
    return 'Not published';
  }

  const resolvedCurrency = currency ?? (country === 'Canada' ? 'CAD' : 'USD');
  const formatted = new Intl.NumberFormat('en-US', {
    maximumFractionDigits: 0,
    style: 'currency',
    currency: resolvedCurrency,
    currencyDisplay: 'narrowSymbol',
  }).format(value);
  return resolvedCurrency === 'CAD' ? `${formatted} CAD` : formatted;
}

export function getCaseOfficialSources(rewardCase: RewardCase): OfficialSourceRecord[] {
  if (rewardCase.sourceRecords && rewardCase.sourceRecords.length > 0) {
    return rewardCase.sourceRecords;
  }

  return [
    {
      author: getCaseSourceName(rewardCase),
      caseId: rewardCase.id,
      reward: rewardCase.reward,
      rewardCurrency: rewardCase.rewardCurrency,
      rewardText: rewardCase.rewardText,
      sourceUpdatedDate: rewardCase.sourceUpdatedDate,
      title: rewardCase.sourceTitle,
      url: rewardCase.sourceUrl,
    },
  ];
}

export function normalizeSearchText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}
