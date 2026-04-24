import "./StatusBar.css";

export default function StatusBar({ status, type }) {
  if (!status) return null;

  return (
    <div className={`status-bar ${type || ""}`}>
      {type === "loading" && <span className="status-spinner" />}
      <span>{status}</span>
    </div>
  );
}
