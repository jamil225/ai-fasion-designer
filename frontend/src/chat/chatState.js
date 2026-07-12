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
export function useChatState({ onCombosChange } = {}) {
  const [threadId, setThreadId] = useState(generateThreadId);
  const [messages, setMessages] = useState([]);
  const [pendingInterrupt, setPendingInterrupt] = useState(null);
  const [lastCombos, setLastCombos] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);

  // Guard against concurrent sends while a request is in-flight.
  const inflightRef = useRef(false);
  const abortControllerRef = useRef(null);

  const _mergeResponse = useCallback((data) => {
    if (data.type === "interrupt") {
      setPendingInterrupt(data.pending_action);
      setLastCombos([]);
    } else {
      // final
      setPendingInterrupt(null);
      const newCombos = data.combos || [];
      setLastCombos(newCombos);
      // Notify parent with new combos so canvas can display them
      if (onCombosChange && newCombos.length > 0) {
        onCombosChange(newCombos);
      }
      // Append assistant message if present
      if (data.message) {
        setMessages((prev) => [
          ...prev,
          { 
            role: "assistant", 
            content: data.message, 
            combos: newCombos,
            guardrailsPassed: data.guardrails_passed
          },
        ]);
      }
    }
  }, [onCombosChange]);

  const send = useCallback(
    async (text) => {
      if (!text.trim() || inflightRef.current) return;
      inflightRef.current = true;
      setError(null);
      setIsLoading(true);

      // Append user bubble immediately
      setMessages((prev) => [...prev, { role: "user", content: text }]);

      abortControllerRef.current = new AbortController();
      try {
        const data = await sendMessage(threadId, text, abortControllerRef.current.signal);
        _mergeResponse(data);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
        }
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

      abortControllerRef.current = new AbortController();
      try {
        const data = await sendResume(threadId, replyText, abortControllerRef.current.signal);
        _mergeResponse(data);
      } catch (err) {
        if (err.name !== "AbortError") {
          setError(err.message);
        }
      } finally {
        setIsLoading(false);
        inflightRef.current = false;
      }
    },
    [threadId, _mergeResponse],
  );

  const stop = useCallback(() => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
  }, []);

  const reset = useCallback(() => {
    setThreadId(generateThreadId());
    setMessages([]);
    setPendingInterrupt(null);
    setLastCombos([]);
    setError(null);
    setIsLoading(false);
    inflightRef.current = false;
    // Clear canvas combos on reset
    if (onCombosChange) onCombosChange([]);
  }, [onCombosChange]);

  return {
    threadId,
    messages,
    pendingInterrupt,
    lastCombos,
    isLoading,
    error,
    send,
    resume,
    stop,
    reset,
  };
}
