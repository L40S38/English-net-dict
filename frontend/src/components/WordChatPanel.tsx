import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ChatPanel } from "./ChatPanel";
import { chatApi } from "../lib/api";
import type { ChatSession } from "../types";

interface Props {
  wordId: number;
}

const presetQuestions = ["語源をもっと簡単に説明して", "覚え方を作って", "似た単語との違いは？"];

export function WordChatPanel({ wordId }: Props) {
  const queryClient = useQueryClient();
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [input, setInput] = useState("");
  const [pendingUserMessage, setPendingUserMessage] = useState<string | null>(null);

  const sessionsQuery = useQuery({
    queryKey: ["chat-sessions", wordId],
    queryFn: () => chatApi.sessions(wordId),
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

  const createSessionMutation = useMutation({
    mutationFn: () => chatApi.createSession(wordId),
    onSuccess: async (session) => {
      setSessionId(session.id);
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", wordId] });
    },
  });

  const sendMutation = useMutation({
    mutationFn: async (content: string) => {
      let sid = currentSession?.id;
      if (!sid) {
        const created = await chatApi.createSession(wordId);
        sid = created.id;
        setSessionId(created.id);
        await queryClient.invalidateQueries({ queryKey: ["chat-sessions", wordId] });
      }
      return chatApi.sendMessage(sid, content.trim());
    },
    onSuccess: async () => {
      setPendingUserMessage(null);
      if (currentSession?.id) {
        await queryClient.invalidateQueries({ queryKey: ["chat-messages", currentSession.id] });
      }
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", wordId] });
    },
    onError: () => {
      setPendingUserMessage(null);
    },
  });

  const renameMutation = useMutation({
    mutationFn: ({ sid, title }: { sid: number; title: string }) =>
      chatApi.updateSession(sid, title),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", wordId] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: (sid: number) => chatApi.deleteSession(sid),
    onSuccess: async () => {
      setSessionId(null);
      await queryClient.invalidateQueries({ queryKey: ["chat-sessions", wordId] });
    },
  });

  return (
    <ChatPanel
      title="単語チャット"
      sessions={sessionsQuery.data}
      currentSessionId={currentSession?.id ?? null}
      messages={messagesQuery.data}
      presetQuestions={presetQuestions}
      input={input}
      placeholder="この単語について質問"
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
