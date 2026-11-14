import { useCallback, useRef, useState } from 'react';
import { useFocusEffect } from 'expo-router';
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { z } from 'zod';
import { ApiError } from '@/services/api/client';
import { pageSchema, socialRequest } from '@/services/api/social';
import { tokenFor, useFixtureSession } from './session';

function useActor() {
  const actor = useFixtureSession((s) => s.actor);
  return { actor, token: actor ? tokenFor(actor) : '' };
}

function retry(failures: number, error: Error) {
  return failures < 1 && (!(error instanceof ApiError) || error.status >= 500);
}

export function useSocialQuery<T>(path: string, schema: z.ZodType<T>, enabled = true) {
  const { actor, token } = useActor();
  return useQuery({
    queryKey: ['social', actor, path],
    queryFn: ({ signal }) => socialRequest(token, path, schema, { signal }),
    enabled: !!actor && enabled,
    retry,
    gcTime: path.startsWith('/assets/') ? 0 : undefined,
  });
}

export function useSocialPage<T>(path: string, item: z.ZodType<T>, enabled = true) {
  const { actor, token } = useActor();
  return useInfiniteQuery({
    queryKey: ['social', actor, path],
    initialPageParam: null as string | null,
    queryFn: ({ pageParam, signal }) =>
      socialRequest(
        token,
        pageParam
          ? `${path}${path.includes('?') ? '&' : '?'}cursor=${encodeURIComponent(pageParam)}`
          : path,
        pageSchema(item),
        { signal },
      ),
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    enabled: !!actor && enabled,
    retry,
  });
}

export function useRefreshOnFocus(refetch: () => Promise<unknown>) {
  useFocusEffect(
    useCallback(() => {
      if (useFixtureSession.getState().actor) void refetch();
    }, [refetch]),
  );
}

function newKey() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  // The key correlates retries. It is neither a credential nor a security token.
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (character) => {
    const nibble = Math.floor(Math.random() * 16);
    return (character === 'x' ? nibble : (nibble & 3) | 8).toString(16);
  });
}

type Command<T> = {
  method: 'POST' | 'PATCH' | 'PUT' | 'DELETE';
  path: string;
  schema: z.ZodType<T>;
  body?: object;
};

export function useSocialMutation() {
  const { actor, token } = useActor();
  const client = useQueryClient();
  const pending = useRef(new Map<string, string>());
  const busy = useRef(false);
  const [repeat, setRepeat] = useState<(() => Promise<void>) | null>(null);
  const mutation = useMutation({
    mutationFn: async (command: Command<unknown>) => {
      if (!actor) throw new Error('Phiên đã kết thúc.');
      const fingerprint = JSON.stringify([actor, command.method, command.path, command.body]);
      const key = pending.current.get(fingerprint) ?? newKey();
      pending.current.set(fingerprint, key);
      try {
        const result = await socialRequest(token, command.path, command.schema, {
          method: command.method,
          headers: { 'Content-Type': 'application/json', 'Idempotency-Key': key },
          body: command.body === undefined ? undefined : JSON.stringify(command.body),
        });
        pending.current.delete(fingerprint);
        return result;
      } catch (error) {
        if (error instanceof ApiError && error.status < 500 && !error.retryable) {
          pending.current.delete(fingerprint);
        }
        throw error;
      }
    },
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ['social', actor] });
    },
  });
  async function send<T>(command: Command<T>, onSuccess?: (value: T) => void) {
    if (busy.current) return;
    busy.current = true;
    try {
      setRepeat(null);
      const value = await mutation.mutateAsync(command);
      if (useFixtureSession.getState().actor === actor) onSuccess?.(command.schema.parse(value));
    } catch (error) {
      if (!(error instanceof ApiError) || error.status >= 500 || error.retryable) {
        setRepeat(() => () => send(command, onSuccess));
      }
    } finally {
      busy.current = false;
    }
  }
  return {
    send,
    pending: mutation.isPending,
    error: mutation.error,
    retry: () => {
      void repeat?.();
    },
    canRetry: mutation.isError && repeat !== null,
  };
}
