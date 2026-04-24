import { useState, useEffect } from "react";
import { getImageUrl } from "./api";
import "./ProductCard.css";

export default function ProductCard({ result, index, isBrowseMode }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [imageError, setImageError] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);

  const attrs = result.matched_attributes || {};
  const filename = (result.image_path || result.filename || "")
    .split("/")
    .pop()
    .split("\\")
    .pop();
  const score = result.score != null ? (result.score * 100).toFixed(1) : null;
  const category = attrs.category || "—";
  const occasion = attrs.occasion || "—";
  const colors = Array.isArray(attrs.colors)
    ? attrs.colors
    : attrs.colors
      ? [attrs.colors]
      : [];
  const tags = Array.isArray(result.style_tags) ? result.style_tags : [];
  const caption = result.caption || "";

  useEffect(() => {
    if (!filename) return;

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

  return (
    <div
      className="product-card"
      style={{ animationDelay: `${index * 0.06}s` }}
    >
      <div className="card-image-container">
        {imageUrl && !imageError ? (
          <>
            {!imageLoaded && <div className="image-skeleton" />}
            <img
              src={imageUrl}
              alt={category}
              loading="lazy"
              className={`card-image ${imageLoaded ? "loaded" : ""}`}
              onLoad={() => setImageLoaded(true)}
              onError={() => setImageError(true)}
            />
          </>
        ) : (
          <div className="image-placeholder">
            <span>👗</span>
          </div>
        )}
        {score !== null && !isBrowseMode && (
          <div className="score-badge">
            {score}%
          </div>
        )}
      </div>

      <div className="card-body">
        {!isBrowseMode ? (
          <>
            <div className="card-meta">
              <div className="meta-item">
                <span className="meta-label">Category</span>
                <span className="meta-value">{category}</span>
              </div>
              <div className="meta-item">
                <span className="meta-label">Occasion</span>
                <span className="meta-value">{occasion}</span>
              </div>
            </div>

            {colors.length > 0 && (
              <div className="color-chips">
                {colors.map((color, i) => (
                  <span key={i} className="color-chip">
                    {color}
                  </span>
                ))}
              </div>
            )}

            {tags.length > 0 && (
              <div className="tag-list">
                {tags.slice(0, 5).map((tag, i) => (
                  <span key={i} className="tag-chip">
                    {tag}
                  </span>
                ))}
              </div>
            )}

            {caption && (
              <p className="card-caption">
                {caption.length > 100
                  ? caption.slice(0, 97) + "…"
                  : caption}
              </p>
            )}
          </>
        ) : (
          <div className="browse-filename">{filename}</div>
        )}
      </div>
    </div>
  );
}
