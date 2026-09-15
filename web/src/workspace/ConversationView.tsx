import { useEffect, useRef, useState } from "react";
import type { ClarificationSnapshot, ConversationSnapshot, Message } from "./types";

export function ConversationView({
  conversation,
  messages,
  clarification,
  onSend,
  onOpenIssue,
  onCreateIssue,
}: {
  conversation: ConversationSnapshot;
  messages: Message[];
  clarification: ClarificationSnapshot | null;
  onSend: (content: string, replyTo?: { clarificationId: string; expectedRevision: string }) => Promise<void>;
  onOpenIssue: (issueId: string) => void;
  onCreateIssue: () => void;
}) {
  const [input, setInput] = useState("");
  const [reply, setReply] = useState(false);
  const bodyRef = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = bodyRef.current;
    if (el !== null) el.scrollTop = el.scrollHeight;
  }, [messages]);
  const submit = async () => {
    const content = input.trim();
    if (content.length === 0) return;
    const replyTo = reply && clarification !== null && clarification.actions.canReply
      ? { clarificationId: clarification.id, expectedRevision: clarification.revision }
      : undefined;
    await onSend(content, replyTo);
    setInput("");
    setReply(false);
  };
  return (
    <div className="ws-conversation">
      <header className="ws-top">
        <div>
          <p>订单系统 / 会话 · Manager 主房间</p>
          <h1>{conversation.title}</h1>
          <p>关联 {conversation.linkedIssues.length} 条 Issue · 映射上游 task_room，不嵌入 Element</p>
        </div>
        <button onClick={onCreateIssue}>＋ 建立新的 Issue</button>
      </header>
      <div className="ws-body" ref={bodyRef}>
        <div className="ws-chat">
          {messages.map((message) => {
            const card = message.issueCard;
            if (card !== null) {
              return (
                <div className="ws-issue-card" key={message.id}>
                  <div>
                    <strong>#{card.number} {card.title}</strong>
                    <p className="ws-quiet">独立工作事项 · 主 ChangeSet 已建立</p>
                  </div>
                  <button onClick={() => onOpenIssue(card.id)}>查看 Issue →</button>
                </div>
              );
            }
            return (
              <article className="ws-message" key={message.id}>
                <div className="ws-message-head"><span>{message.author.displayName}</span><time>{message.createdAt.replace("T", " ").replace("Z", "")}</time></div>
                <div className={message.author.kind === "user" ? "ws-human" : undefined} style={{ whiteSpace: "pre-wrap" }}>{message.content}</div>
                {message.clarificationId !== null && clarification !== null && (
                  <div className="ws-clarify">
                    <h2>需要补充目标</h2>
                    <p>也可以直接回复说明。目标明确前，这条请求暂不调整计划。</p>
                    <div className="ws-clarify-actions">
                      {clarification.candidates.map((item) => (
                        <button key={item.issueId} onClick={() => onOpenIssue(item.issueId)}>#{item.number} {item.title}</button>
                      ))}
                    </div>
                    {clarification.actions.canReply && <p className="ws-quiet" style={{ marginTop: 10 }}>答复会引用当前问题版本 {clarification.revision}。</p>}
                    {!clarification.actions.canReply && <p className="ws-quiet">当前问题已保存答复，等待处理。</p>}
                  </div>
                )}
              </article>
            );
          })}
        </div>
      </div>
      <div className="ws-composer-wrap">
        {reply && clarification !== null && (
          <div className="ws-reply-ref">
            <span>回复 Manager 的目标问题<small style={{ display: "block" }}>引用 {clarification.id}</small></span>
            <button onClick={() => setReply(false)} aria-label="移除问题引用">×</button>
          </div>
        )}
        <div className="ws-composer">
          <textarea value={input} onChange={(event) => setInput(event.target.value)} placeholder="继续讨论；聊天不会自动修改某条 Issue…" aria-label="给 Manager 的消息" />
          <div className="ws-composer-bottom">
            <span>
              Manager
              {clarification?.actions.canReply === true && (
                <button type="button" onClick={() => setReply(true)} style={{ marginLeft: 8 }}>引用澄清问题</button>
              )}
            </span>
            <button className="ws-send" onClick={() => void submit()} aria-label="发送">↑</button>
          </div>
        </div>
      </div>
    </div>
  );
}
