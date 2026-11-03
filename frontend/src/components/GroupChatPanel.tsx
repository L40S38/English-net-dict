import { ChatPanel } from "./ChatPanel";
import { groupChatApi } from "../lib/api";
import { useChatPanel } from "../lib/useChatPanel";

interface GroupChatPanelProps {
  groupId: number;
}

const presetQuestions = [
  "このグループの共通点をまとめて",
  "覚え方を作って",
  "追加すべき関連語は？",
];

export function GroupChatPanel({ groupId }: GroupChatPanelProps) {
  const chat = useChatPanel({
    sessionsQueryKey: ["group-chat-sessions", groupId],
    fetchSessions: () => groupChatApi.sessions(groupId),
    createSession: () => groupChatApi.createSession(groupId),
  });

  return (
    <ChatPanel
      title="グループチャット"
      sessions={chat.sessions}
      currentSessionId={chat.currentSessionId}
      messages={chat.messages}
      presetQuestions={presetQuestions}
      input={chat.input}
      placeholder="このグループについて質問"
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
