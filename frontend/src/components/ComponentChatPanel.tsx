import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ChatPanel } from "./ChatPanel";
import { chatApi, componentChatApi } from "../lib/api";
import type { ChatSession } from "../types";

interface Props {
  componentText: string;
}

const presetQuestions = [
  "この語源要素のコアイメージを説明して",
  "この語源要素を含む単語の共通点は？",
  "この語根の派生語をもっと教えて",
];

export function ComponentChatPanel({ componentText }: Props) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["component-chat-sessions", componentText],
    queryFn: () => componentChatApi.sessions(componentText),
    enabled: componentText.trim().length > 0,
  });

  const currentSession = useMemo<ChatSession | undefined>(
    () => sessionsQuery.data?.find((s) => s.id === sessionId) ?? sessionsQuery.data?.[0],
    [sessionsQuery.data, sessionId],
  );

  const messagesQuery = useQuery({
    queryKey: ["chat-messages", currentSession?.id],
    queryFn: () => chatApi.messages(currentSession!.id),
    enabled: !!currentSession,
  });

  const sessionsQueryKey = ["component-chat-sessions", componentText];

  const createSessionMutation = useMutation({
    mutationFn: () => componentChatApi.createSession(componentText),
    onSuccess: async (session) => {
      setSessionId(session.id);
      await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
    },
  });

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      let sid = currentSession?.id;
      if (!sid) {
        const created = await componentChatApi.createSession(componentText);
        sid = created.id;
        setSessionId(created.id);
        await queryClient.invalidateQueries({ queryKey: sessionsQueryKey });
      }
      return chatApi.sendMessage(sid, content.trim());
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

  return (
    <ChatPanel
      title="語源要素チャット"
      sessions={sessionsQuery.data}
      currentSessionId={currentSession?.id ?? null}
      messages={messagesQuery.data}
      presetQuestions={presetQuestions}
      input={input}
      placeholder="この語源要素について質問"
      sessionsLoading={sessionsQuery.isLoading}
      messagesLoading={messagesQuery.isLoading}
      createPending={createSessionMutation.isPending}
      sendPending={sendMutation.isPending}
      pendingUserMessage={pendingUserMessage}
      onInputChange={setInput}
      onCreateSession={() => createSessionMutation.mutate()}
      onSelectSession={(id) => setSessionId(id)}
      onSendMessage={(content) => {
        setPendingUserMessage(content);
        sendMutation.mutate(content);
        setInput("");
      }}
      onRenameSession={(sid, title) => renameMutation.mutate({ sid, title })}
      onDeleteSession={(sid) => deleteMutation.mutate(sid)}
    />
  );
}
