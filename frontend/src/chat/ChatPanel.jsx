import { useState, useRef, useEffect } from "react";
import { useChatState } from "./chatState";
import InterruptCard from "./InterruptCard";
import { getImageUrl } from "../api";
import ImageLightbox from "../ImageLightbox";
import "./ChatPanel.css";

const THINKING_STAGES = [
  { delay: 0,    text: "Checking your preferences…" },
  { delay: 2800, text: "Building a search query…" },
  { delay: 5000, text: "Searching the catalog…" },
  { delay: 7000, text: "Curating outfit combinations…" },
  { delay: 10000, text: "Almost there…" },
];

/**
 * Provides staged progress text while an operation is loading.
 * @param {boolean} isLoading - Whether to display the progress stages.
 * @return {string|null} The current progress text, or `null` when loading is inactive.
 */
function useThinkingStage(isLoading) {
  const [stage, setStage] = useState(null);
  const timersRef = useRef([]);

  useEffect(() => {
    if (isLoading) {
      setStage(THINKING_STAGES[0].text);
      timersRef.current = THINKING_STAGES.slice(1).map(({ delay, text }) =>
        setTimeout(() => setStage(text), delay)
      );
    } else {
      timersRef.current.forEach(clearTimeout);
      timersRef.current = [];
      setStage(null);
    }
    return () => {
      timersRef.current.forEach(clearTimeout);
    };
  }, [isLoading]);

  return stage;
}

/**
 * Extract the final segment from a slash- or backslash-delimited path.
 * @param {string} path - The path to process.
 * @return {string} The final path segment, or an empty string for a falsy path.
 */
function basename(path) {
  return (path || "").split("/").pop().split("\\").pop();
}

/**
 * Render an outfit item image with a placeholder fallback and optional lightbox viewing.
 * @param {Object} props - Component properties.
 * @param {Object} props.item - Outfit item data used to resolve and label the image.
 */
function ComboItemImage({ item }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [imageError, setImageError] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const filename = basename(item?.image_path);

  useEffect(() => {
    if (!filename) return undefined;

    let cancelled = false;
    getImageUrl(filename).then((url) => {
      if (!cancelled && url) {
        setImageUrl(url);
      } else if (!cancelled) {
        setImageError(true);
      }
    });

    return () => {
      cancelled = true;
    };
  }, [filename]);

  if (!imageUrl || imageError) {
    return (
      <div className="chat-combo-image-placeholder" aria-hidden="true">
        <span className="chat-combo-image-placeholder-icon">👕</span>
        <span className="chat-combo-image-placeholder-label">{item?.category || "Item"}</span>
      </div>
    );
  }

  return (
    <>
      <img
        className="chat-combo-image chat-combo-image-clickable"
        src={imageUrl}
        alt={item?.caption || item?.category || "Outfit item"}
        loading="lazy"
        onError={() => setImageError(true)}
        onClick={() => setLightboxOpen(true)}
        title="Click to enlarge"
      />
      {lightboxOpen && (
        <ImageLightbox
          src={imageUrl}
          alt={item?.caption || item?.category}
          onClose={() => setLightboxOpen(false)}
        />
      )}
    </>
  );
}

/**
 * Render the AI Stylist chat panel with conversation controls and outfit recommendations.
 * @param {Function} onCombosChange - Callback invoked when outfit combinations change.
 */
