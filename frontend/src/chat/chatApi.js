// Chat API client — mirrors the fetch patterns in ../api.js
// Uses credentials: 'include' so the HttpOnly session cookie travels.

const JSON_HEADERS = { "Content-Type": "application/json" };

/**
 * Submits a new message to a chat thread.
 * @param {string} threadId - The identifier of the chat thread.
 * @param {string} text - The message content.
 * @param {AbortSignal} signal - The signal used to cancel the request.
 * @return {Promise<unknown>} The parsed chat response.
 * @throws {Error} If the request fails or the server returns an error response.
 */
export async function sendMessage(threadId, text, signal) {
  const response = await fetch("/v1/chat", {
    method: "POST",
    headers: JSON_HEADERS,
    credentials: "include",
    body: JSON.stringify({ thread_id: threadId, message: text }),
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}

/**
 * Resumes an interrupted chat thread with a user response.
 * @param {string} threadId - The identifier of the chat thread to resume.
 * @param {string} replyText - The response submitted to the interrupted chat.
 * @returns {Promise<Object>} The parsed chat response.
 * @throws {Error} If the request fails or the server returns an unsuccessful response.
 */
export async function sendResume(threadId, replyText, signal) {
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
    signal,
  });

  if (!response.ok) {
    const err = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(err.detail || response.statusText);
  }

  return response.json();
}

/**
 * Retrieves diagnostic information for a chat thread.
 * @param {string} threadId - The identifier of the chat thread.
 * @return {*} The thread's diagnostic information.
 * @throws {Error} If the request fails.
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
