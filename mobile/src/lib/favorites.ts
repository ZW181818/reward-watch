import AsyncStorage from '@react-native-async-storage/async-storage';

import type { RewardCase } from '@/types/reward-case';

const favoritesKey = 'reward-watch.favorite-case-ids';

export async function loadFavoriteIds(): Promise<string[]> {
  const rawValue = await AsyncStorage.getItem(favoritesKey);

  if (!rawValue) {
    return [];
  }

  try {
    const parsedValue = JSON.parse(rawValue);
    return Array.isArray(parsedValue)
      ? parsedValue.filter((item): item is string => typeof item === 'string')
      : [];
  } catch {
    return [];
  }
}

export async function saveFavoriteIds(ids: string[]) {
  await AsyncStorage.setItem(favoritesKey, JSON.stringify(Array.from(new Set(ids))));
}

export function isCaseFavorite(rewardCase: RewardCase, ids: string[]) {
  const compatibleIds = [
    rewardCase.id,
    ...(rewardCase.sourceRecords?.map((source) => source.caseId) ?? []),
  ];
  return compatibleIds.some((id) => ids.includes(id));
}

export async function toggleFavoriteCase(rewardCase: RewardCase): Promise<string[]> {
  const ids = await loadFavoriteIds();
  const compatibleIds = new Set([
    rewardCase.id,
    ...(rewardCase.sourceRecords?.map((source) => source.caseId) ?? []),
  ]);
  const isFavorite = ids.some((id) => compatibleIds.has(id));
  const withoutCompatibleIds = ids.filter((id) => !compatibleIds.has(id));
  const nextIds = isFavorite
    ? withoutCompatibleIds
    : [...withoutCompatibleIds, rewardCase.id];
  await saveFavoriteIds(nextIds);
  return nextIds;
}
