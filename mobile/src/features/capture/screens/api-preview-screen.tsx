import { useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { AppState, Image, Text } from 'react-native';
import { useQueryClient } from '@tanstack/react-query';
import { currentActor, useActorId } from '@/features/social/api/session';
import {
  captureKeys,
  getSubmission,
  retrySubmission,
  uploadAndSubmit,
  type Submission,
} from '@/services/api/capture';
import { newKey } from '@/services/api/idempotency';
import { useCaptureStore } from '@/state/capture-store';
import { Page } from '@/shared/components/page';
import { Action } from '@/shared/components/action';
import { Note, Surface, commonStyles as c } from '@/shared/components/surface';

export function ApiPreviewScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const draft = useCaptureStore((state) => state.draft);
  const actor = useActorId();
  const queryClient = useQueryClient();
  const [result, setResult] = useState<Submission>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [waiting, setWaiting] = useState(false);
  const [foreground, setForeground] = useState(AppState.currentState === 'active');
  const request = useRef<AbortController | null>(null);
  const submissionId = result?.id ?? draft?.submissionId;
  const pending =
    (!result && !!submissionId) || result?.status === 'queued' || result?.status === 'running';

  useEffect(() => {
    const subscription = AppState.addEventListener('change', (state) =>
      setForeground(state === 'active'),
    );
    return () => {
      subscription.remove();
      request.current?.abort();
    };
  }, []);

  useEffect(() => {
    if (!pending || !submissionId || !actor || !foreground || waiting) return;
    const controller = new AbortController();
    const start = Date.now();
    let timer: ReturnType<typeof setTimeout>;
    async function poll(submission: string, owner: string) {
      try {
        const next = await getSubmission(submission, owner, controller.signal);
        if (controller.signal.aborted) return;
        setError('');
        setResult(next);
        if (next.status === 'succeeded' || next.status === 'failed') {
          if (next.discovery) {
            void queryClient.invalidateQueries({ queryKey: ['social', owner] });
            void queryClient.invalidateQueries({ queryKey: ['timeline', owner] });
          }
          return;
        }
      } catch (cause) {
        if (controller.signal.aborted) return;
        setError(cause instanceof Error ? cause.message : 'Chưa kiểm tra được kết quả.');
      }
      const elapsed = Date.now() - start;
      if (elapsed >= 120_000) setWaiting(true);
      else
        timer = setTimeout(
          () => void poll(submission, owner),
          elapsed < 10_000 ? 2000 : elapsed < 30_000 ? 3000 : 5000,
        );
    }
    void poll(submissionId, actor);
    return () => {
      controller.abort();
      clearTimeout(timer);
    };
  }, [actor, foreground, pending, queryClient, submissionId, waiting]);

  if (!draft || draft.id !== id || draft.ownerId !== actor)
    return (
      <Page title="Xem trước ảnh">
        <Note>Không còn ảnh chờ gửi.</Note>
        <Action label="Mở máy ảnh" href="/(main)/(tabs)/capture" />
      </Page>
    );

  async function send(retry: boolean) {
    if (!draft || !actor || request.current) return;
    const controller = new AbortController();
    request.current = controller;
    setBusy(true);
    setError('');
    try {
      const keys = draft.apiKeys ?? captureKeys();
      useCaptureStore.setState({ draft: { ...draft, apiKeys: keys } });
      const next =
        retry && submissionId
          ? await retrySubmission(submissionId, actor, keys.retry, controller.signal)
          : await uploadAndSubmit(draft, keys, controller.signal);
      if (controller.signal.aborted || currentActor() !== actor) return;
      useCaptureStore.setState({
        draft: {
          ...draft,
          submissionId: next.id,
          apiKeys: retry ? { ...keys, retry: newKey() } : keys,
        },
      });
      setWaiting(false);
      setResult(next);
    } catch (cause) {
      if (!controller.signal.aborted)
        setError(cause instanceof Error ? cause.message : 'Chưa gửi được ảnh. Hãy thử lại.');
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  function retake() {
    if (!draft || !actor) return;
    const continuation =
      result?.session_status === 'awaiting_evidence'
        ? {
            ownerId: actor,
            mode: draft.mode,
            missionId: draft.mission?.id ?? null,
            sessionId: draft.sessionId,
            evidence: [],
            serverSession: { id: result.evaluation_session_id, previous: result.id },
          }
        : null;
    useCaptureStore.setState({ draft: null, continuation });
    router.replace({
      pathname: '/(main)/capture/camera',
      params: { mode: draft.mode, ...(draft.mission ? { missionId: draft.mission.id } : {}) },
    });
  }

  return (
    <Page title={result?.discovery ? 'Khám phá đã lưu' : 'Xem trước ảnh'}>
      <Image
        source={{ uri: draft.photo.uri }}
        accessibilityLabel="Ảnh vừa chụp"
        style={{
          width: '100%',
          aspectRatio: draft.photo.width / draft.photo.height,
          borderRadius: 20,
        }}
      />
      {error ? <Note error>{error}</Note> : null}
      {!result && !submissionId ? (
        <Action label="Gửi đánh giá" loading={busy} onPress={() => void send(false)} />
      ) : null}
      {pending ? <Note>{waiting ? 'Vẫn đang xử lý.' : 'Đang đánh giá ảnh…'}</Note> : null}
      {pending && waiting ? (
        <Action label="Kiểm tra kết quả" onPress={() => setWaiting(false)} />
      ) : null}
      {result?.status === 'failed' ? (
        <Note error>{result.error?.message ?? 'Chưa đánh giá được ảnh.'}</Note>
      ) : null}
      {result?.status === 'failed' && result.error?.retryable ? (
        <Action label="Thử lại" loading={busy} onPress={() => void send(true)} />
      ) : null}
      {result?.discovery ? (
        <>
          <Surface>
            <Text style={c.title}>{result.discovery.name}</Text>
            <Text style={c.body}>{result.discovery.knowledge}</Text>
            <Note>Đã nhận {result.discovery.xp_awarded} XP</Note>
            {result.discovery.fragment_added ? (
              <Note>Đã thêm một mảnh vào dòng thời gian.</Note>
            ) : null}
          </Surface>
          <Action
            label="Chia sẻ khám phá"
            href={{
              pathname: '/(main)/posts/compose',
              params: { discoveryId: result.discovery.id },
            }}
          />
          <Action secondary label="Xem bộ sưu tập" href="/(main)/collection" />
        </>
      ) : null}
      {result?.instruction ? <Note>{result.instruction}</Note> : null}
      {!pending ? <Action secondary label="Chụp ảnh mới" disabled={busy} onPress={retake} /> : null}
    </Page>
  );
}
