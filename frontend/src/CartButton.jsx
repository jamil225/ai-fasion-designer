import { useState, useRef, useEffect } from "react";
import { useCart } from "./CartContext";
import CartPopup from "./CartPopup";
import "./CartButton.css";

export default function CartButton() {
  const { itemCount } = useCart();
  const [isOpen, setIsOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (ref.current && !ref.current.contains(e.target)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div className="cart-button-wrap" ref={ref}>
      <button
        className="cart-button-trigger"
        onClick={() => setIsOpen((open) => !open)}
        aria-label="Cart"
      >
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="9" cy="21" r="1"></circle>
          <circle cx="20" cy="21" r="1"></circle>
          <path d="M1 1h4l2.68 13.39a2 2 0 0 0 2 1.61h9.72a2 2 0 0 0 2-1.61L23 6H6"></path>
        </svg>
        {itemCount > 0 && <span className="cart-button-badge">{itemCount}</span>}
      </button>

      {isOpen && <CartPopup onClose={() => setIsOpen(false)} />}
    </div>
  );
}
