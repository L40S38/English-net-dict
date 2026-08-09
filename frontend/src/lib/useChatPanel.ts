import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient, type QueryKey } from "@tanstack/react-query";

import { chatApi } from "./api";
import type { ChatReply, ChatSession } from "../types";

// Tool names whose execution mutates word data; when one appears in an assistant
// message's citations, the cached word detail query must be refreshed.
const WRITE_TOOL_SOURCES = new Set(["register_related_word"]);

function repliedWithDataChange(reply: ChatReply): boolean {
  return reply.assistant_message.citations.some(
    (c) => typeof c.source === "string" && WRITE_TOOL_SOURCES.has(c.source),
  );
}

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
    onSuccess: async (reply) => {
      setPendingUserMessage(null);
      if (currentSession?.id) {
        await queryClient.invalidateQueries({ queryKey: ["chat-messages", currentSession.id] });
      }
      await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
      if (repliedWithDataChange(reply)) {
        await queryClient.invalidateQueries({ queryKey: ["word"] });
      }
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
