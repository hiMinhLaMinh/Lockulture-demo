import { useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Linking, Platform, StyleSheet, Text, View } from 'react-native';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Page } from '@/shared/components/page';
import { Action } from '@/shared/components/action';
import { Surface, Note, commonStyles as c } from '@/shared/components/surface';
import { ConfirmSheet } from '@/shared/components/confirm-sheet';
import { colors } from '@/shared/theme/tokens';
import { currentActor } from '@/features/social/api/session';
import { env } from '@/config/env';
import { getMission, revealMission } from '@/services/api/missions';
import { newKey } from '@/services/api/idempotency';
import { useAppStore } from '@/state/app-store';
export default function MissionDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const mission = useAppStore((s) => s.activeMission);
  const revealHint = useAppStore((s) => s.revealHint);
  const revealAnswer = useAppStore((s) => s.revealAnswer);
  const [reload, setReload] = useState(0);
  const [loadedId, setLoadedId] = useState<string | null>(null);
  const loaded = env.dataSource !== 'api' || loadedId === id;
  const [apiError, setApiError] = useState('');
  const [busy, setBusy] = useState(false);
  const pending = useRef<{
    answer: boolean;
    key: string;
    mission: NonNullable<typeof mission>;
  } | null>(null);
  useEffect(() => {
    if (env.dataSource !== 'api' || !id) return;
    const controller = new AbortController();
    void getMission(id, controller.signal)
      .then((m) => {
        if (!controller.signal.aborted) {
          useAppStore.getState().setMission(m);
          setApiError('');
          setLoadedId(id);
        }
      })
      .catch(() => {
        if (!controller.signal.aborted)
          setApiError('Không tải được nhiệm vụ từ server. Hãy mở lại trang.');
      });
    return () => controller.abort();
  }, [id, reload]);
  async function reveal(answer: boolean) {
    if (!mission || busy) return;
    if (env.dataSource !== 'api') {
      if (answer) revealAnswer(mission.id);
      else revealHint(mission.id);
      return;
    }
    if (!pending.current || pending.current.answer !== answer)
      pending.current = { answer, key: newKey(), mission };
    const attempt = pending.current;
    const actor = currentActor();
    setBusy(true);
    setApiError('');
    try {
      const updated = await revealMission(attempt.mission, answer, attempt.key);
      if (actor !== currentActor()) return;
      useAppStore.getState().setMission(updated);
      pending.current = null;
    } catch {
      setApiError('Chưa mở được gợi ý/đáp án. Thử lại để kiểm tra cùng yêu cầu.');
    } finally {
      setBusy(false);
    }
  }
  const [confirm, setConfirm] = useState(false);
  const [mapError, setMapError] = useState(false);
  if (env.dataSource === 'api' && !loaded)
    return (
      <Page title="Nhiệm vụ">
        <Note error={!!apiError}>{apiError || 'Đang tải nhiệm vụ từ server…'}</Note>
        {apiError ? (
          <Action
            secondary
            label="Tải lại nhiệm vụ"
            onPress={() => setReload((value) => value + 1)}
          />
        ) : null}
      </Page>
    );
  if (!mission || mission.id !== id)
    return (
      <Page title="Nhiệm vụ">
        <Note>
          {apiError}
          Nhiệm vụ này không còn hoạt động. Hãy mở nhiệm vụ hiện tại hoặc tìm một mục tiêu mới.
        </Note>
        {mission && (
          <Action
            label="Mở nhiệm vụ hiện tại"
            href={{ pathname: '/(main)/missions/[id]', params: { id: mission.id } }}
          />
        )}
        <Action secondary label="Về Khám phá" href="/(main)/(tabs)" />
      </Page>
    );
  const m = mission;
  async function openMap() {
    setMapError(false);
    try {
      await Linking.openURL(
        `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${m.location.latitude},${m.location.longitude}`)}&query_place_id=${encodeURIComponent(m.placeId)}`,
      );
    } catch {
      setMapError(true);
    }
  }
  return (
    <Page title="Nhiệm vụ của bạn" subtitle={m.eraName}>
      {apiError ? <Note error>{apiError}</Note> : null}
      <Note>Bán kính đến nơi: {m.arrivalRadiusM} m. Cần GPS mới và ảnh đúng địa điểm.</Note>
      <View style={c.row}>
        <View style={styles.meta}>
          <Ionicons name="location-outline" size={18} color={colors.accent} />
          <Text style={c.body}>
            {m.distanceMeters < 1000
              ? `${m.distanceMeters} m`
              : `${(m.distanceMeters / 1000).toFixed(1)} km`}{' '}
            quanh vị trí tìm
          </Text>
        </View>
        <Text style={styles.reward}>Thưởng {m.xp} XP</Text>
      </View>
      <Surface>
        <Text style={styles.clueTitle}>Mật thư</Text>
        <Text style={styles.clue}>{m.clue}</Text>
        <Note>Tìm địa điểm và chụp bằng chứng để góp một mảnh ghép cho thời kỳ này.</Note>
      </Surface>
      <View style={styles.section}>
        <Text style={c.title}>Bạn cần chụp gì?</Text>
        {m.photoRequirements.map((line) => (
          <View style={styles.requirement} key={line}>
            <Ionicons name="camera-outline" size={18} color={colors.accent} />
            <Text style={[c.body, styles.flex]}>{line}</Text>
          </View>
        ))}
      </View>
      <View style={styles.section}>
        {m.hints.slice(0, m.revealedHints).map((hint, i) => (
          <Surface key={hint}>
            <Text style={c.title}>Gợi ý {i + 1}</Text>
            <Text style={c.body}>{hint}</Text>
          </Surface>
        ))}
        <Action
          secondary
          disabled={!loaded || busy || m.revealedHints >= m.hints.length}
          label={
            m.revealedHints >= m.hints.length
              ? 'Đã mở hết gợi ý'
              : `Gợi ý thêm (${m.revealedHints}/${m.hints.length})`
          }
          onPress={() => void reveal(false)}
        />
      </View>
      {!m.answerRevealed ? (
        <Action
          secondary
          label="Xem đáp án và đường đi"
          disabled={!loaded || busy}
          onPress={() => void reveal(true)}
        />
      ) : (
        <Surface>
          <Text style={c.title}>{m.placeName}</Text>
          <Text style={c.body}>{m.address}</Text>
          <Action secondary label="Mở Google Maps" onPress={() => void openMap()} />
          {mapError && (
            <Note error>
              Chưa mở được bản đồ. Bạn có thể tìm địa chỉ trên bằng ứng dụng bản đồ.
            </Note>
          )}
        </Surface>
      )}
      <Action
        label="Chụp hoàn thành"
        disabled={
          !loaded || busy || !!apiError || (env.dataSource === 'api' && m.status !== 'active')
        }
        href={{ pathname: '/(main)/capture/camera', params: { mode: 'mission', missionId: m.id } }}
      />
      <Action secondary label="Đổi nhiệm vụ" onPress={() => setConfirm(true)} />
      <ConfirmSheet
        visible={confirm}
        onCancel={() => setConfirm(false)}
        onConfirm={() => {
          setConfirm(false);
          router.push({
            pathname: '/(main)/missions/search',
            params: { eraId: m.eraId, replaceId: m.id },
          });
        }}
      />
    </Page>
  );
}
const styles = StyleSheet.create({
  section: { gap: 14 },
  meta: { flexDirection: 'row', alignItems: 'center', gap: 8, flexShrink: 1 },
  reward: { color: colors.accent, fontSize: 14, lineHeight: 22 },
  clueTitle: {
    color: colors.accent,
    fontSize: 24,
    fontFamily: Platform.select({ ios: 'Georgia', android: 'serif', web: 'Georgia' }),
  },
  clue: { color: colors.text, fontSize: 19, lineHeight: 31 },
  requirement: { flexDirection: 'row', gap: 12, alignItems: 'flex-start' },
  flex: { flex: 1 },
});