export default function ChatPanel({ onCombosChange }) {
  const {
    messages,
    pendingInterrupt,
    isLoading,
    error,
    send,
    resume,
    stop,
    reset,
  } = useChatState({ onCombosChange });

  const [isOpen, setIsOpen] = useState(() => (
    typeof window === "undefined" ? true : window.innerWidth >= 1080
  ));
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);
  const thinkingStage = useThinkingStage(isLoading);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, isLoading, pendingInterrupt]);

  const handleSend = (e) => {
    e.preventDefault();
    if (!input.trim() || isLoading) return;
    send(input.trim());
    setInput("");
  };

  const handleReset = () => {
    reset();
    setInput("");
  };

  // Floating toggle button when panel is closed
  if (!isOpen) {
    return (
      <button
        id="chat-toggle-open"
        className="chat-toggle-btn"
        onClick={() => setIsOpen(true)}
        aria-label="Open AI stylist chat"
        title="Open AI stylist chat"
      >
        <span className="chat-toggle-icon" aria-hidden="true">✦</span> Chat with AI Stylist
      </button>
    );
  }

  return (
    <div className="chat-panel" id="chat-panel">
      {/* Header */}
      <div className="chat-header">
        <h2>AI Stylist</h2>
        <div className="chat-header-actions">
          <button id="chat-reset-btn" onClick={handleReset} title="New conversation">
            New
          </button>
          <button
            id="chat-close-btn"
            onClick={() => setIsOpen(false)}
            aria-label="Close chat panel"
            title="Close chat panel"
          >
            X
          </button>
        </div>
      </div>

      {/* Messages */}
      <div className="chat-messages" id="chat-messages">
        {messages.length === 0 && !isLoading && (
          <div className="chat-empty">
            <span className="chat-empty-icon" aria-hidden="true">AI</span>
            <p>
              Describe what you're looking for - occasion, colors, style - and
              I'll curate outfits for you.
            </p>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i}>
            <div className={`chat-bubble ${msg.role}`}>
              {msg.content}
              {msg.guardrailsPassed && (
                <div className="chat-guardrail-badge" title="Input passed safety guardrails">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="20 6 9 17 4 12"></polyline>
                  </svg>
                  Guardrails Passed
                </div>
              )}
            </div>
            {/* Render combo cards inline after assistant messages that have them */}
            {msg.role === "assistant" && msg.combos && msg.combos.length > 0 && (
              <div className="chat-combos">
                {msg.combos.map((combo, ci) => (
                  <div className="chat-combo-card" key={combo.combo_id || ci}>
                    <div className="chat-combo-rank">
                      Outfit #{combo.combo_rank}
                    </div>
                    {(combo.items || []).slice(0, 3).map((item, ii) => (
                      <div className="chat-combo-item" key={item.product_id || ii}>
                        <ComboItemImage item={item} />
                        <div className="chat-combo-item-copy">
                          <strong className="chat-combo-item-name">
                            {item.caption || item.category || "Item"}
                          </strong>
                          <span className="chat-combo-item-meta">
                            {[item.category, item.colors?.join(", ")].filter(Boolean).join(" · ")}
                          </span>
                        </div>
                      </div>
                    ))}
                    <div className="chat-combo-rationale">
                      <strong>Rationale:</strong> {combo.rationale}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}

        {thinkingStage && (
          <div className="chat-bubble assistant chat-thinking-bubble">
            <span className="chat-thinking-text">{thinkingStage}</span>
            <span className="chat-loading-dots" aria-hidden="true">
              <span></span><span></span><span></span>
            </span>
          </div>
        )}

        {error && (
          <div className="chat-error">{error}</div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Input area - either the regular input or the interrupt card */}
      {pendingInterrupt ? (
        <InterruptCard
          question={pendingInterrupt.arguments?.question || "Could you tell me more?"}
          onSubmit={resume}
          isLoading={isLoading}
        />
      ) : (
        <form className="chat-input-bar" onSubmit={handleSend}>
          <input
            id="chat-message-input"
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe your style..."
            disabled={isLoading}
            autoComplete="off"
          />
          {isLoading ? (
            <button
              type="button"
              className="chat-stop-btn"
              onClick={stop}
              aria-label="Stop generation"
            >
              Stop
            </button>
          ) : (
            <button
              id="chat-send-btn"
              type="submit"
              className="chat-send-btn"
              disabled={!input.trim()}
            >
              Send
            </button>
          )}
        </form>
      )}
    </div>
  );
}
