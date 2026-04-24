import ProductCard from "./ProductCard";
import "./ResultsGrid.css";

export default function ResultsGrid({ results, isBrowseMode }) {
  if (!results || results.length === 0) {
    return null;
  }

  return (
    <div className="results-grid">
      {results.map((result, index) => (
        <ProductCard
          key={result.product_id || result.filename || index}
          result={result}
          index={index}
          isBrowseMode={isBrowseMode}
        />
      ))}
    </div>
  );
}
