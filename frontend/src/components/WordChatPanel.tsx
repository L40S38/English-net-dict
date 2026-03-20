import { ChatPanel } from "./ChatPanel";
import { chatApi } from "../lib/api";
import { useChatPanel } from "../lib/useChatPanel";

interface WordChatPanelProps {
  wordId: number;
}

const presetQuestions = ["語源をもっと簡単に説明して", "覚え方を作って", "似た単語との違いは？"];

export function WordChatPanel({ wordId }: WordChatPanelProps) {
  const chat = useChatPanel({
    sessionsQueryKey: ["chat-sessions", wordId],
    fetchSessions: () => chatApi.sessions(wordId),
    createSession: () => chatApi.createSession(wordId),
  });

  return (
    <ChatPanel
      title="単語チャット"
      sessions={chat.sessions}
      currentSessionId={chat.currentSessionId}
      messages={chat.messages}
      presetQuestions={presetQuestions}
      input={chat.input}
      placeholder="この単語について質問"
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
