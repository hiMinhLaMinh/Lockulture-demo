import type { PropsWithChildren } from 'react';
import { ActivityIndicator, Text } from 'react-native';
import { Action } from '@/shared/components/action';
import { commonStyles as c } from '@/shared/components/surface';
import { colors } from '@/shared/theme/tokens';
import { ApiError } from '@/services/api/client';
import { SelectRow } from '@/features/social/ui';

export function ErrorNote({ error }: { error: Error | null }) {
  if (!error) return null;
  const message =
    error instanceof ApiError
      ? ({
          401: 'Phiên đăng nhập đã hết.',
          403: 'Bạn không có quyền thực hiện thao tác.',
          404: 'Nội dung không còn khả dụng.',
          409: 'Thao tác xung đột với dữ liệu hiện tại.',
          422: 'Thông tin gửi đi chưa hợp lệ.',
        }[error.status] ?? error.message)
      : 'Không tải được dữ liệu. Kiểm tra kết nối và thử lại.';
  return (
    <Text accessibilityRole="alert" style={[c.body, { color: colors.danger }]}>
      {message}
    </Text>
  );
}

type QueryStatus = {
  isPending: boolean;
  error: Error | null;
  refetch: () => Promise<unknown>;
};

export function QueryView({ query, children }: PropsWithChildren<{ query: QueryStatus }>) {
  if (query.isPending) return <ActivityIndicator color={colors.accent} />;
  if (query.error)
    return (
      <>
        <ErrorNote error={query.error} />
        <Action secondary label="Tải lại" onPress={() => void query.refetch()} />
      </>
    );
  return <>{children}</>;
}

export function PageControls({
  query,
  empty,
}: {
  query: {
    hasNextPage: boolean;
    isFetchingNextPage: boolean;
    fetchNextPage: () => Promise<unknown>;
  };
  empty?: string;
}) {
  return (
    <>
      {empty ? <Text style={c.label}>{empty}</Text> : null}
      {query.hasNextPage && (
        <Action
          secondary
          label="Tải thêm"
          loading={query.isFetchingNextPage}
          onPress={() => void query.fetchNextPage()}
        />
      )}
    </>
  );
}

export function Selection({
  rows,
  ids,
  change,
  maximum,
}: {
  rows: { id: string; label: string }[];
  ids: string[];
  change: (ids: string[]) => void;
  maximum: number;
}) {
  return rows.map((row) => (
    <SelectRow
      key={row.id}
      name={row.label}
      selected={ids.includes(row.id)}
      onPress={() => {
        if (ids.includes(row.id)) change(ids.filter((id) => id !== row.id));
        else if (ids.length < maximum) change([...ids, row.id]);
      }}
    />
  ));
}

export function MutationFeedback({
  mutation,
}: {
  mutation: { error: Error | null; canRetry: boolean; retry: () => void };
}) {
  return (
    <>
      <ErrorNote error={mutation.error} />
      {mutation.canRetry && <Action secondary label="Thử lại thao tác" onPress={mutation.retry} />}
    </>
  );
}
