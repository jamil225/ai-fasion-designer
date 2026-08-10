import { createContext, useContext, useState } from "react";

const CartContext = createContext(null);

export function CartProvider({ children }) {
  const [items, setItems] = useState([]);

  const addItems = (newItems) => {
    setItems((prev) => {
      const existingIds = new Set(prev.map((it) => it.product_id));
      const toAdd = (newItems || []).filter(
        (it) => it.product_id && !existingIds.has(it.product_id)
      );
      return [...prev, ...toAdd];
    });
  };

  const removeItem = (productId) => {
    setItems((prev) => prev.filter((it) => it.product_id !== productId));
  };

  const clearCart = () => setItems([]);

  return (
    <CartContext.Provider
      value={{ items, addItems, removeItem, clearCart, itemCount: items.length }}
    >
      {children}
    </CartContext.Provider>
  );
}

export function useCart() {
  const ctx = useContext(CartContext);
  if (!ctx) throw new Error("useCart must be used within a CartProvider");
  return ctx;
}
