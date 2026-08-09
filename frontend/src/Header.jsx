import UserMenu from "./UserMenu";
import CartButton from "./CartButton";
import "./Header.css";

export default function Header() {
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-brand">
          <div className="logo-mark">
            <span className="logo-icon">✦</span>
          </div>
          <h1 className="header-title">
            AI Fashion <span className="title-accent">Designer</span>
          </h1>
          <p className="header-subtitle">
            Vision-first garment search powered by Gemini + Pinecone
          </p>
        </div>
        <div className="header-actions">
          <CartButton />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
