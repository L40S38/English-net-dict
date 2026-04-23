import { ChatPanel } from "./ChatPanel";
import { phraseChatApi } from "../lib/api";
import { useChatPanel } from "../lib/useChatPanel";

interface PhraseChatPanelProps {
  phraseId: number;
}

const presetQuestions = ["この熟語のニュアンスを教えて", "例文を作って", "似た熟語との違いは？"];

export function PhraseChatPanel({ phraseId }: PhraseChatPanelProps) {
  const chat = useChatPanel({
    sessionsQueryKey: ["phrase-chat-sessions", phraseId],
    fetchSessions: () => phraseChatApi.sessions(phraseId),
    createSession: () => phraseChatApi.createSession(phraseId),
  });

  return (
    <ChatPanel
      title="熟語チャット"
      sessions={chat.sessions}
      currentSessionId={chat.currentSessionId}
      messages={chat.messages}
      presetQuestions={presetQuestions}
      input={chat.input}
      placeholder="この熟語について質問"
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
