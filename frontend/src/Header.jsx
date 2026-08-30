import UserMenu from "./UserMenu";
import CartButton from "./CartButton";
import "./Header.css";

export default function Header() {
  return (
    <header className="app-header">
      <div className="header-content">
        <div className="header-brand">
          <div className="logo-mark">
            <img src="/logo.jpg" alt="AI Fashion Logo" className="app-vip-logo" />
          </div>
          <div className="header-brand-info">
            <h1 className="header-title">
              ATELIER AI <span className="title-accent">Designer</span>
            </h1>
            <p className="header-subtitle">
              Vision-First Agentic Outfit Architecture
            </p>
          </div>
        </div>
        <div className="header-actions">
          <CartButton />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
