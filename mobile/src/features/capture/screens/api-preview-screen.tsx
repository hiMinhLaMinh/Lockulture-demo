import { useEffect, useRef, useState } from 'react';
import { router, useLocalSearchParams } from 'expo-router';
import { Alert, AppState, Image, Text } from 'react-native';
import { useQueryClient } from '@tanstack/react-query';
import { currentActor, useActorId } from '@/features/social/api/session';
import {
  captureKeys,
  getSubmission,
  retrySubmission,
  uploadAndSubmit,
  type Submission,
} from '@/services/api/capture';
import { captureLocation } from '@/features/capture/lib/location';
import { Celebration } from '@/features/missions/components/celebration';
import { ApiError } from '@/services/api/client';
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
  const [intakeRejected, setIntakeRejected] = useState(false);
  const [locationBusy, setLocationBusy] = useState(false);
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
            void queryClient.invalidateQueries({ queryKey: ['mission', owner] });
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

  const discoveryId = result?.discovery?.id;
  useEffect(() => {
    if (!discoveryId || !actor) return;
    void queryClient.invalidateQueries({ queryKey: ['social', actor] });
    void queryClient.invalidateQueries({ queryKey: ['timeline', actor] });
    void queryClient.invalidateQueries({ queryKey: ['mission', actor] });
  }, [discoveryId, actor, queryClient]);

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
      let frozenDraft = draft;
      if (draft.mode === 'mission' && !draft.apiKeys) {
        const location = await captureLocation();
        frozenDraft = { ...draft, captureLocation: location };
      }
      if (controller.signal.aborted || currentActor() !== actor) return;
      const keys = frozenDraft.apiKeys ?? captureKeys();
      frozenDraft = {
        ...frozenDraft,
        apiKeys: keys,
        souvenirOptIn: frozenDraft.souvenirOptIn ?? false,
      };
      useCaptureStore.setState({ draft: frozenDraft });
      const next =
        retry && submissionId
          ? await retrySubmission(submissionId, actor, keys.retry, controller.signal)
          : await uploadAndSubmit(frozenDraft, keys, controller.signal);
      if (controller.signal.aborted || currentActor() !== actor) return;
      useCaptureStore.setState({
        draft: {
          ...frozenDraft,
          submissionId: next.id,
          apiKeys: retry ? { ...keys, retry: newKey() } : keys,
        },
      });
      setWaiting(false);
      setResult(next);
    } catch (cause) {
      if (
        cause instanceof ApiError &&
        (cause.status === 422 || cause.code === 'location_out_of_range')
      ) {
        setIntakeRejected(true);
        setError(
          cause.code === 'location_out_of_range'
            ? 'Bạn đang ngoài bán kính nhiệm vụ. Hãy tới gần địa điểm rồi lấy lại GPS.'
            : 'Vị trí hoặc dữ liệu chưa hợp lệ. Hãy kiểm tra quyền, ra nơi thoáng và lấy lại GPS.',
        );
      } else if (!controller.signal.aborted)
        setError(cause instanceof Error ? cause.message : 'Chưa gửi được ảnh. Hãy thử lại.');
    } finally {
      request.current = null;
      if (!controller.signal.aborted) setBusy(false);
    }
  }

  async function refreshLocation() {
    if (!draft || draft.submissionId || locationBusy) return;
    setLocationBusy(true);
    try {
      const location = await captureLocation();
      if (currentActor() !== actor) return;
      useCaptureStore.setState({
        draft: { ...draft, captureLocation: location, apiKeys: undefined },
      });
      setIntakeRejected(false);
      setError('');
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : 'Chưa lấy được GPS.');
    } finally {
      setLocationBusy(false);
    }
  }
  function consent() {
    if (!draft || draft.apiKeys) return;
    Alert.alert(
      'Đồng ý tạo ảnh hoạt hoạ?',
      'Ảnh bằng chứng (và chân dung nếu có) sẽ được gửi tới dịch vụ AI để tạo ảnh minh hoạ tại địa danh, lưu riêng tư. Chỉ dùng ảnh có bạn và được phép. Ảnh lỗi không thay đổi kết quả nhiệm vụ.',
      [
        { text: 'Huỷ', style: 'cancel' },
        {
          text: 'Tôi đồng ý',
          onPress: () => {
            if (currentActor() !== actor || useCaptureStore.getState().draft?.id !== draft.id)
              return;
            useCaptureStore.setState({ draft: { ...draft, souvenirOptIn: true } });
          },
        },
      ],
    );
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
      {!result && !submissionId && draft.mode === 'mission' ? (
        <Surface>
          <Note>
            {draft.captureLocation
              ? `Độ chính xác GPS: ${Math.round(draft.captureLocation.accuracy_m)} m. Server sẽ kiểm tra khoảng cách.`
              : 'Chưa có vị trí GPS hợp lệ. Sẽ xin quyền và lấy vị trí mới khi gửi.'}
          </Note>
          <Note>
            {draft.souvenirOptIn
              ? 'Đã đồng ý tạo ảnh hoạt hoạ từ ảnh của bạn.'
              : 'Ảnh hoạt hoạ là tuỳ chọn, cần bạn đồng ý trước khi gửi ảnh cho AI.'}
          </Note>
          <Action
            secondary
            label="Tạo ảnh hoạt hoạ"
            disabled={!!draft.apiKeys || busy}
            onPress={consent}
          />
          {draft.souvenirOptIn && !draft.apiKeys ? (
            <Action
              secondary
              label={
                draft.portraitPhoto
                  ? 'Chụp lại chân dung cho ảnh quà'
                  : 'Ảnh cảnh không có bạn? Chụp thêm chân dung'
              }
              onPress={() =>
                router.push({ pathname: '/(main)/capture/camera', params: { purpose: 'portrait' } })
              }
            />
          ) : null}
          {draft.portraitPhoto ? (
            <Image
              source={{ uri: draft.portraitPhoto.uri }}
              accessibilityLabel="Chân dung đã đồng ý dùng cho ảnh quà"
              style={{ width: 100, height: 100, borderRadius: 14 }}
            />
          ) : null}
          {draft.souvenirOptIn && !draft.apiKeys ? (
            <Action
              secondary
              label="Không tạo ảnh hoạt hoạ"
              onPress={() =>
                useCaptureStore.setState({ draft: { ...draft, souvenirOptIn: false } })
              }
            />
          ) : null}
          {intakeRejected ? (
            <Action
              secondary
              label="Lấy lại GPS để gửi lại"
              loading={locationBusy}
              onPress={() => void refreshLocation()}
            />
          ) : null}
        </Surface>
      ) : null}
      {!result && !submissionId ? (
        <Action
          label="Gửi đánh giá"
          disabled={intakeRejected || locationBusy}
          loading={busy}
          onPress={() => void send(false)}
        />
      ) : null}
      {pending ? (
        <Note>
          {waiting ? 'Vẫn đang xử lý.' : `Trạng thái: ${result?.status ?? 'đang kiểm tra'}`}
        </Note>
      ) : null}
      {result?.stage ? <Note>Giai đoạn: {result.stage}</Note> : null}
      {result?.tool_status
        ? Object.entries(result.tool_status).map(([tool, status]) => (
            <Note key={tool}>
              {tool}: {typeof status === 'string' ? status : 'Chưa có trạng thái dạng văn bản'}
            </Note>
          ))
        : null}
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
      {result?.verdict ? (
        <Note error={!['accepted', 'completed'].includes(result.verdict)}>
          {
            {
              accepted: 'Khám phá đã được chấp nhận.',
              completed: 'Nhiệm vụ đã hoàn thành.',
              not_matched: 'Ảnh chưa đúng địa điểm yêu cầu. Hãy giữ đúng công trình trong khung.',
              wrong_subject: 'Ảnh sai đối tượng yêu cầu. Hãy chụp lại đúng địa điểm.',
              out_of_radius: 'Bạn đang ngoài bán kính nhiệm vụ. Hãy tới gần địa điểm rồi chụp lại.',
              location_unverified:
                'Chưa xác minh được vị trí. Hãy cấp quyền và lấy lại GPS ở nơi thoáng.',
              retake_required: 'Ảnh chưa đủ rõ. Hãy giữ máy ổn định và chụp lại.',
              unidentified: 'Chưa nhận diện được địa điểm. Hãy chụp rõ chi tiết hoặc biển tên.',
              out_of_scope: 'Ảnh chưa thuộc phạm vi khám phá hỗ trợ.',
            }[result.verdict]
          }
        </Note>
      ) : null}
      {result?.verdict === 'completed' && result.discovery ? (
        <Celebration discoveryId={result.discovery.id} animate />
      ) : null}
      {result?.instruction ? <Note>{result.instruction}</Note> : null}
      {!pending ? <Action secondary label="Chụp ảnh mới" disabled={busy} onPress={retake} /> : null}
    </Page>
  );
}
