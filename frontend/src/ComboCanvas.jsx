import { useState, useEffect } from "react";
import { getImageUrl } from "./api";
import ImageLightbox from "./ImageLightbox";
import "./ComboCanvas.css";

/**
 * Extract the final segment from a slash- or backslash-delimited path.
 * @param {string} path - The path whose final segment should be extracted.
 * @return {string} The final path segment, or an empty string when no path is provided.
 */
function basename(path) {
  return (path || "").split("/").pop().split("\\").pop();
}

/**
 * Renders an outfit item image with loading, error, placeholder, and lightbox states.
 * @param {Object} props - Component properties.
 * @param {Object} props.item - Outfit item data used to resolve and describe the image.
 * @returns {JSX.Element} The rendered image, placeholder, skeleton, or lightbox content.
 */
function ComboImage({ item }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState(false);
  const [lightboxOpen, setLightboxOpen] = useState(false);
  const filename = basename(item?.image_path);

  useEffect(() => {
    if (!filename) return;
    let cancelled = false;
    getImageUrl(filename).then((url) => {
      if (!cancelled) {
        if (url) setImageUrl(url);
        else setError(true);
      }
    });
    return () => { cancelled = true; };
  }, [filename]);

  if (error || !filename) {
    return (
      <div className="combo-img-placeholder">
        <span>👕</span>
        <span className="combo-img-placeholder-label">{item?.category || "Item"}</span>
      </div>
    );
  }

  if (!imageUrl) {
    return <div className="combo-img-skeleton" />;
  }

  return (
    <>
      <div
        className={`combo-img-wrapper ${loaded ? "loaded" : ""}`}
        onClick={() => setLightboxOpen(true)}
        title="Click to enlarge"
        style={{ cursor: "zoom-in" }}
      >
        <img
          className="combo-img"
          src={imageUrl}
          alt={item?.caption || item?.category || "Outfit item"}
          onLoad={() => setLoaded(true)}
          onError={() => setError(true)}
        />
        <div className="combo-img-zoom-hint" aria-hidden="true">⊕</div>
      </div>
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
 * Render a combo card with its items, metadata, caption, and rationale.
 * @param {Object} combo - The outfit combination to display.
 * @param {number} rank - The fallback display rank for the combination.
 */
function ComboCard({ combo, rank }) {
  const items = (combo.items || []).slice(0, 3);

  return (
    <article className="combo-card">
      <header className="combo-card-header">
        <span className="combo-card-rank">Outfit #{combo.combo_rank ?? rank}</span>
        {combo.occasion && (
          <span className="combo-card-occasion">{combo.occasion}</span>
        )}
      </header>

      {/* Image pair — side by side */}
      <div className={`combo-card-images count-${Math.min(items.length, 3)}`}>
        {items.map((item, i) => (
          <div key={item.product_id || i} className="combo-card-image-cell">
            <ComboImage item={item} />
            <div className="combo-card-image-meta">
              <span className="combo-card-item-category">{item.category || "—"}</span>
              {item.colors?.length > 0 && (
                <span className="combo-card-item-colors">
                  {item.colors.slice(0, 3).join(" · ")}
                </span>
              )}
            </div>
          </div>
        ))}
      </div>

      {/* Caption / title from first item */}
      {items[0]?.caption && (
        <p className="combo-card-caption">
          {items.map(it => it.caption).filter(Boolean).join(" + ")}
        </p>
      )}

      {/* Rationale */}
      {combo.rationale && (
        <p className="combo-card-rationale">
          <strong>Why this works: </strong>
          {combo.rationale}
        </p>
      )}
    </article>
  );
}

/**
 * Renders a grid of outfit combinations or an empty-state message.
 * @param {Array<Object>} combos - The outfit combinations to display.
 */
export default function ComboCanvas({ combos }) {
  if (!combos || combos.length === 0) {
    return (
      <div className="combo-empty">
        <div className="combo-empty-icon" aria-hidden="true">✦</div>
        <h2 className="combo-empty-title">Your outfits will appear here</h2>
        <p className="combo-empty-sub">
          Ask the AI Stylist on the right — describe an occasion, style, or
          colour, and it will curate matching outfits for you.
        </p>
      </div>
    );
  }

  return (
    <div className="combo-canvas">
      <div className="combo-canvas-grid">
        {combos.map((combo, i) => (
          <ComboCard key={combo.combo_id || i} combo={combo} rank={i + 1} />
        ))}
      </div>
    </div>
  );
}
