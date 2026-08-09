import { useState, useEffect } from "react";
import { getImageUrl } from "./api";
import { useCart } from "./CartContext";
import "./CartPopup.css";

function basename(path) {
  return (path || "").split("/").pop().split("\\").pop();
}

function CartItemImage({ item }) {
  const [imageUrl, setImageUrl] = useState(null);
  const [error, setError] = useState(false);
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

  if (error || !filename || !imageUrl) {
    return (
      <div className="cart-item-img-placeholder">
        <span>👕</span>
      </div>
    );
  }

  return <img className="cart-item-img" src={imageUrl} alt={item?.caption || item?.category || "Cart item"} />;
}

export default function CartPopup({ onClose }) {
  const { items, removeItem } = useCart();
  const [orderPlaced, setOrderPlaced] = useState(false);

  return (
    <div className="cart-popup">
      <div className="cart-popup-header">
        <span>Your Cart {items.length > 0 && `(${items.length})`}</span>
        <button className="cart-popup-close" onClick={onClose} aria-label="Close cart">
          ✕
        </button>
      </div>

      {items.length === 0 ? (
        <div className="cart-popup-empty">Your cart is empty.</div>
      ) : (
        <div className="cart-popup-list">
          {items.map((item) => (
            <div className="cart-popup-item" key={item.product_id}>
              <CartItemImage item={item} />
              <div className="cart-popup-item-copy">
                <strong className="cart-popup-item-name">
                  {item.caption || item.category || "Item"}
                </strong>
                <span className="cart-popup-item-meta">
                  {[item.category, item.colors?.join(", ")].filter(Boolean).join(" · ")}
                </span>
              </div>
              <button
                className="cart-popup-item-remove"
                onClick={() => removeItem(item.product_id)}
                aria-label="Remove item"
              >
                ✕
              </button>
            </div>
          ))}
        </div>
      )}

      {items.length > 0 && (
        <div className="cart-popup-footer">
          {orderPlaced && (
            <div className="cart-popup-success">Order placed! 🎉</div>
          )}
          <button className="cart-popup-buy" onClick={() => setOrderPlaced(true)}>
            Buy Now
          </button>
        </div>
      )}
    </div>
  );
}
