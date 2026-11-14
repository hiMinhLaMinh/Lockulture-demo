import { useEffect, useState } from 'react';
import { AccessibilityInfo, Animated, AppState, Linking, Text } from 'react-native';
import { useIsFocused } from 'expo-router';
import { useSocialQuery, useRefreshOnFocus } from '@/features/social/api/hooks';
import { celebration } from '@/services/api/celebration';
import { Action } from '@/shared/components/action';
import { Note, Surface, commonStyles as c } from '@/shared/components/surface';
import { AssetImage } from '@/features/social/api/asset-image';

const statuses = {
  not_requested: 'Chưa yêu cầu ảnh hoạt hoạ.',
  queued: 'Ảnh hoạt hoạ đang chờ xử lý…',
  running: 'Đang tạo ảnh hoạt hoạ…',
  succeeded: 'Ảnh hoạt hoạ đã sẵn sàng.',
  failed: 'Không tạo được ảnh hoạt hoạ.',
};
export function Celebration({
  discoveryId,
  animate = false,
}: {
  discoveryId: string;
  animate?: boolean;
}) {
  const query = useSocialQuery(`/discoveries/${discoveryId}/celebration`, celebration);
  const focused = useIsFocused();
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const [linkError, setLinkError] = useState('');
  const [scale] = useState(() => new Animated.Value(1));
  const { data, refetch } = query;
  const hasData = !!data;
  useRefreshOnFocus(refetch);
  useEffect(() => {
    const listener = AppState.addEventListener('change', (state) =>
      setForeground(state === 'active'),
    );
    return () => listener.remove();
  }, []);
  useEffect(() => {
    if (!hasData || !animate) return;
    let active = true;
    let animation: Animated.CompositeAnimation | undefined;
    void AccessibilityInfo.isReduceMotionEnabled().then((reduce) => {
      if (!active || reduce) return;
      scale.setValue(0.85);
      animation = Animated.spring(scale, { toValue: 1, useNativeDriver: true, friction: 6 });
      animation.start();
    });
    const listener = AccessibilityInfo.addEventListener('reduceMotionChanged', (reduce) => {
      if (reduce) {
        animation?.stop();
        scale.setValue(1);
      }
    });
    return () => {
      active = false;
      animation?.stop();
      listener.remove();
    };
  }, [hasData, animate, scale]);
  useEffect(() => {
    if (!foreground || !focused || !data || !['queued', 'running'].includes(data.souvenir.status))
      return;
    const timer = setTimeout(() => void refetch(), 3000);
    return () => clearTimeout(timer);
  }, [data, query.dataUpdatedAt, foreground, focused, refetch]);
  if (!data)
    return (
      <Surface>
        <Note error={!!query.error}>
          {query.error
            ? 'Chưa tải được phần thưởng từ server. Nhiệm vụ đã lưu vẫn được giữ.'
            : 'Đang tải huy hiệu và kiến thức…'}
        </Note>
        {query.error ? (
          <Action secondary label="Tải lại phần thưởng" onPress={() => void refetch()} />
        ) : null}
      </Surface>
    );
  return (
    <>
      <Animated.View style={{ transform: [{ scale }] }}>
        <Surface>
          <Text accessibilityRole="header" style={c.title}>
            Chúc mừng hoàn thành nhiệm vụ!
          </Text>
          <Text style={c.title}>✦ {data.badge.title} ✦</Text>
          <Text style={c.body}>{data.badge.motif}</Text>
          <Note>Thời kỳ: {data.badge.era_id}</Note>
        </Surface>
      </Animated.View>
      <Surface>
        <Text style={c.title}>Câu chuyện địa danh</Text>
        <Text style={c.body}>{data.heritage.summary}</Text>
        <Note>Thời kỳ: {data.heritage.era_id}</Note>
        {data.heritage.fun_facts.map((fact, i) => (
          <Text key={i} style={c.body}>
            {fact}
          </Text>
        ))}
        {data.heritage.sources.map((source, i) => (
          <Action
            key={i}
            secondary
            label={source.title}
            onPress={() => {
              if (!/^https?:\/\//i.test(source.url)) {
                setLinkError('Nguồn không có liên kết web hợp lệ.');
                return;
              }
              void Linking.openURL(source.url).catch(() =>
                setLinkError('Chưa mở được nguồn. Hãy thử lại.'),
              );
            }}
          />
        ))}
        {linkError ? <Note error>{linkError}</Note> : null}
      </Surface>
      <Surface>
        <Text style={c.title}>Ảnh hoạt hoạ của bạn</Text>
        <Note error={data.souvenir.status === 'failed'}>{statuses[data.souvenir.status]}</Note>
        {data.souvenir.error ? <Note error>{data.souvenir.error.message}</Note> : null}
        {query.error ? (
          <Note error>Chưa cập nhật được trạng thái ảnh. Hãy kiểm tra lại.</Note>
        ) : null}
        {data.souvenir.status === 'succeeded' && data.souvenir.asset_id ? (
          <>
            <AssetImage id={data.souvenir.asset_id} />
            <Note>Ảnh minh hoạ do AI tạo.</Note>
          </>
        ) : null}
        <Action
          secondary
          label="Kiểm tra ảnh quà"
          loading={query.isFetching}
          onPress={() => void refetch()}
        />
      </Surface>
    </>
  );
}
