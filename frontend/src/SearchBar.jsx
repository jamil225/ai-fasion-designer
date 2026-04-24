import { useState, useRef, useEffect } from "react";
import "./SearchBar.css";

export default function SearchBar({ onSearch, onBrowse, isLoading }) {
  const [query, setQuery] = useState("");
  const inputRef = useRef(null);

  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (query.trim() && !isLoading) {
      onSearch(query.trim());
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") {
      handleSubmit(e);
    }
  };

  return (
    <div className="search-container">
      <form className="search-form" onSubmit={handleSubmit}>
        <div className="search-input-wrapper">
          <svg
            className="search-icon"
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <circle cx="11" cy="11" r="8" />
            <path d="m21 21-4.35-4.35" />
          </svg>
          <input
            ref={inputRef}
            id="search-input"
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search for fashion... e.g. red wedding saree, casual blue jacket"
            disabled={isLoading}
            autoComplete="off"
          />
          {query && (
            <button
              type="button"
              className="clear-btn"
              onClick={() => {
                setQuery("");
                inputRef.current?.focus();
              }}
              aria-label="Clear search"
            >
              ✕
            </button>
          )}
        </div>
        <button
          type="submit"
          id="search-btn"
          className="btn btn-primary"
          disabled={isLoading || !query.trim()}
        >
          {isLoading ? (
            <span className="btn-spinner" />
          ) : (
            <>Search</>
          )}
        </button>
        <button
          type="button"
          id="browse-btn"
          className="btn btn-secondary"
          onClick={onBrowse}
          disabled={isLoading}
        >
          Browse All
        </button>
      </form>
    </div>
  );
}
