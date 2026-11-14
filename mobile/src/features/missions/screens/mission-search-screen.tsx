import { useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { LocationInput } from '@/features/missions/components/location-input';
import { AppState, Pressable, StyleSheet, Text, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Page } from '@/shared/components/page';
import { Action } from '@/shared/components/action';
import { Surface, Note, commonStyles as c } from '@/shared/components/surface';
import { colors } from '@/shared/theme/tokens';
import { useQuery } from '@tanstack/react-query';
import { useActorId } from '@/features/social/api/session';
import { env } from '@/config/env';
import { getActiveMission } from '@/services/api/missions';
import { services } from '@/services';
import { useAppStore } from '@/state/app-store';
import type { Coordinates, MissionSearchStage } from '@/domain/models';

const stages: Record<MissionSearchStage, string> = {
  queued: 'Đang chờ xử lý…',
  evaluating: 'Đang đánh giá…',
  persisting: 'Đang lưu…',
  done: 'Đã xử lý',
  finding: 'Đang tìm mục tiêu quanh bạn…',
  reviewing: 'Đang chọn địa điểm phù hợp…',
  preparing: 'Đang chuẩn bị mật thư và gợi ý…',
};
export default function MissionSearchScreen() {
  const params = useLocalSearchParams<{ eraId?: string; replaceId?: string }>();
  const eraId = typeof params.eraId === 'string' ? params.eraId : undefined;
  const actor = useActorId();
  const { data: eras } = useQuery({
    queryKey: ['timeline', actor],
    queryFn: services.exploration.listEras,
  });
  const era = eras?.find((e) => e.id === eraId);
  const [locationSource, setLocationSource] = useState<'gps' | 'manual'>('gps');
  const cached = useAppStore((s) => s.activeMission);
  const activeQuery = useQuery({
    queryKey: ['mission', actor],
    queryFn: ({ signal }) => getActiveMission(signal),
    enabled: !!actor && env.dataSource === 'api',
  });
  const active = env.dataSource === 'api' ? activeQuery.data : cached;
  const [location, setLocation] = useState<Coordinates | null>(null);
  const [locationName, setLocationName] = useState('Chưa áp dụng vị trí tìm kiếm');
  const [radius, setRadius] = useState(1000);
  const [searching, setSearching] = useState(false);
  const [stage, setStage] = useState<MissionSearchStage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [empty, setEmpty] = useState(false);
  const locating = false;
  const request = useRef<AbortController | null>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    const listener = AppState.addEventListener('change', (state) => {
      if (state !== 'active') request.current?.abort();
    });
    return () => {
      listener.remove();
      mounted.current = false;
      request.current?.abort();
    };
  }, []);
  const busy = searching || locating;
  const invalidEra = !!eraId && !!eras && !era;
  const staleReplacement = !!params.replaceId && params.replaceId !== active?.id;
  async function find(nextRadius = radius) {
    if (request.current || !location || invalidEra || staleReplacement) return;
    const controller = new AbortController();
    request.current = controller;
    const expected = useAppStore.getState().activeMission?.id;
    setError(null);
    setEmpty(false);
    setSearching(true);
    try {
      const result = await services.missions.search(
        {
          location,
          locationSource,
          expectedActiveMissionId: active?.id ?? null,
          radiusMeters: nextRadius,
          eraId,
          excludePlaceId: params.replaceId ? active?.placeId : undefined,
        },
        controller.signal,
        setStage,
      );
      if (controller.signal.aborted || !mounted.current) return;
      if (result.status === 'no_suitable_place') {
        setEmpty(true);
        return;
      }
      if (env.dataSource !== 'api' && useAppStore.getState().activeMission?.id !== expected)
        throw new Error('Nhiệm vụ đang hoạt động đã thay đổi. Hãy quay về và kiểm tra lại.');
      useAppStore.getState().setMission(result.mission);
      router.replace({ pathname: '/(main)/missions/[id]', params: { id: result.mission.id } });
    } catch (e) {
      if (!controller.signal.aborted && mounted.current)
        setError(e instanceof Error ? e.message : 'Chưa thể tìm nhiệm vụ. Hãy thử lại.');
    } finally {
      request.current = null;
      if (mounted.current) {
        setStage(null);
        setSearching(false);
      }
    }
  }
  return (
    <Page title={params.replaceId ? 'Đổi nhiệm vụ' : 'Tìm nhiệm vụ'}>
      {invalidEra || staleReplacement ? (
        <>
          <Note error>
            {invalidEra
              ? 'Thời kỳ này không có trong danh sách hiện tại.'
              : 'Nhiệm vụ cần thay đã thay đổi hoặc không còn hoạt động.'}
          </Note>
          <Action label="Về Khám phá" href="/(main)/(tabs)" />
        </>
      ) : (
        <>
          <Surface>
            <View style={c.row}>
              <Text style={c.title}>{era?.name ?? 'Mọi thời kỳ'}</Text>
            </View>
            <Note>
              {era
                ? 'Giữ nguyên thời kỳ bạn đã chọn trong suốt lượt tìm.'
                : 'Địa điểm tìm được sẽ quyết định thời kỳ. Không giới hạn theo node trên trang chủ.'}
            </Note>
          </Surface>
          <View style={styles.section}>
            <Text style={c.title}>Vị trí tìm kiếm</Text>
            <View style={styles.location}>
              <Ionicons name="location-outline" size={22} color={colors.accent} />
              <Text style={[c.body, styles.flex]}>{locationName}</Text>
            </View>
            <LocationInput
              disabled={busy}
              onChange={(point, label, source) => {
                setLocationSource(source);
                setLocation(point);
                setLocationName(label);
                setEmpty(false);
                setError(null);
              }}
            />
          </View>
          <View style={styles.section}>
            <Text style={c.title}>Phạm vi quanh bạn</Text>
            <View style={styles.options}>
              {[1000, 3000, 5000].map((value) => (
                <Pressable
                  key={value}
                  accessibilityRole="button"
                  accessibilityLabel={`Bán kính ${value / 1000} km`}
                  accessibilityState={{ selected: radius === value, disabled: busy }}
                  disabled={busy}
                  onPress={() => {
                    setRadius(value);
                    setEmpty(false);
                  }}
                  style={[styles.option, radius === value && styles.selected]}
                >
                  <Text style={[c.body, radius === value && styles.selectedText]}>
                    {value / 1000} km
                  </Text>
                </Pressable>
              ))}
            </View>
          </View>
          {active && (
            <Note>Nhiệm vụ “{active.placeName}” vẫn được giữ cho đến khi có nhiệm vụ mới.</Note>
          )}
          {searching && !stage ? <Note>Đang gửi yêu cầu tìm kiếm…</Note> : null}
          {stage && (
            <Surface>
              <Text accessibilityLiveRegion="polite" style={c.title}>
                {stages[stage]}
              </Text>
              <Note>Bạn có thể quay lại để dừng lượt tìm.</Note>
            </Surface>
          )}
          {activeQuery.error ? (
            <>
              <Note error>Chưa xác nhận được nhiệm vụ đang hoạt động từ server.</Note>
              <Action
                secondary
                label="Tải lại nhiệm vụ đang hoạt động"
                onPress={() => void activeQuery.refetch()}
              />
            </>
          ) : null}
          {error && <Note error>{error}</Note>}
          {empty && (
            <Surface>
              <Text style={c.title}>Chưa có nhiệm vụ phù hợp</Text>
              <Note>
                Thử phạm vi rộng hơn hoặc tìm ở thời kỳ khác. Nhiệm vụ hiện tại của bạn không bị
                thay đổi.
              </Note>
              {radius < 5000 && (
                <Action
                  secondary
                  label="Tìm rộng hơn"
                  onPress={() => {
                    const next = radius === 1000 ? 3000 : 5000;
                    setRadius(next);
                    void find(next);
                  }}
                />
              )}
              {eraId && (
                <Action secondary label="Tìm ở mọi thời kỳ" href="/(main)/missions/search" />
              )}
            </Surface>
          )}
          <Action
            label={stage ? 'Đang tìm nhiệm vụ…' : error ? 'Thử tìm lại' : 'Tìm nhiệm vụ tại đây'}
            loading={searching}
            disabled={
              busy ||
              !location ||
              (env.dataSource === 'api' && (activeQuery.isPending || !!activeQuery.error))
            }
            onPress={() => void find()}
          />
          {active && (
            <Action
              secondary
              disabled={busy}
              label="Tiếp tục nhiệm vụ hiện tại"
              href={{ pathname: '/(main)/missions/[id]', params: { id: active.id } }}
            />
          )}
          <Action
            secondary
            disabled={busy}
            label="Chụp khám phá tự do"
            href={{ pathname: '/(main)/capture/camera', params: { mode: 'free' } }}
          />
        </>
      )}
    </Page>
  );
}
const styles = StyleSheet.create({
  section: { gap: 12 },
  location: { flexDirection: 'row', alignItems: 'center', gap: 10 },
  flex: { flex: 1 },
  reward: { fontSize: 14, lineHeight: 22, color: colors.accent },
  options: { flexDirection: 'row', gap: 10 },
  option: {
    flex: 1,
    paddingVertical: 14,
    alignItems: 'center',
    borderRadius: 12,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  selected: { backgroundColor: colors.accent, borderColor: colors.accent },
  selectedText: { color: colors.background, fontWeight: '600' },
  debug: { minHeight: 44, justifyContent: 'center' },
});
