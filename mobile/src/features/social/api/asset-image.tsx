import { useEffect, useState } from 'react';
import { AppState } from 'react-native';
import { useIsFocused } from 'expo-router';
import { Image } from 'expo-image';
import { assetUrl } from '@/services/api/social';
import { useSocialQuery, useRefreshOnFocus } from './hooks';
import { QueryView } from './components';
export function AssetImage({ id, postId }: { id: string; postId?: string }) {
  const path = `/assets/${id}/url${postId ? `?post_id=${postId}` : ''}`;
  const url = useSocialQuery(path, assetUrl);
  const focused = useIsFocused();
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const [expired, setExpired] = useState<string>();
  const { data, refetch } = url;
  useRefreshOnFocus(refetch);

  useEffect(() => {
    const listener = AppState.addEventListener('change', (state) =>
      setForeground(state === 'active'),
    );
    return () => listener.remove();
  }, []);
  useEffect(() => {
    if (!data || !foreground || !focused) return;
    const remaining = Date.parse(data.expires_at) - Date.now();
    const timer = setTimeout(
      () => {
        setExpired(data.url);
        void refetch();
      },
      Math.max(remaining, 0),
    );
    return () => clearTimeout(timer);
  }, [data, foreground, focused, refetch]);

  return (
    <QueryView query={url}>
      {data && data.url !== expired && (
        <Image
          accessibilityLabel="Ảnh khám phá"
          source={data.url}
          cachePolicy="none"
          contentFit="cover"
          style={{ aspectRatio: 4 / 3, width: '100%', borderRadius: 14 }}
        />
      )}
    </QueryView>
  );
}
