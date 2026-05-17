import { useState } from "react";
import { AuthProvider, useAuth } from "./AuthContext";
import LoginPage from "./LoginPage";
import Header from "./Header";
import SearchBar from "./SearchBar";
import StatusBar from "./StatusBar";
import ResultsGrid from "./ResultsGrid";
import EmptyState from "./EmptyState";
import ChatPanel from "./chat/ChatPanel";
import { searchProducts, listImages } from "./api";
import "./App.css";

function Dashboard() {
  const [results, setResults] = useState([]);
  const [status, setStatus] = useState(null);
  const [statusType, setStatusType] = useState(null);
  const [isLoading, setIsLoading] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [isBrowseMode, setIsBrowseMode] = useState(false);

  const handleSearch = async (query) => {
    setIsLoading(true);
    setStatus(null);
    setStatusType("loading");
    setStatus("Searching…");
    setResults([]);
    setHasSearched(true);
    setIsBrowseMode(false);

    try {
      const t0 = performance.now();
      const data = await searchProducts(query, 10, false);
      const elapsed = Math.round(performance.now() - t0);
      const latency = data.latency_ms != null ? data.latency_ms : elapsed;

      if (!data.results || data.results.length === 0) {
        setStatus("No results found");
        setStatusType(null);
        setResults([]);
      } else {
        setStatus(
          `${data.results.length} result${data.results.length !== 1 ? "s" : ""} · ${latency}ms`
        );
        setStatusType("success");
        setResults(data.results);
      }
    } catch (err) {
      setStatus("Error: " + err.message);
      setStatusType("error");
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleBrowse = async () => {
    setIsLoading(true);
    setStatus("Loading images…");
    setStatusType("loading");
    setResults([]);
    setHasSearched(true);
    setIsBrowseMode(true);

    try {
      const data = await listImages();
      const filenames = data.filenames || [];

      if (filenames.length === 0) {
        setStatus("No images found in folder");
        setStatusType(null);
        setResults([]);
      } else {
        setStatus(`${filenames.length} images in catalog`);
        setStatusType("success");
        setResults(
          filenames.map((filename) => ({
            filename,
            image_path: filename,
          }))
        );
      }
    } catch (err) {
      setStatus("Error: " + err.message);
      setStatusType("error");
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  };

  const showEmptyState = !hasSearched && results.length === 0;
  const showNoResults = hasSearched && !isLoading && results.length === 0;

  return (
    <div className="app">
      <Header />
      <div className="app-workspace">
        <main className="main-content">
          <SearchBar
            onSearch={handleSearch}
            onBrowse={handleBrowse}
            isLoading={isLoading}
          />
          <StatusBar status={status} type={statusType} />
          {showEmptyState && <EmptyState type="initial" onExampleClick={handleSearch} />}
          {showNoResults && <EmptyState type="no-results" />}
          <ResultsGrid results={results} isBrowseMode={isBrowseMode} />
        </main>
        <ChatPanel />
      </div>
      <footer className="app-footer">
        <p>AI Fashion Designer · Powered by Gemini Vision + Pinecone</p>
      </footer>
    </div>
  );
}

function AppContent() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <div className="app-loading">
        <span className="app-loading-spinner" />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <LoginPage />;
  }

  return <Dashboard />;
}

export default function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  );
}
