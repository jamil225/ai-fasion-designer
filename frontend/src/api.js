// All API calls use credentials: 'include' so the browser
// automatically sends the HttpOnly session cookie.
// No tokens are stored in or read from JavaScript.

const JSON_HEADERS = { "Content-Type": "application/json" };

// --- Auth ---

export async function loginWithGoogle(credential) {
  const response = await fetch("/v1/auth/google", {
    method: "POST",
    headers: JSON_HEADERS,
    credentials: "include",
    body: JSON.stringify({ credential }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || "Login failed");
  }

  return response.json();
}

export async function fetchCurrentUser() {
  const response = await fetch("/v1/auth/me", {
    credentials: "include",
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

export async function logoutUser() {
  await fetch("/v1/auth/logout", {
    method: "POST",
    credentials: "include",
  });
}

// --- Search ---

export async function searchProducts(query, topK = 10, strictMode = false, filters = null) {
  const body = {
    query,
    top_k: topK,
    strict_mode: strictMode,
  };
  if (filters) {
    body.filters = filters;
  }

  const response = await fetch("/v1/search", {
    method: "POST",
    headers: JSON_HEADERS,
    credentials: "include",
    body: JSON.stringify(body),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}

// --- Images ---

export async function listImages() {
  const response = await fetch("/v1/images", {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error(response.statusText);
  }

  return response.json();
}

export async function getImageUrl(filename) {
  const response = await fetch(`/v1/images/${encodeURIComponent(filename)}`, {
    credentials: "include",
  });

  if (!response.ok) {
    return null;
  }

  const blob = await response.blob();
  return URL.createObjectURL(blob);
}

// --- Health ---

export async function checkHealth() {
  const response = await fetch("/v1/health");
  if (!response.ok) {
    throw new Error("Backend unreachable");
  }
  return response.json();
}

// --- Ingestion ---

export async function startIngestion(mode = "full") {
  const response = await fetch("/v1/ingest/start", {
    method: "POST",
    headers: JSON_HEADERS,
    credentials: "include",
    body: JSON.stringify({ mode }),
  });

  const data = await response.json();
  if (!response.ok) {
    throw new Error(data.detail || response.statusText);
  }

  return data;
}

export async function getIngestionStatus(jobId) {
  const response = await fetch(`/v1/ingest/status/${jobId}`, {
    credentials: "include",
  });

  if (!response.ok) {
    throw new Error("Job not found");
  }

  return response.json();
}
