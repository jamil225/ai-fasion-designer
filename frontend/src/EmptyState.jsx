import "./EmptyState.css";

const EXAMPLE_QUERIES = [
  "red bridal saree",
  "casual blue denim jacket",
  "elegant party wear",
  "floral summer dress",
];

export default function EmptyState({ type, onExampleClick }) {
  if (type === "no-results") {
    return (
      <div className="empty-state">
        <div className="empty-icon">🔍</div>
        <h3>No results found</h3>
        <p>Try different keywords or broaden your search</p>
      </div>
    );
  }

  return (
    <div className="empty-state initial">
      <div className="empty-icon">👗</div>
      <h3>Search your fashion catalog</h3>
      <p>
        Describe what you're looking for in natural language — colors, styles,
        occasions, or garment types
      </p>
      <div className="example-queries">
        {EXAMPLE_QUERIES.map((q) => (
          <button
            key={q}
            className="example-chip"
            onClick={() => onExampleClick?.(q)}
          >
            {q}
          </button>
        ))}
      </div>
    </div>
  );
}
