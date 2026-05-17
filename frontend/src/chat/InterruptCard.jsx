import { useState } from "react";

/**
 * InterruptCard - renders when the agent pauses to ask for clarification.
 * Shows the question prominently and provides a reply input + submit button.
 */
export default function InterruptCard({ question, onSubmit, isLoading }) {
  const [reply, setReply] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!reply.trim() || isLoading) return;
    onSubmit(reply.trim());
    setReply("");
  };

  return (
    <div className="interrupt-card">
      <p className="interrupt-question">{question}</p>
      <form className="interrupt-input-row" onSubmit={handleSubmit}>
        <input
          id="interrupt-reply-input"
          type="text"
          value={reply}
          onChange={(e) => setReply(e.target.value)}
          placeholder="Type your answer..."
          autoFocus
          disabled={isLoading}
        />
        <button
          id="interrupt-submit-btn"
          type="submit"
          className="interrupt-submit-btn"
          disabled={!reply.trim() || isLoading}
        >
          Reply
        </button>
      </form>
    </div>
  );
}
