// Lightweight API client for the AKIRS backend.
// The frontend is served from a separate static host, so use an absolute base URL.
const API_BASE = "http://localhost:8000";

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
  return res.json();
}

// GET /scraped/advertisers/ -> list of enriched advertisers
async function fetchAdvertisers() {
  return request("/scraped/advertisers/");
}

// POST /chatbot/chat -> { answer, sources, ... }
async function sendChat(question, collection = "akirs_businesses") {
  return request("/chatbot/chat", {
    method: "POST",
    body: JSON.stringify({ collection, question }),
  });
}

// POST /chatbot/ingest/from-scraper -> ingest scraped advertisers into the RAG store
async function ingestFromScraper(collection = "akirs_businesses") {
  return request("/chatbot/ingest/from-scraper", {
    method: "POST",
    body: JSON.stringify({ collection }),
  });
}

// POST /jobs/scrape -> trigger the background Celery worker
async function startScrapeJob(payload) {
  return request("/jobs/scrape", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// GET /jobs/{job_id} -> get job status and live counts
async function pollJobStatus(jobId) {
  return request(`/jobs/${jobId}`);
}

// POST /jobs/{job_id}/stop -> stop a running job
async function stopScrapeJob(jobId) {
  return request(`/jobs/${jobId}/stop`, { method: "POST" });
}

window.akirsApi = { API_BASE, fetchAdvertisers, sendChat, ingestFromScraper, startScrapeJob, pollJobStatus, stopScrapeJob };
