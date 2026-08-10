import { useEffect } from "react";
import { createPortal } from "react-dom";
import "./ImageLightbox.css";

/**
 * Displays an image preview in a modal overlay.
 *
 * The overlay can be dismissed by clicking its background, pressing Escape, or
 * activating the close button. Background scrolling is disabled while it is open.
 *
 * @param {string} src - URL of the image to display.
 * @param {string} [alt] - Alternative text and optional caption for the image.
 * @param {Function} onClose - Callback invoked when the overlay is dismissed.
 * @returns {React.ReactPortal} The image preview overlay rendered into the document body.
 */
export default function ImageLightbox({ src, alt, onClose }) {
  // Close on Escape key
  useEffect(() => {
    const handler = (e) => { if (e.key === "Escape") onClose(); };
    document.addEventListener("keydown", handler);
    return () => document.removeEventListener("keydown", handler);
  }, [onClose]);

  // Prevent body scroll while open
  useEffect(() => {
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = ""; };
  }, []);

  return createPortal(
    <div
      className="lightbox-overlay"
      role="dialog"
      aria-modal="true"
      aria-label="Image preview"
      onClick={onClose}
    >
      <button className="lightbox-close" onClick={onClose} aria-label="Close preview">
        ✕
      </button>

      <div className="lightbox-content" onClick={(e) => e.stopPropagation()}>
        <img
          className="lightbox-image"
          src={src}
          alt={alt || "Product image"}
        />
        {alt && (
          <p className="lightbox-caption">{alt}</p>
        )}
      </div>
    </div>,
    document.body
  );
}
