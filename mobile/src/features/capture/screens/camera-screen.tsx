import { useEffect, useRef, useState } from 'react';
import { AppState, Linking, Platform, Pressable, StyleSheet, Text, View } from 'react-native';
import { CameraView, useCameraPermissions } from 'expo-camera';
import { router, useIsFocused, useLocalSearchParams } from 'expo-router';
import Ionicons from '@expo/vector-icons/Ionicons';
import { Page } from '@/shared/components/page';
import { Action } from '@/shared/components/action';
import { Note, Surface, commonStyles as c } from '@/shared/components/surface';
import { colors } from '@/shared/theme/tokens';
import { useAppStore } from '@/state/app-store';
import { useCaptureStore } from '@/state/capture-store';
import { captureLocation } from '@/features/capture/lib/location';
import { preparePhoto } from '@/features/capture/lib/photo';
import { env } from '@/config/env';
import { currentActor, useActorId } from '@/features/social/api/session';
export default function CameraScreen() {
  const {
    mode: rawMode,
    missionId,
    purpose,
  } = useLocalSearchParams<{
    mode?: string;
    missionId?: string;
    purpose?: string;
  }>();
  const portrait = purpose === 'portrait';
  const parentDraft = useCaptureStore((s) => s.draft);
  const mode = rawMode === 'mission' ? 'mission' : 'free';
  const mockUser = useAppStore((s) => s.mockUser);
  const actor = useActorId();
  const owner = env.dataSource === 'api' ? actor : mockUser?.id;
  const mission = useAppStore((s) => s.activeMission);
  const records = useCaptureStore((s) => s.records);
  const valid =
    (portrait &&
      !!parentDraft?.souvenirOptIn &&
      !parentDraft.apiKeys &&
      parentDraft.ownerId === owner) ||
    (!portrait && mode === 'free') ||
    (!!mission &&
      mission.id === missionId &&
      (env.dataSource === 'api'
        ? mission.status === 'active'
        : !records.some(
            (r) => r.ownerId === owner && r.missionId === mission.id && r.verdict === 'completed',
          )));
  const [permission, requestPermission, refreshPermission] = useCameraPermissions();
  const camera = useRef<CameraView>(null);
  const focused = useIsFocused();
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const [cameraVersion, setCameraVersion] = useState(0);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [torch, setTorch] = useState(false);
  const [facing, setFacing] = useState<'back' | 'front'>('back');
  const lock = useRef(false);
  const mounted = useRef(true);
  const focusRef = useRef(focused);
  useEffect(() => {
    focusRef.current = focused;
  }, [focused]);
  useEffect(() => {
    mounted.current = true;
    const sub = AppState.addEventListener('change', (state) => {
      setForeground(state === 'active');
      if (state === 'active') void refreshPermission().catch(() => {});
      setReady(false);
    });
    return () => {
      mounted.current = false;
      sub.remove();
    };
  }, [refreshPermission]);

  async function shoot() {
    if (lock.current || !ready || !focused || !foreground || !camera.current || !owner) return;
    lock.current = true;
    setBusy(true);
    setError('');
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.85 });
      const saved = await preparePhoto(photo);
      if (
        !mounted.current ||
        !focusRef.current ||
        (env.dataSource === 'api' ? currentActor() : useAppStore.getState().mockUser?.id) !== owner
      )
        return;
      if (portrait) {
        const original = useCaptureStore.getState().draft;
        if (!original || original.ownerId !== owner || !original.souvenirOptIn || original.apiKeys)
          throw new Error('Phiên ảnh đã thay đổi.');
        useCaptureStore.setState({ draft: { ...original, portraitPhoto: saved } });
        router.back();
        return;
      }
      if (mode === 'mission' && useAppStore.getState().activeMission?.id !== missionId)
        throw new Error('Nhiệm vụ đã thay đổi. Hãy mở lại camera từ nhiệm vụ hiện tại.');
      const draft = useCaptureStore
        .getState()
        .start(saved, owner, mode, mode === 'mission' ? mission : null);
      if (env.dataSource === 'api' && mode === 'mission') {
        try {
          const location = await captureLocation();
          if (!mounted.current || !focusRef.current || currentActor() !== owner) return;
          useCaptureStore.setState({ draft: { ...draft, captureLocation: location } });
        } catch (cause) {
          setError(cause instanceof Error ? cause.message : 'Chưa lấy được GPS.');
        }
      }
      if (
        !mounted.current ||
        !focusRef.current ||
        (env.dataSource === 'api' && currentActor() !== owner)
      )
        return;
      router.push({ pathname: '/(main)/capture/preview', params: { id: draft.id } });
    } catch {
      if (mounted.current) setError('Chưa chụp hoặc lưu được ảnh. Kiểm tra camera và thử lại.');
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <Page
      title={
        portrait
          ? 'Ảnh chân dung cho ảnh quà'
          : mode === 'mission'
            ? 'Chụp nhiệm vụ'
            : 'Chụp khám phá'
      }
    >
      {!valid ? (
        <>
          <Note error>Nhiệm vụ không còn hoạt động hoặc đã hoàn thành.</Note>
          <Action label="Về Khám phá" href="/(main)/(tabs)" />
        </>
      ) : (
        <>
          {portrait ? (
            <Note>
              Chụp rõ chính bạn. Ảnh này chỉ dùng cho ảnh hoạt hoạ bạn đã đồng ý; không thay bằng
              chứng địa điểm.
            </Note>
          ) : null}
          {!portrait && mode === 'free' && (
            <Note>
              Đặt biển tên đường, món ăn hoặc đồ vật trong khung. Giữ máy ổn định để thấy rõ chi
              tiết.
            </Note>
          )}
          {!permission ? (
            <Note>Đang kiểm tra quyền camera…</Note>
          ) : !permission.granted ? (
            <Surface>
              <Ionicons name="camera-outline" size={40} color={colors.accent} />
              <Text style={c.title}>Cho phép sử dụng camera</Text>
              <Note>
                Quyền camera chỉ phục vụ chụp ảnh khám phá. Nhiệm vụ cần thêm quyền vị trí để xác
                minh đến nơi.
              </Note>
              <Action
                label={permission.canAskAgain ? 'Cho phép camera' : 'Mở cài đặt camera'}
                onPress={() => {
                  setError('');
                  void (
                    permission.canAskAgain ? requestPermission() : Linking.openSettings()
                  ).catch(() => setError('Hãy mở cài đặt thiết bị để cấp quyền camera.'));
                }}
              />
            </Surface>
          ) : (
            <>
              <View style={styles.frame}>
                {focused && foreground && (
                  <CameraView
                    key={cameraVersion}
                    ref={camera}
                    style={StyleSheet.absoluteFill}
                    facing={facing}
                    enableTorch={torch && facing === 'back' && Platform.OS !== 'web'}
                    onCameraReady={() => {
                      setReady(true);
                      setError('');
                    }}
                    onMountError={() => {
                      setReady(false);
                      setError(
                        'Không mở được camera. Hãy kiểm tra quyền hoặc đóng ứng dụng đang dùng camera rồi thử lại.',
                      );
                    }}
                  />
                )}
                <View pointerEvents="none" style={styles.guide} />
              </View>
              <View style={styles.controls}>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel={
                    Platform.OS === 'web' || facing === 'front'
                      ? 'Đèn không hỗ trợ'
                      : torch
                        ? 'Tắt đèn'
                        : 'Bật đèn'
                  }
                  accessibilityState={{
                    disabled: busy || facing === 'front' || Platform.OS === 'web',
                    selected: torch,
                  }}
                  disabled={busy || facing === 'front' || Platform.OS === 'web'}
                  onPress={() => setTorch(!torch)}
                  style={({ pressed }) => [
                    styles.cameraControl,
                    (pressed || busy || facing === 'front' || Platform.OS === 'web') && styles.dim,
                  ]}
                >
                  <Ionicons
                    name={torch ? 'flash' : 'flash-off-outline'}
                    size={26}
                    color={
                      facing === 'front' || Platform.OS === 'web'
                        ? '#929B9B'
                        : torch
                          ? colors.accent
                          : colors.text
                    }
                  />
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Chụp ảnh"
                  accessibilityState={{ disabled: !ready || busy, busy }}
                  disabled={!ready || busy}
                  onPress={() => void shoot()}
                  style={[styles.shutter, (!ready || busy) && { opacity: 0.45 }]}
                >
                  <View style={styles.shutterInner} />
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  accessibilityLabel="Đổi camera"
                  accessibilityState={{ disabled: busy }}
                  disabled={busy}
                  style={({ pressed }) => [styles.cameraControl, (pressed || busy) && styles.dim]}
                  onPress={() => {
                    setReady(false);
                    setFacing(facing === 'back' ? 'front' : 'back');
                    setTorch(false);
                  }}
                >
                  <Ionicons name="sync-outline" size={28} color={colors.text} />
                </Pressable>
              </View>
              <Text style={[c.label, { textAlign: 'center' }]}>
                {busy ? 'Đang lưu ảnh…' : 'Ảnh chưa được gửi để đánh giá'}
              </Text>
            </>
          )}
          {!!error && (
            <>
              <Note error>{error}</Note>
              {permission?.granted && (
                <Action
                  secondary
                  label="Thử mở lại camera"
                  onPress={() => {
                    setReady(false);
                    setError('');
                    setCameraVersion((v) => v + 1);
                  }}
                />
              )}
            </>
          )}
          {mode === 'mission' && mission ? (
            <Surface>
              <Text style={c.title}>{mission.eraName}</Text>
              {mission.photoRequirements.map((line) => (
                <Text key={line} style={c.body}>
                  {line}
                </Text>
              ))}
              <Action
                secondary
                label="Xem nhiệm vụ"
                href={{ pathname: '/(main)/missions/[id]', params: { id: mission.id } }}
              />
            </Surface>
          ) : null}
        </>
      )}
    </Page>
  );
}
const styles = StyleSheet.create({
  controls: {
    width: '100%',
    paddingHorizontal: '12.5%',
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  cameraControl: {
    width: 56,
    height: 56,
    borderRadius: 28,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    alignItems: 'center',
    justifyContent: 'center',
  },
  dim: { opacity: 0.45 },
  frame: {
    width: '100%',
    aspectRatio: 1,
    borderRadius: 24,
    overflow: 'hidden',
    backgroundColor: colors.surface,
  },
  guide: {
    position: 'absolute',
    inset: 18,
    borderWidth: 1,
    borderColor: '#FFFFFF55',
    borderRadius: 16,
  },
  shutter: {
    height: 78,
    width: 78,
    borderRadius: 39,
    borderWidth: 2,
    borderColor: colors.accent,
    alignSelf: 'center',
    alignItems: 'center',
    justifyContent: 'center',
  },
  shutterInner: { width: 62, height: 62, borderRadius: 31, backgroundColor: colors.accent },
});
