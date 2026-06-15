// Lightweight API client for the AKIRS backend.
// The frontend never reads akirs.db directly; it loads database records through
// these backend endpoints so the same UI works locally and when served at /ui.
(function () {
function resolveApiBase() {
  if (window.AKIRS_API_BASE) return window.AKIRS_API_BASE;
  if (window.location.pathname.startsWith("/ui")) return "";
  return "http://127.0.0.1:8000";
}

const API_BASE = resolveApiBase();

async function request(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body && body.detail) detail = body.detail;
    } catch (_) {
      /* response had no JSON body */
    }
    throw new Error(detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

// GET /scraped/advertisers/ -> list of enriched advertisers
async function fetchAdvertisers() {
  return request("/scraped/advertisers/");
}

// GET /taxation/entities -> list of classified taxable entities
async function fetchTaxableEntities() {
  return request("/taxation/entities");
}

async function fetchJobs() {
  return request("/jobs");
}

async function fetchJob(jobId) {
  return request(`/jobs/${jobId}`);
}

async function pauseJob(jobId) {
  return request(`/jobs/${jobId}/pause`, { method: "POST" });
}

async function resumeJob(jobId) {
  return request(`/jobs/${jobId}/resume`, { method: "POST" });
}

async function stopJob(jobId) {
  return request(`/jobs/${jobId}/stop`, { method: "POST" });
}

async function deleteJob(jobId) {
  return request(`/jobs/${jobId}`, { method: "DELETE" });
}

// POST /chatbot/chat -> { answer, sources, collection, retrieved_count, elapsed_ms }
async function sendChat(question, collection = "akirs_tax") {
  return request("/chatbot/chat", {
    method: "POST",
    body: JSON.stringify({ question, collection }),
  });
}

// GET /chatbot/health -> { status, llm_ok, model, collections, collection_counts }
async function chatbotHealth() {
  return request("/chatbot/health");
}

window.akirsApi = {
  API_BASE,
  fetchAdvertisers,
  fetchTaxableEntities,
  fetchJobs,
  fetchJob,
  pauseJob,
  resumeJob,
  stopJob,
  deleteJob,
  sendChat,
  chatbotHealth,
};
})();
