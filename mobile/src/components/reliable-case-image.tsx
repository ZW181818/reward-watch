import { useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import { Image, type ImageProps } from 'expo-image';

import { resolveApiAssetUrl } from '@/lib/cases';
import type { RewardCase } from '@/types/reward-case';

type ReliableCaseImageProps = {
  contentFit: NonNullable<ImageProps['contentFit']>;
  fallback: ReactNode;
  loadDelayMs?: number;
  rewardCase: RewardCase;
  style: ImageProps['style'];
};

export function ReliableCaseImage({
  contentFit,
  fallback,
  loadDelayMs = 0,
  rewardCase,
  style,
}: ReliableCaseImageProps) {
  const imageUrls = useMemo(
    () =>
      Array.from(
        new Set(
          [rewardCase.imageUrl, ...(rewardCase.imageUrls ?? [])]
            .filter((imageUrl): imageUrl is string => Boolean(imageUrl))
            .map(resolveApiAssetUrl)
        )
      ),
    [rewardCase.imageUrl, rewardCase.imageUrls]
  );
  const imageUrlsKey = imageUrls.join('|');
  const [imageIndex, setImageIndex] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const [hasFailed, setHasFailed] = useState(false);
  const [isReady, setIsReady] = useState(loadDelayMs === 0);
  const delayTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const loadTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const retryTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const imageUrl = imageUrls[imageIndex];
  const sourceUri =
    imageUrl && attempt > 0
      ? `${imageUrl}${imageUrl.includes('?') ? '&' : '?'}reward_watch_retry=${attempt}`
      : imageUrl;

  useEffect(() => {
    if (delayTimer.current) {
      clearTimeout(delayTimer.current);
      delayTimer.current = null;
    }
    if (loadTimer.current) {
      clearTimeout(loadTimer.current);
      loadTimer.current = null;
    }
    if (retryTimer.current) {
      clearTimeout(retryTimer.current);
      retryTimer.current = null;
    }

    setImageIndex(0);
    setAttempt(0);
    setHasFailed(false);
    setIsReady(loadDelayMs === 0);

    if (loadDelayMs > 0) {
      delayTimer.current = setTimeout(() => {
        delayTimer.current = null;
        setIsReady(true);
      }, loadDelayMs);
    }
  }, [imageUrlsKey, loadDelayMs]);

  useEffect(
    () => () => {
      if (delayTimer.current) {
        clearTimeout(delayTimer.current);
      }
      if (loadTimer.current) {
        clearTimeout(loadTimer.current);
      }
      if (retryTimer.current) {
        clearTimeout(retryTimer.current);
      }
    },
    []
  );

  function handleError() {
    if (loadTimer.current) {
      clearTimeout(loadTimer.current);
      loadTimer.current = null;
    }
    if (retryTimer.current) {
      return;
    }

    if (attempt < 3) {
      retryTimer.current = setTimeout(
        () => {
          retryTimer.current = null;
          setAttempt((current) => current + 1);
        },
        350 * 2 ** attempt
      );
      return;
    }

    if (imageIndex < imageUrls.length - 1) {
      setImageIndex((current) => current + 1);
      setAttempt(0);
      return;
    }

    setHasFailed(true);
  }

  if (!imageUrl || !sourceUri || hasFailed || !isReady) {
    return fallback;
  }

  return (
    <Image
      accessibilityLabel={`${rewardCase.title} official case image`}
      cachePolicy="memory-disk"
      contentFit={contentFit}
      key={`${imageUrl}-${attempt}`}
      onError={handleError}
      onLoad={() => {
        if (loadTimer.current) {
          clearTimeout(loadTimer.current);
          loadTimer.current = null;
        }
        if (retryTimer.current) {
          clearTimeout(retryTimer.current);
          retryTimer.current = null;
        }
      }}
      onLoadStart={() => {
        if (loadTimer.current) {
          clearTimeout(loadTimer.current);
        }
        loadTimer.current = setTimeout(handleError, 5000);
      }}
      recyclingKey={`${imageUrl}-${attempt}`}
      source={{ uri: sourceUri }}
      style={style}
      transition={attempt === 0 ? 120 : 0}
    />
  );
}
