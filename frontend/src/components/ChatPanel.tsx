import { useEffect, useRef, useState } from "react";
import { Loader2 } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { Card, Chip, ChipList, Muted, Row } from "./atom";
import type { ChatMessage, ChatSession } from "../types";

function normalizeText(input: string): string {
  const cleaned = Array.from(input)
    .filter((ch) => {
      const code = ch.charCodeAt(0);
      return (code >= 32 && code !== 127) || code === 10 || code === 13;
    })
    .join("")
    .trim();
  const mojibakeLike = (cleaned.match(/縺|繧|隱|譁|�/g) ?? []).length;
  if (cleaned.length > 0 && mojibakeLike > cleaned.length / 4) {
    return "文字エンコード異常の可能性があります。再入力してください。";
  }
  return cleaned;
}

interface ChatPanelProps {
  title: string;
  sessions?: ChatSession[];
  currentSessionId: number | null;
  messages?: ChatMessage[];
  presetQuestions: string[];
  input: string;
  placeholder: string;
  sessionsLoading: boolean;
  messagesLoading: boolean;
  createPending: boolean;
  sendPending: boolean;
  pendingUserMessage?: string | null;
  onInputChange: (value: string) => void;
  onCreateSession: () => void;
  onSelectSession: (sessionId: number) => void;
  onSendMessage: (content: string) => void;
  onRenameSession?: (sessionId: number, title: string) => void;
  onDeleteSession?: (sessionId: number) => void;
}

export function ChatPanel({
  title,
  sessions,
  currentSessionId,
  messages,
  presetQuestions,
  input,
  placeholder,
  sessionsLoading,
  messagesLoading,
  createPending,
  sendPending,
  pendingUserMessage,
  onInputChange,
  onCreateSession,
  onSelectSession,
  onSendMessage,
  onRenameSession,
  onDeleteSession,
}: ChatPanelProps) {
  const chatBoxRef = useRef<HTMLDivElement>(null);
  const [editingTitle, setEditingTitle] = useState(false);
  const [titleDraft, setTitleDraft] = useState("");

  useEffect(() => {
    const el = chatBoxRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages, pendingUserMessage, sendPending]);

  const currentSession = sessions?.find((s) => s.id === currentSessionId);

  const handleStartRename = () => {
    if (!currentSession) return;
    setTitleDraft(currentSession.title);
    setEditingTitle(true);
  };

  const handleConfirmRename = () => {
    if (currentSession && titleDraft.trim() && onRenameSession) {
      onRenameSession(currentSession.id, titleDraft.trim());
    }
    setEditingTitle(false);
  };

  const handleDeleteSession = () => {
    if (!currentSession || !onDeleteSession) return;
    if (window.confirm(`セッション「${currentSession.title}」を削除しますか？`)) {
      onDeleteSession(currentSession.id);
    }
  };

  return (
    <Card stack>
      <Row justify="between">
        <h3>{title}</h3>
        <button type="button" onClick={onCreateSession} disabled={createPending}>
          {createPending ? "作成中..." : "新規セッション"}
        </button>
      </Row>
      <Row>
        {editingTitle ? (
          <>
            <input
              value={titleDraft}
              onChange={(e) => setTitleDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleConfirmRename();
                if (e.key === "Escape") setEditingTitle(false);
              }}
              autoFocus
              style={{ flex: 1 }}
            />
            <button type="button" onClick={handleConfirmRename}>
              保存
            </button>
            <button
              type="button"
              onClick={() => setEditingTitle(false)}
              style={{ background: "var(--color-border)", color: "var(--color-text)" }}
            >
              取消
            </button>
          </>
        ) : (
          <>
            <select
              value={currentSessionId ?? ""}
              onChange={(e) => onSelectSession(Number(e.target.value))}
              disabled={sessionsLoading || createPending}
              style={{ flex: 1 }}
            >
              {sessions?.map((session) => (
                <option key={session.id} value={session.id}>
                  {session.title}
                </option>
              ))}
              {!sessions?.length && <option value="">セッションなし</option>}
            </select>
            {currentSession && onRenameSession && (
              <button
                type="button"
                onClick={handleStartRename}
                title="セッション名を変更"
                style={{ background: "var(--color-border)", color: "var(--color-text)", padding: "0.55rem 0.6rem" }}
              >
                ✎
              </button>
            )}
            {currentSession && onDeleteSession && (
              <button
                type="button"
                onClick={handleDeleteSession}
                title="セッションを削除"
                style={{ background: "#fecaca", color: "#991b1b", padding: "0.55rem 0.6rem" }}
              >
                ✕
              </button>
            )}
          </>
        )}
      </Row>
      <ChipList>
        {presetQuestions.map((q) => (
          <Chip key={q} onClick={() => onInputChange(q)}>
            {q}
          </Chip>
        ))}
      </ChipList>
      <div className="chat-box" ref={chatBoxRef}>
        {messagesLoading && <Muted as="p">メッセージを読み込み中...</Muted>}
        {messages?.map((msg) => (
          <div key={msg.id} className={`bubble ${msg.role === "assistant" ? "assistant" : "user"}`}>
            {msg.role === "assistant" ? (
              <div className="markdown-body">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {normalizeText(msg.content)}
                </ReactMarkdown>
              </div>
            ) : (
              <p>{normalizeText(msg.content)}</p>
            )}
            {msg.role === "assistant" && msg.citations.length > 0 && (
              <Muted as="small">
                参照:
                {msg.citations.map((c, idx) => (
                  <span key={idx}> {String(c.source ?? "data")} </span>
                ))}
              </Muted>
            )}
          </div>
        ))}
        {pendingUserMessage && (
          <div className="bubble user">
            <p>{normalizeText(pendingUserMessage)}</p>
          </div>
        )}
        {sendPending && (
          <div className="bubble assistant generating-bubble">
            <Loader2 size={16} className="generating-spinner" />
            <span className="generating-text">回答を生成中</span>
          </div>
        )}
      </div>
      <Row
        as="form"
        onSubmit={(e) => {
          e.preventDefault();
          const content = input.trim();
          if (!content) return;
          onSendMessage(content);
        }}
      >
        <input
          value={input}
          onChange={(e) => onInputChange(e.target.value)}
          placeholder={placeholder}
          disabled={sendPending || createPending}
        />
        <button type="submit" disabled={sendPending || createPending}>
          {sendPending ? "送信中..." : "送信"}
        </button>
      </Row>
    </Card>
  );
}
