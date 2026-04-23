import { ChatPanel } from "./ChatPanel";
import { componentChatApi } from "../lib/api";
import { useChatPanel } from "../lib/useChatPanel";

interface ComponentChatPanelProps {
  componentText: string;
}

const presetQuestions = [
  "この語源要素のコアイメージを説明して",
  "この語源要素を含む単語の共通点は？",
  "この語根の派生語をもっと教えて",
];

export function ComponentChatPanel({ componentText }: ComponentChatPanelProps) {
  const sessionsQueryKey = ["component-chat-sessions", componentText];
  const chat = useChatPanel({
    sessionsQueryKey,
    fetchSessions: () => componentChatApi.sessions(componentText),
    createSession: () => componentChatApi.createSession(componentText),
    sessionsEnabled: componentText.trim().length > 0,
  });

  return (
    <ChatPanel
      title="語源要素チャット"
      sessions={chat.sessions}
      currentSessionId={chat.currentSessionId}
      messages={chat.messages}
      presetQuestions={presetQuestions}
      input={chat.input}
      placeholder="この語源要素について質問"
      sessionsLoading={chat.sessionsLoading}
      messagesLoading={chat.messagesLoading}
      createPending={chat.createPending}
      sendPending={chat.sendPending}
      pendingUserMessage={chat.pendingUserMessage}
      onInputChange={chat.setInput}
      onCreateSession={chat.createSession}
      onSelectSession={chat.setSessionId}
      onSendMessage={chat.sendMessage}
      onRenameSession={chat.renameSession}
      onDeleteSession={chat.deleteSession}
    />
  );
}
