import { useState, useCallback, useRef } from "react";
import { sendMessage, sendResume } from "./chatApi";

function generateThreadId() {
  // crypto.randomUUID() is available in modern browsers
  if (typeof crypto !== "undefined" && crypto.randomUUID) {
    return crypto.randomUUID();
  }
  // Fallback for older browsers
  return "t-" + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
}

/**
 * Custom hook exposing the chat state and actions.
 *
 * Returns { threadId, messages, pendingInterrupt, lastCombos, isLoading,
 *           error, send, resume, reset }
 */
export function useChatState() {
  const [threadId, setThreadId] = useState(generateThreadId);
  const [messages, setMessages] = useState([]);
  const [pendingInterrupt, setPendingInterrupt] = useState(null);
  const [lastCombos, setLastCombos] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Guard against concurrent sends while a request is in-flight.
  const inflightRef = useRef(false);

  const _mergeResponse = useCallback((data) => {
    if (data.type === "interrupt") {
      setPendingInterrupt(data.pending_action);
      setLastCombos([]);
    } else {
      // final
      setPendingInterrupt(null);
      setLastCombos(data.combos || []);
      // Append assistant message if present
      if (data.message) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", content: data.message, combos: data.combos || [] },
        ]);
      }
    }
  }, []);

  const send = useCallback(
    async (text) => {
      if (!text.trim() || inflightRef.current) return;
      inflightRef.current = true;
      setError(null);
      setIsLoading(true);

      // Append user bubble immediately
      setMessages((prev) => [...prev, { role: "user", content: text }]);

      try {
        const data = await sendMessage(threadId, text);
        _mergeResponse(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
        inflightRef.current = false;
      }
    },
    [threadId, _mergeResponse],
  );

  const resume = useCallback(
    async (replyText) => {
      if (!replyText.trim() || inflightRef.current) return;
      inflightRef.current = true;
      setError(null);
      setIsLoading(true);

      // Append user reply bubble
      setMessages((prev) => [...prev, { role: "user", content: replyText }]);

      try {
        const data = await sendResume(threadId, replyText);
        _mergeResponse(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setIsLoading(false);
        inflightRef.current = false;
      }
    },
    [threadId, _mergeResponse],
  );

  const reset = useCallback(() => {
    setThreadId(generateThreadId());
    setMessages([]);
    setPendingInterrupt(null);
    setLastCombos([]);
    setError(null);
    setIsLoading(false);
    inflightRef.current = false;
  }, []);

  return {
    threadId,
    messages,
    pendingInterrupt,
    lastCombos,
    isLoading,
    error,
    send,
    resume,
    reset,
  };
}
