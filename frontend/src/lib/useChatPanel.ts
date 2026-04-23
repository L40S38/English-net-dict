import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { chatApi } from "./api";
import type { ChatSession } from "../types";

interface UseChatPanelOptions {
  sessionsQueryKey: QueryKey;
  fetchSessions: () => Promise<ChatSession[]>;
  createSession: () => Promise<ChatSession>;
  sessionsEnabled?: boolean;
}

export function useChatPanel({
  sessionsQueryKey,
  fetchSessions,
  createSession,
  sessionsEnabled = true,
}: UseChatPanelOptions) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: sessionsQueryKey,
    queryFn: fetchSessions,
    enabled: sessionsEnabled,
  });

  const currentSession = useMemo<ChatSession | undefined>(
    () =>
      sessionsQuery.data?.find((session) => session.id === sessionId) ?? sessionsQuery.data?.[0],
    [sessionsQuery.data, sessionId],
  );

  const messagesQuery = useQuery({
    queryKey: ["chat-messages", currentSession?.id],
    queryFn: () => chatApi.messages(currentSession!.id),
    enabled: !!currentSession,
  });

  const createSessionMutation = useMutation({
    mutationFn: createSession,
    onSuccess: async (session) => {
      setSessionId(session.id);
      await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    },
  });

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      let currentSessionId = currentSession?.id;
      if (!currentSessionId) {
        const created = await createSession();
        currentSessionId = created.id;
        setSessionId(created.id);
        await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
      }
      return chatApi.sendMessage(currentSessionId, content.trim());
    },
    onSuccess: async () => {
      setPendingUserMessage(null);
      if (currentSession?.id) {
        await queryClient.invalidateQueries({ queryKey: ["chat-messages", currentSession.id] });
      }
      await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    },
    onError: () => {
      setPendingUserMessage(null);
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ sid, title }: { sid: number; title: string }) =>
      chatApi.updateSession(sid, title),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (sid: number) => chatApi.deleteSession(sid),
    onSuccess: async () => {
      setSessionId(null);
      await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    },
  });

  return {
    input,
    pendingUserMessage,
    sessions: sessionsQuery.data,
    sessionsLoading: sessionsQuery.isLoading,
    messages: messagesQuery.data,
    messagesLoading: messagesQuery.isLoading,
    currentSessionId: currentSession?.id ?? null,
    createPending: createSessionMutation.isPending,
    sendPending: sendMutation.isPending,
    setInput,
    setSessionId,
    createSession: () => createSessionMutation.mutate(),
    sendMessage: (content: string) => {
      setPendingUserMessage(content);
      sendMutation.mutate(content);
      setInput("");
    },
    renameSession: (sid: number, title: string) => renameMutation.mutate({ sid, title }),
    deleteSession: (sid: number) => deleteMutation.mutate(sid),
  };
}
