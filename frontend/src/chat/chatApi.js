// Chat API client — mirrors the fetch patterns in ../api.js
// Uses credentials: 'include' so the HttpOnly session cookie travels.

const JSON_HEADERS = { "Content-Type": "application/json" };

/**
 * POST /v1/chat — shape 1 (new message).
 */
export async function sendMessage(threadId, text) {
  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: JSON_HEADERS,
    credentials: "include",
    body: JSON.stringify({ thread_id: threadId, message: text }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}

/**
 * POST /v1/chat — shape 2 (resume after interrupt).
 */
export async function sendResume(threadId, replyText) {
  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: JSON_HEADERS,
    credentials: "include",
    body: JSON.stringify({
      thread_id: threadId,
      resume: {
        decisions: [{ type: "respond", message: replyText }],
      },
    }),
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}

/**
 * GET /v1/chat/threads/{threadId} — diagnostic.
 */
export async function getThread(threadId) {
  const response = await fetch(`/v1/chat/threads/${encodeURIComponent(threadId)}`, {
    credentials: "include",
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}
