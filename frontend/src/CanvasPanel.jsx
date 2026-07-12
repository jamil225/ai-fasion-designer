import { useState, useRef, useEffect } from "react";
import SearchBar from "./SearchBar";
import StatusBar from "./StatusBar";
import ResultsGrid from "./ResultsGrid";
import EmptyState from "./EmptyState";
import ComboCanvas from "./ComboCanvas";
import "./CanvasPanel.css";

const TABS = [
  { id: "outfits", label: "✦ Outfits", ariaLabel: "AI outfit combinations" },
  { id: "catalog", label: "⊟ Catalog", ariaLabel: "Browse catalog" },
];

export default function CanvasPanel({
  combos,
  results,
  status,
  statusType,
  isLoading,
  hasSearched,
  isBrowseMode,
  onSearch,
  onBrowse,
}) {
  const [activeTab, setActiveTab] = useState("catalog");
  const outfitsRef = useRef(null);
  const catalogRef = useRef(null);

  // Auto-switch to Outfits tab when new combos arrive
  useEffect(() => {
    if (combos && combos.length > 0) {
      switchTab("outfits");
    }
  }, [combos]);

  function switchTab(newTab) {
    if (newTab === activeTab) return;

    const doSwitch = () => setActiveTab(newTab);

    if (!document.startViewTransition) {
      doSwitch();
      return;
    }

    document.startViewTransition({
      update: doSwitch,
      types: [newTab === "outfits" ? "backward" : "forward"],
    });
  }

  const showEmptyState = !hasSearched && results.length === 0;
  const showNoResults = hasSearched && !isLoading && results.length === 0;

  return (
    <div className="canvas-panel" role="main">
      {/* ── Tab bar ── */}
      <div className="canvas-tab-bar" role="tablist" aria-label="Canvas views">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            role="tab"
            id={`canvas-tab-${tab.id}`}
            aria-selected={activeTab === tab.id}
            aria-controls={`canvas-view-${tab.id}`}
            className={`canvas-tab-btn ${activeTab === tab.id ? "active" : ""}`}
            onClick={() => switchTab(tab.id)}
            aria-label={tab.ariaLabel}
          >
            {tab.label}
            {tab.id === "outfits" && combos?.length > 0 && (
              <span className="canvas-tab-badge">{combos.length}</span>
            )}
          </button>
        ))}
        <div className="canvas-tab-indicator-track">
          <div
            className="canvas-tab-indicator"
            style={{ transform: `translateX(${activeTab === "outfits" ? "0%" : "100%"})` }}
          />
        </div>
      </div>

      {/* ── Outfits view ── */}
      <div
        id="canvas-view-outfits"
        role="tabpanel"
        aria-labelledby="canvas-tab-outfits"
        className={`canvas-view outfits-view ${activeTab !== "outfits" ? "inactive" : ""}`}
        ref={outfitsRef}
        tabIndex={activeTab === "outfits" ? 0 : -1}
        aria-hidden={activeTab !== "outfits"}
      >
        <div className="canvas-scroll-area">
          <div className="canvas-scroll-hint canvas-scroll-hint--top" aria-hidden="true" />
          <ComboCanvas combos={combos} />
          <div className="canvas-scroll-hint canvas-scroll-hint--bottom" aria-hidden="true" />
        </div>
      </div>

      {/* ── Catalog view ── */}
      <div
        id="canvas-view-catalog"
        role="tabpanel"
        aria-labelledby="canvas-tab-catalog"
        className={`canvas-view catalog-view ${activeTab !== "catalog" ? "inactive" : ""}`}
        ref={catalogRef}
        tabIndex={activeTab === "catalog" ? 0 : -1}
        aria-hidden={activeTab !== "catalog"}
      >
        <SearchBar onSearch={onSearch} onBrowse={onBrowse} isLoading={isLoading} />
        <StatusBar status={status} type={statusType} />
        {showEmptyState && <EmptyState type="initial" onExampleClick={onSearch} />}
        {showNoResults && <EmptyState type="no-results" />}
        <div className="canvas-scroll-area">
          <div className="canvas-scroll-hint canvas-scroll-hint--top" aria-hidden="true" />
          <ResultsGrid results={results} isBrowseMode={isBrowseMode} />
          <div className="canvas-scroll-hint canvas-scroll-hint--bottom" aria-hidden="true" />
        </div>
      </div>
    </div>
  );
}
