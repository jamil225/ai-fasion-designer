import { useEffect } from "react";
import { createPortal } from "react-dom";
import "./ImageLightbox.css";

/**
 * ImageLightbox
 *
 * Props:
 *   src      — image URL to display
 *   alt      — alt / caption text
 *   onClose  — called when the user dismisses the overlay
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
