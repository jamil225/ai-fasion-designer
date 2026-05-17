import { useState, useRef, useEffect } from "react";
import { useChatState } from "./chatState";
import InterruptCard from "./InterruptCard";
import { getImageUrl } from "../api";
import "./ChatPanel.css";

function basename(path) {
  return (path || "").split("/").pop().split("\\").pop();
}

function ComboItemImage({ item }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [imageError, setImageError] = useState(false);
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
        IMG
      </div>
    );
  }

  return (
    <img
      className="chat-combo-image"
      src={imageUrl}
      alt={item?.category || "Outfit item"}
      loading="lazy"
      onError={() => setImageError(true)}
    />
  );
}

/**
 * ChatPanel - right-side rail docked into the existing search screen.
 * Self-contained: does NOT reuse ResultsGrid or ProductCard.
 */
export default function ChatPanel() {
  const {
    messages,
    pendingInterrupt,
    isLoading,
    error,
    send,
    resume,
    reset,
  } = useChatState();

  const [isOpen, setIsOpen] = useState(() => (
    typeof window === "undefined" ? true : window.innerWidth >= 1080
  ));
  const [input, setInput] = useState("");
  const messagesEndRef = useRef(null);

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
        Chat
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
                          <strong>{item.category || "Item"}</strong>
                          {item.colors?.length > 0 && (
                            <span>{item.colors.join(", ")}</span>
                          )}
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

        {isLoading && (
          <div className="chat-loading">
            <span className="chat-loading-dots">
              <span></span><span></span><span></span>
            </span>
            Thinking...
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
          <button
            id="chat-send-btn"
            type="submit"
            className="chat-send-btn"
            disabled={!input.trim() || isLoading}
          >
            Send
          </button>
        </form>
      )}
    </div>
  );
}
