function resolveApiBase() {
  if (window.AKIRS_API_BASE) return window.AKIRS_API_BASE;
  if (window.location.pathname.startsWith("/ui")) return "";
  return "http://127.0.0.1:8000";
}

const APP_API_BASE = resolveApiBase();

const defaultConfig = {
  country: "Nigeria",
  state: "Akwa Ibom",
  city: "Uyo",
  query: "restaurant",
};

const profiles = [
  {
    name: "Ibom Fresh Foods",
    owner: "Daniel Akpan",
    platform: "Facebook",
    verified: true,
    followers: 18420,
    following: 312,
    engagement: 86,
    category: "Local Services",
    industry: "Restaurant",
    location: "Uyo, Akwa Ibom",
    website: "ibomfresh.example",
    contact: "hello@ibomfresh.example",
    found: "2026-05-30",
    reviewer: "Ada M.",
    status: "Pending Review",
    risk: 82,
    relevance: 94,
  },
  {
    name: "Eket Beauty Studio",
    owner: "Maya Udo",
    platform: "Instagram",
    verified: true,
    followers: 64200,
    following: 980,
    engagement: 91,
    category: "Business Owners",
    industry: "Beauty",
    location: "Eket, Akwa Ibom",
    website: "eketbeauty.example",
    contact: "+234 802 014 8840",
    found: "2026-05-29",
    reviewer: "Chris N.",
    status: "Ready To Contact",
    risk: 76,
    relevance: 97,
  },
  {
    name: "Northline Builders",
    owner: "Marcus Udofia",
    platform: "LinkedIn",
    verified: false,
    followers: 12880,
    following: 421,
    engagement: 73,
    category: "Companies",
    industry: "Construction",
    location: "Ikot Ekpene, Akwa Ibom",
    website: "northlinebuilders.example",
    contact: "contact form",
    found: "2026-05-28",
    reviewer: "Ada M.",
    status: "Needs More Information",
    risk: 69,
    relevance: 89,
  },
  {
    name: "Spark Auto Mechanics",
    owner: "Elijah Bassey",
    platform: "TikTok",
    verified: false,
    followers: 39210,
    following: 205,
    engagement: 88,
    category: "Entrepreneurs",
    industry: "Auto Repair",
    location: "Uyo, Akwa Ibom",
    website: "",
    contact: "DM available",
    found: "2026-05-27",
    reviewer: "Nora P.",
    status: "Rejected",
    risk: 43,
    relevance: 78,
  },
  {
    name: "Marina Grill House",
    owner: "Olivia Etim",
    platform: "X/Twitter",
    verified: true,
    followers: 23100,
    following: 744,
    engagement: 80,
    category: "Business Pages",
    industry: "Restaurant",
    location: "Oron, Akwa Ibom",
    website: "marinagrill.example",
    contact: "bookings@marinagrill.example",
    found: "2026-05-26",
    reviewer: "Chris N.",
    status: "Ready To Contact",
    risk: 71,
    relevance: 92,
  },
];

const activityLog = [
  ["12:18:44", "Browser", "Success", "Hidden browser launched with residential proxy pool."],
  ["12:19:03", "Search", "Running", `Query: restaurants near Uyo, Akwa Ibom with contact links.`],
  ["12:19:41", "Lead", "Success", "Collected Ibom Fresh Foods with website and email."],
  ["12:20:08", "Queue", "Warning", "18 leads require duplicate checks."],
  ["12:20:55", "Outreach", "Success", "Contact list prepared for tax revenue follow-up."],
];

let state = { isLoading: false, jobs: [], currentJob: null, user: null, profiles: [], taxable: [], activityLog: activityLog };

const app = document.querySelector("#app");

function signOut() {
  window.localStorage.removeItem("akirs.user");
  window.location.reload();
}
const drawerRoot = document.querySelector("#drawer-root");
const authRoot = document.querySelector("#auth-root");

function icon(name) {
  return `<span class="material-symbols-outlined">${name}</span>`;
}

function number(value) {
  return Number(value || 0).toLocaleString();
}

function addActivity(type, status, message) {
  const time = new Date().toLocaleTimeString([], { hour12: false });
  state.activityLog = [[time, type, status, message], ...state.activityLog].slice(0, 20);
  render();
}

function activeJobs() {
  return state.jobs.filter((job) => ["queued", "running", "paused"].includes(job.status));
}

function isScraperActive(job = state.currentJob) {
  return Boolean(job && ["queued", "running"].includes(job.status));
}

function isJobControllable(job = state.currentJob) {
  return Boolean(job && ["queued", "running", "paused"].includes(job.status));
}

async function apiFetch(path, options = {}) {
  const response = await fetch(`${APP_API_BASE}${path}`, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    const detail = await response.text();
    throw new Error(detail || `${response.status} ${response.statusText}`);
  }

  return response.status === 204 ? null : response.json();
}

function readStoredUser() {
  try {
    return JSON.parse(window.localStorage.getItem("akirs.user") || "null");
  } catch {
    return null;
  }
}

function initials(value) {
  return String(value || "--")
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase())
    .join("") || "--";
}

function mapTaxableEntity(entity) {
  return {
    id: entity.advertiser_id,
    name: entity.legal_name || `Advertiser ${entity.advertiser_id}`,
    owner: entity.entity_type || "Unknown",
    platform: "Social",
    verified: true,
    followers: 0,
    following: 0,
    engagement: 0,
    category: "Taxable Entity",
    industry: entity.entity_type || "Business",
    location: entity.address || defaultConfig.state,
    website: "",
    contact: [entity.emails, entity.phones].filter(Boolean).join(" / ") || "Not discovered",
    found: "Recently assessed",
    reviewer: "Tax classifier",
    status: "Ready To Contact",
    risk: Math.round((entity.taxable_score || 0) * 100),
    relevance: Math.round((entity.taxable_score || 0) * 100),
    reasoning: entity.reasoning || "",
  };
}

function formatDate(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "Not recorded" : date.toISOString().slice(0, 10);
}

function formatDateTime(value) {
  if (!value) return "Not recorded";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Not recorded";
  return date.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function runtimeLabel(job) {
  if (!job?.started_at) return "00:00";
  const start = new Date(job.started_at).getTime();
  const end = job.completed_at ? new Date(job.completed_at).getTime() : Date.now();
  if (Number.isNaN(start) || Number.isNaN(end) || end < start) return "00:00";
  const totalSeconds = Math.floor((end - start) / 1000);
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return hours
    ? `${hours}h ${String(minutes).padStart(2, "0")}m`
    : `${String(minutes).padStart(2, "0")}:${String(seconds).padStart(2, "0")}`;
}

function emptyState(title, body) {
  return `
    <div class="empty-state">
      ${icon("database")}
      <strong>${escapeHtml(title)}</strong>
      <p class="muted">${escapeHtml(body)}</p>
    </div>
  `;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[c]);
}

function capitalize(value) {
  return value ? value.charAt(0).toUpperCase() + value.slice(1) : value;
}

// Adapt an enriched advertiser from the API to the shape the render helpers expect.
function mapAdvertiser(a) {
  const socialLinks = a.social_links || [];
  const platforms = (a.platforms || []).map(capitalize);
  const website = (socialLinks.find((l) => !/facebook\.com/i.test(l.url)) || {}).url || "";
  const email = (a.emails || [])[0];
  const phone = (a.phones || [])[0];
  return {
    id: a.id,
    name: a.name || a.fb_url,
    owner: "—",
    platform: platforms[0] || "Facebook",
    platforms,
    verified: false,
    followers: a.followers ?? 0,
    following: 0,
    engagement: 0,
    category: "—",
    industry: "—",
    location: (a.addresses || [])[0] || "—",
    website,
    fbUrl: a.fb_url,
    socialLinks,
    emails: a.emails || [],
    phones: a.phones || [],
    addresses: a.addresses || [],
    sources: a.sources || [],
    contact: email || phone || "Not found",
    found: (a.first_seen || "").slice(0, 10),
    reviewer: "—",
    status: "Pending Review",
    risk: 0,
    relevance: 0,
  };
}

async function loadData() {
  if (!window.akirsApi) return;
  dataState = "loading";
  dataError = null;
  state.isLoading = true;
  render();
  try {
    const raw = await window.akirsApi.fetchAdvertisers();
    state.profiles = raw.map(mapAdvertiser);
    const taxableRaw = await window.akirsApi.fetchTaxableEntities();
    state.taxable = taxableRaw.map(mapAdvertiser);
    dataState = state.profiles.length ? "ready" : "empty";
  } catch (error) {
    dataError = error.message;
    dataState = "error";
  } finally {
    state.isLoading = false;
  }
  render();
}

async function loadJobs(shouldRender = true) {
  if (!window.akirsApi?.fetchJobs) return;
  try {
    state.jobs = await window.akirsApi.fetchJobs();
    if (!state.currentJob && state.jobs.length) {
      state.currentJob = state.jobs[0];
    } else if (state.currentJob) {
      const fresh = state.jobs.find((job) => job.job_id === state.currentJob.job_id);
      if (fresh) state.currentJob = fresh;
    }
  } catch (error) {
    addActivity("Jobs", "Warning", `Could not load scraper jobs: ${error.message}`);
  }
  if (shouldRender) render();
}

function dataBanner() {
  if (dataState === "loading")
    return `<div class="data-banner">${icon("hourglass_top")} Loading scraped data…</div>`;
  if (dataState === "empty")
    return `<div class="data-banner">${icon("inbox")} No scraped advertisers yet. Run the scraper to populate this view.</div>`;
  if (dataState === "error")
    return `<div class="data-banner data-banner--error">${icon("error")} Couldn't reach the API at ${escapeHtml(window.akirsApi.API_BASE)} — is the backend running? <small>${escapeHtml(dataError || "")}</small></div>`;
  return "";
}


function getRoute() {
  return window.location.hash.replace("#/", "") || "dashboard";
}

function setActiveNav(route) {
  document.querySelectorAll("[data-route]").forEach((link) => {
    link.classList.toggle("is-active", link.dataset.route === route);
  });
}

function render() {
  const route = getRoute();
  const pages = {
    dashboard: renderDashboard,
    scraper: renderScraper,
    results: renderResults,
    review: renderReview,
    taxable: renderTaxable,
    analytics: renderAnalytics,
    settings: renderSettings,
  };

  const activeRoute = pages[route] ? route : "dashboard";
  setActiveNav(activeRoute);
  const dataRoutes = ["dashboard", "results", "review", "taxable", "analytics"];
  const banner = dataRoutes.includes(activeRoute) ? dataBanner() : "";
  app.innerHTML = banner + (pages[route] || renderDashboard)();
  app.focus({ preventScroll: true });
  renderAuthPanel();
  updateAuthChrome();
  updateTopbarStatus();
  renderAuthOverlay();
  bindPageEvents(route);
}

function updateAuthChrome() {
  const user = state.user;
  const displayName = user?.display_name || "Not signed in";
  const username = user?.username ? `${user.username}@akirs.local` : "Login required";
  const avatar = initials(displayName);

  const profileAvatar = document.querySelector("#profile-avatar");
  if (profileAvatar) profileAvatar.textContent = avatar;
  const panelAvatar = document.querySelector("#panel-avatar");
  if (panelAvatar) panelAvatar.textContent = avatar;
  const profileName = document.querySelector("#profile-name");
  if (profileName) profileName.textContent = displayName;
  const panelName = document.querySelector("#panel-name");
  if (panelName) panelName.textContent = displayName;
  const panelUsername = document.querySelector("#panel-username");
  if (panelUsername) panelUsername.textContent = username;
  document.body.classList.toggle("is-auth-locked", !user);
}

function updateTopbarStatus() {
  const runningCount = activeJobs().length;
  const browserChip = document.querySelector("#browser-status-chip");
  const jobsChip = document.querySelector("#running-jobs-chip");
  const active = runningCount > 0 || isScraperActive();

  if (browserChip) {
    browserChip.classList.toggle("is-active", active);
    browserChip.classList.toggle("is-idle", !active);
    browserChip.innerHTML = `<span></span> ${active ? "Scraper Active" : "Browser Idle"}`;
  }

  if (jobsChip) {
    const label = runningCount === 1 ? "Running Job" : "Running Jobs";
    jobsChip.textContent = `${runningCount} ${label}`;
  }
}

function renderAuthPanel() {
  const panel = document.querySelector("#auth-panel");
  if (!panel) return;

  if (state.user) {
    const displayName = state.user.display_name || "Not signed in";
    const username = state.user.username ? `${state.user.username}@akirs.local` : "Login required";
    const avatar = initials(displayName);

    panel.innerHTML = `
      <div class="auth-panel__header">
        <span id="panel-avatar" class="profile-button__avatar">${avatar}</span>
        <div>
          <strong id="panel-name">${escapeHtml(displayName)}</strong>
          <small id="panel-username">${escapeHtml(username)}</small>
        </div>
      </div>
      <button class="button button--block" type="button">
        <span class="material-symbols-outlined">manage_accounts</span>
        Profile
      </button>
      <button id="sign-out" class="button button--block" type="button">
        <span class="material-symbols-outlined">logout</span>
        Sign Out
      </button>
    `;

    panel.querySelector("#sign-out")?.addEventListener("click", signOut);
  } else {
    panel.innerHTML = `
      <form id="panel-login-form" class="login-card" style="max-width:320px; padding:12px;">
        <div class="login-card__intro login-card__intro--compact">
          <div class="login-card__mark">${icon("lock")}</div>
          <div>
            <strong>Sign in</strong>
            <p class="muted">Use your AKIRS operator account.</p>
          </div>
        </div>
        <label style="margin-top:8px;">
           <span class="label">Username</span>
           <input name="username" type="text" autocomplete="username" required />
        </label>
          <label>
           <span class="label">Password</span>
           <input name="password" type="password" autocomplete="current-password" required />
        </label>
        <button class="button button--primary button--block" type="submit">${icon("login")} Sign In</button>
        <p class="login-card__hint">Local demo: <strong>user1</strong> / <strong>user1</strong></p>
        <button id="open-full-login" class="button button--block" type="button">Open full sign-in</button>
      </form>
    `;

    panel.querySelector("#panel-login-form")?.addEventListener("submit", login);
    panel.querySelector("#open-full-login")?.addEventListener("click", () => {
      renderAuthOverlay();
      document.querySelector('#login-form input[name="username"]')?.focus();
    });
  }
}

function renderAuthOverlay(message = "") {
  if (!authRoot) return;
  if (state.user) {
    authRoot.innerHTML = "";
    return;
  }

  authRoot.innerHTML = `
    <div class="auth-gate" role="dialog" aria-modal="true" aria-label="Sign in">
      <form id="login-form" class="login-card">
        <div class="login-card__intro">
          <div class="login-card__mark">${icon("lock")}</div>
          <div>
            <span class="eyebrow">Secure workspace</span>
            <h1>AKIRS Scraper</h1>
            <p class="muted">Sign in to view scraper records from the backend database.</p>
          </div>
        </div>
        <label>
           <span class="label">Username</span>
           <input name="username" type="text" autocomplete="username" required />
        </label>
        <label>
           <span class="label">Password</span>
           <input name="password" type="password" autocomplete="current-password" required />
        </label>
        <p class="login-card__hint">Local demo account: <strong>user1</strong> / <strong>user1</strong></p>
        ${message ? `<p class="form-error">${escapeHtml(message)}</p>` : ""}
        <button class="button button--primary button--block" type="submit">${icon("login")} Sign In</button>
      </form>
    </div>
  `;

  authRoot.querySelector("#login-form")?.addEventListener("submit", login);
}

function pageHeader(title, subtitle, actions = "") {
  return `
    <div class="page-heading">
      <div>
        <h1>${title}</h1>
        <p class="muted">${subtitle}</p>
      </div>
      <div class="toolbar">${actions}</div>
    </div>
  `;
}

function metric(label, value, iconName, trend = "", modifier = "") {
  return `
    <article class="stat-card metric-card ${modifier}">
      <div class="metric-card__top">
        <span class="eyebrow">${label}</span>
        ${icon(iconName)}
      </div>
      <strong>${value}</strong>
      ${trend ? `<small>${trend}</small>` : ""}
    </article>
  `;
}

function renderDashboard() {
  const profiles = state.profiles;
  const readyCount = state.taxable.length;
  const runningJobs = activeJobs().length;

  return `
    <section class="page">
      ${pageHeader(
        "Dashboard",
        "Operational overview for finding business contacts and preparing tax revenue outreach.",
        `<a class="button button--primary" href="#/scraper">${icon("play_arrow")} Launch Scraper</a>
         <button class="button" type="button" data-refresh-data>${icon("refresh")} Refresh Data</button>`,
      )}

      <div class="stats-grid">
        ${metric("Leads Collected", number(profiles.length), "group", state.isLoading ? "Loading backend data" : "From scraper database")}
        ${metric("Businesses Identified", number(profiles.length), "storefront", "Scraped advertisers")}
        ${metric("Outreach Ready", number(readyCount), "fact_check", "Taxable entities")}
        ${metric("Active Jobs", number(runningJobs), "settings_remote", state.currentJob?.status || "No active job", runningJobs ? "is-highlighted" : "")}
      </div>

      <div class="dashboard-grid">
        <section class="panel span-8">
          <div class="panel__header">
            <h2>${icon("history")} Recent Discoveries</h2>
            <a class="button" href="#/results">Open Results</a>
          </div>
          ${profiles.length ? profileTable(profiles.slice(0, 4), false) : emptyState("No scraper results yet", "Start a scrape job to collect advertisers from the backend.")}
        </section>
        <section class="panel span-4">
          <div class="panel__header"><h2>${icon("bolt")} Quick Actions</h2></div>
          <div class="list-stack">
            ${quickAction("Start new scrape", "Open login browser, then queue scraper job", "play_circle", "#/scraper")}
            ${quickAction("Review pending leads", "Verify contact details before outreach", "rule", "#/review")}
            ${quickAction("Contact taxable businesses", "Open verified contacts ready for tax payment follow-up", "contact_mail", "#/taxable")}
          </div>
        </section>
        <section class="panel span-12">
          <div class="panel__header">
            <h2>${icon("receipt_long")} Live Activity Log</h2>
            <span class="status-chip ${runningJobs ? "is-active" : "is-idle"}"><span></span> ${runningJobs ? "Scraper Active" : "Idle"}</span>
          </div>
          ${activityTable()}
        </section>
      </div>
    </section>
  `;
}

function quickAction(title, body, iconName, href) {
  return `
    <a class="quick-action" href="${href}">
      <span>${icon(iconName)}</span>
      <div><strong>${title}</strong><p class="muted">${body}</p></div>
    </a>
  `;
}

function renderScraper() {
  const job = state.currentJob;
  const keywords = defaultConfig.keywords.split(",")[0].trim();

  return `
    <section class="page">
      ${pageHeader(
        "Scraper Control Center",
        "Configure platform searches, launch jobs, and monitor the hidden browser worker.",
        `<button id="start-scraping" class="button button--primary" type="button">${icon("play_arrow")} Start Scraping</button>
         <button class="button" type="button" data-toast="Job paused">${icon("pause")} Pause</button>
         <button class="button" type="button" data-toast="Job resumed">${icon("resume")} Resume</button>
         <button class="button button--danger" type="button" data-confirm="Stop the active scraper job?">${icon("stop")} Stop</button>`,
      )}

      <div class="dashboard-grid">
        <section class="panel span-5">
          <div class="panel__header"><h2>${icon("tune")} Scraper Configuration</h2></div>
          <form id="scraper-config" class="config-form">
            ${selectField("Platform", ["Facebook", "Instagram", "LinkedIn", "X/Twitter", "TikTok", "Other"], "platform")}
            ${selectField("Search Type", ["All", "Business Owners", "Business Pages", "Companies", "Entrepreneurs", "Local Services"], "search_type")}
            <div class="form-grid">
              ${inputField("Target Country", defaultConfig.country, "country")}
              ${staticField("Target State", defaultConfig.state)}
              ${inputField("City", defaultConfig.city, "city")}
            </div>
            ${inputField("Keywords", defaultConfig.keywords, "keywords")}
            <label class="range-field">
              <span class="range-field__top">
                <span class="label">Thread Count</span>
                <output id="thread-count-value" for="thread-count">8 threads</output>
              </span>
              <input id="thread-count" type="range" min="1" max="12" value="8" list="thread-count-marks" />
              <datalist id="thread-count-marks">
                <option value="1"></option>
                <option value="4"></option>
                <option value="8"></option>
                <option value="12"></option>
              </datalist>
            </label>
          </form>
        </section>

        <section class="span-7">
          <div class="kpi-grid">
            ${metric("Browser Status", job?.status || "Idle", "desktop_windows", job?.celery_task_id ? "Celery worker queued" : "Login browser opens first")}
            ${metric("Leads Found", number(job?.advertiser_count || 0), "group_add", "Advertisers saved")}
            ${metric("Ads Found", number(job?.ad_count || 0), "travel_explore", "From active job")}
            ${metric("Job ID", job?.job_id || "-", "tag", job?.created_at ? formatDate(job.created_at) : "No job queued")}
            ${metric("Job Status", job?.status || "Idle", "queue", job?.error || "No backend errors")}
            ${metric("Running Jobs", number(activeJobs().length), "memory", "From backend jobs")}
          </div>
        </section>

        <section class="panel span-12">
          <div class="panel__header"><h2>${icon("receipt_long")} Scraping Activity Log</h2></div>
          ${activityTable()}
        </section>
      </div>
    </section>
  `;
}

function scraperSignalPanel() {
  const job = state.currentJob;
  const active = isScraperActive(job);
  const paused = job?.status === "paused";
  const controllable = isJobControllable(job);
  const jobs = state.jobs;
  const params = job?.params || {};
  const jobTitle = job ? `Job #${job.job_id}` : "No scraper job selected";
  const locationText = (params.locations || []).join(", ") || "Default geography";

  return `
    <section class="scraper-signal ${active ? "is-active" : ""} ${paused ? "is-paused" : ""} ${!active && !paused ? "is-idle" : ""}" aria-live="polite">
      <div class="signal-monitor">
        <div class="signal-monitor__screen">
          <div class="gear-field">
            <div class="gear gear--outer">
              <div class="gear gear--inner gear--inner-one"></div>
              <div class="gear gear--inner gear--inner-two"></div>
              <div class="gear gear--inner gear--inner-three"></div>
            </div>
          </div>
        </div>
        <div class="signal-monitor__meta">
          <span class="eyebrow">${active ? "Scraper engine running" : paused ? "Scraper paused" : "Scraper engine idle"}</span>
          <strong>${escapeHtml(jobTitle)}</strong>
          <small>${escapeHtml(job?.status || "idle")} ${job?.error ? `- ${escapeHtml(job.error)}` : ""}</small>
        </div>
      </div>

      <div class="signal-details">
        <div><span class="label">Location</span><strong>${escapeHtml(locationText)}</strong></div>
        <div><span class="label">Runtime</span><strong>${escapeHtml(runtimeLabel(job))}</strong></div>
        <div><span class="label">Started</span><strong>${escapeHtml(job?.started_at ? formatDateTime(job.started_at) : "Not started")}</strong></div>
        <div><span class="label">Ads</span><strong>${number(job?.ad_count || 0)}</strong></div>
        <div><span class="label">Advertisers</span><strong>${number(job?.advertiser_count || 0)}</strong></div>
      </div>

      <div class="job-switcher">
        <div class="job-switcher__top">
          <strong>Scraping Jobs</strong>
        </div>
        <div class="scraper-controls">
          ${
            controllable
              ? `<button class="button button--danger" type="button" data-stop-job="${job.job_id}">${icon("stop")} End</button>
                 ${
                   paused
                     ? `<button class="button button--primary" type="button" data-resume-job="${job.job_id}">${icon("play_arrow")} Resume</button>`
                     : `<button class="button" type="button" data-pause-job="${job.job_id}">${icon("pause")} Pause</button>`
                 }`
              : `<button id="start-scraping" class="button button--primary" type="button" data-start-scrape>${icon("play_arrow")} Start</button>`
          }
          <button class="button" type="button" data-new-scrape>${icon("add")} New Job</button>
        </div>
        <div class="job-switcher__list">
          ${
            jobs.length
              ? jobs.map(jobButton).join("")
              : `<p class="muted">No scraper jobs have been created yet.</p>`
          }
        </div>
      </div>
    </section>
  `;
}

function jobButton(job) {
  const selected = state.currentJob?.job_id === job.job_id;
  const deletable = job.status === "stopped";
  return `
    <div class="job-pill ${selected ? "is-selected" : ""}">
      <button class="job-pill__select" type="button" data-select-job="${job.job_id}">
        <span class="status-dot is-${escapeHtml(job.status)}"></span>
        <strong>#${job.job_id}</strong>
        <small>${escapeHtml(job.status)}</small>
      </button>
      ${deletable ? `<button class="icon-button job-pill__delete" type="button" data-delete-job="${job.job_id}" aria-label="Delete job #${job.job_id}" title="Delete stopped job">${icon("delete")}</button>` : ""}
    </div>
  `;
}

function selectField(label, options, name = "") {
  return `
    <label>
      <span class="label">${label}</span>
      <select ${name ? `name="${name}"` : ""}>${options.map((option) => `<option>${option}</option>`).join("")}</select>
    </label>
  `;
}

function inputField(label, value, name = "") {
  return `
    <label>
      <span class="label">${label}</span>
      <input type="text" value="${escapeHtml(value)}" ${name ? `name="${name}"` : ""} />
    </label>
  `;
}

function staticField(label, value) {
  return `
    <div class="static-field">
      <span class="label">${label}</span>
      <strong>${value}</strong>
    </div>
  `;
}

function renderResults() {
  const profiles = state.profiles;

  return `
    <section class="page">
      ${pageHeader(
        "Results Explorer",
        "Search, filter, and triage business contact details before tax revenue outreach.",
        `<button class="button" type="button" data-view="cards">${icon("view_module")} Cards</button>
         <button class="button button--primary" type="button" data-view="table">${icon("table_rows")} Table</button>`,
      )}
      ${filterBar(["Platform", "Follower Count", "Category", "Location", "Verification Status", "Date Found"], "Search all collected leads...")}
      <div id="results-view" class="panel">${profiles.length ? resultsTable(profiles) : emptyState("No backend results", "Scraped advertisers will appear here after a scrape completes.")}</div>
    </section>
  `;
}

function profileCard(profile) {
  const website = profile.website || profile.fbUrl || "";
  const platforms = profile.platforms || [];
  const emails = profile.emails || [];
  const phones = profile.phones || [];
  const sources = profile.sources || [];
  return `
    <article class="profile-card" data-profile="${escapeHtml(`${profile.name} ${profile.platform} ${profile.location} ${profile.contact}`.toLowerCase())}">
      <div class="profile-card__header">
        <div>
          <h2>${escapeHtml(profile.name)}</h2>
          <div class="tag-row">
            ${(platforms.length ? platforms : [profile.platform]).map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join(" ")}
          </div>
        </div>
        <span class="score-ring">${number(profile.followers)}</span>
      </div>
      <dl class="detail-list">
        <div><dt>Location</dt><dd>${escapeHtml(profile.location)}</dd></div>
        <div><dt>Email</dt><dd>${escapeHtml(emails[0] || "Not found")}</dd></div>
        <div><dt>Phone</dt><dd>${escapeHtml(phones[0] || "Not found")}</dd></div>
        <div><dt>Sources</dt><dd>${sources.length ? escapeHtml(sources.join(", ")) : "-"}</dd></div>
      </dl>
      <div class="link-stack">
        <a href="${escapeHtml(profile.fbUrl || "#")}" target="_blank" rel="noopener">Facebook page</a>
        ${website && website !== profile.fbUrl ? `<a href="${escapeHtml(website)}" target="_blank" rel="noopener">${escapeHtml(website)}</a>` : ""}
      </div>
      <div class="card-actions">
        ${businessActions(profile)}
      </div>
    </article>
  `;
}

function renderReview() {
  const profiles = state.profiles;

  return `
    <section class="page">
      ${pageHeader(
        "Review Queue",
        "A focused workspace for confirming business contact details before payment outreach.",
        `<button class="button" type="button" data-toast="Selected businesses queued for outreach">${icon("contact_mail")} Queue Selected</button>
         <button class="button button--primary" type="button" data-toast="Selected contacts marked ready">${icon("done_all")} Mark Ready</button>`,
      )}
      ${filterBar(["Status", "Platform", "Reviewer", "Category", "Location"], "Search review queue...")}
      <div class="panel">
        ${profiles.length ? reviewTable(profiles) : emptyState("Nothing to review", "Collected advertisers will move into this queue after scraping.")}
        <div class="panel__footer">
          <span class="label">Showing ${number(profiles.length)} records from the backend.</span>
        </div>
      </div>
    </section>
  `;
}

function renderTaxable() {
  const approved = state.taxable;
  return `
    <section class="page">
      ${pageHeader(
        "Taxable Businesses",
        "Verified business contacts ready for tax revenue payment follow-up.",
        `<button class="button button--primary" type="button" data-toast="Payment outreach message prepared">${icon("contact_mail")} Prepare Outreach</button>
         <button class="button" type="button" data-toast="Contacts marked as called">${icon("call")} Mark Called</button>
         <button class="button" type="button" data-toast="Follow-up reminders created">${icon("event_repeat")} Schedule Follow-up</button>`,
      )}
      <div class="stats-grid">
        ${metric("Contacts Ready", number(approved.length), "contact_mail")}
        ${metric("Payment Outreach Due", number(approved.length), "request_quote")}
        ${metric("High Priority Calls", number(approved.filter((profile) => profile.risk >= 80).length), "priority_high", "Risk score above 80", "is-highlighted")}
        ${metric("Recently Contacted", "0", "verified", "No outreach backend yet")}
      </div>
      <div class="panel">
        ${approved.length ? taxableTable(approved) : emptyState("No taxable entities yet", "Run tax classification after scraping to populate this list.")}
        <div class="panel__footer"><span class="label">Verified businesses with usable contact details</span></div>
      </div>
    </section>
  `;
}

function renderAnalytics() {
  const profiles = state.profiles;
  const readyCount = state.taxable.length;
  const pendingCount = Math.max(profiles.length - readyCount, 0);

  return `
    <section class="page">
      ${pageHeader("Analytics Dashboard", "Performance and distribution metrics for collected leads and reviewers.")}
      <div class="stats-grid">
        ${metric("Total Leads Collected", number(profiles.length), "group")}
        ${metric("Businesses Identified", number(profiles.length), "storefront")}
        ${metric("Outreach Ready Businesses", number(readyCount), "verified")}
        ${metric("Pending Review", number(pendingCount), "pending")}
      </div>
      <div class="dashboard-grid">
        ${chartPanel("Businesses By Industry", [["Advertisers", profiles.length ? 100 : 0], ["Taxable", readyCount ? Math.round((readyCount / Math.max(profiles.length, 1)) * 100) : 0]])}
        ${chartPanel("Platform Distribution", [["Selected Source", profiles.length ? 100 : 0], ["Other Sources", 0]])}
        ${chartPanel("Contact Readiness", [["Ready", readyCount], ["Pending", pendingCount]])}
        ${chartPanel("Job Progress", [["Ads", state.currentJob?.ad_count || 0], ["Advertisers", state.currentJob?.advertiser_count || 0]])}
      </div>
    </section>
  `;
}

function chartPanel(title, rows) {
  const max = Math.max(...rows.map(([, value]) => Number(value) || 0), 100);
  return `
    <section class="panel span-6">
      <div class="panel__header"><h2>${icon("bar_chart")} ${title}</h2></div>
      <div class="chart-list">
        ${rows
          .map(
            ([label, value]) => {
              const width = Math.min(100, Math.round(((Number(value) || 0) / max) * 100));
              return `
              <div class="chart-row">
                <span>${escapeHtml(label)}</span>
                <div class="progress"><span style="width:${width}%"></span></div>
                <strong>${number(value)}</strong>
              </div>
            `;
            },
          )
          .join("")}
      </div>
    </section>
  `;
}

function renderSettings() {
  return `
    <section class="page">
      ${pageHeader("Settings", "Operational preferences for scraper behavior, saved filters, and notifications.")}
      <div class="dashboard-grid">
        <section class="panel span-6">
          <div class="panel__header"><h2>${icon("tune")} Scraper Defaults</h2></div>
          <form class="config-form">
            ${selectField("Default Platform", ["Facebook", "Instagram", "LinkedIn", "X/Twitter", "TikTok"])}
            ${inputField("Max Leads Per Job", "5000")}
          </form>
        </section>
        <section class="panel span-6">
          <div class="panel__header"><h2>${icon("notifications")} Notifications</h2></div>
          <div class="list-stack">
            ${toggleRow("Job completion alerts", true)}
            ${toggleRow("High-risk business alerts", true)}
            ${toggleRow("Daily review digest", false)}
          </div>
        </section>
      </div>
    </section>
  `;
}

function toggleRow(label, checked) {
  return `<label class="schedule-card"><span>${label}</span><input type="checkbox" ${checked ? "checked" : ""} /></label>`;
}

function businessActions(profile) {
  return `
    <button class="button" type="button" data-open-drawer="${profile.id}">${icon("visibility")} View Contact</button>
    <button class="button button--primary" type="button" data-toast="Tax payment outreach prepared">${icon("contact_mail")} Prepare Outreach</button>
    <button class="button" type="button" data-toast="Business marked as contacted">${icon("call")} Mark Contacted</button>
    <button class="button" type="button" data-toast="Follow-up added">${icon("event_repeat")} Follow Up</button>
  `;
}

function businessTableActions(profile) {
  return `
    <button class="icon-button" type="button" data-open-drawer="${profile.id}" aria-label="View contact" title="View contact">${icon("visibility")}</button>
    <button class="icon-button icon-button--primary" type="button" data-toast="Tax payment outreach prepared" aria-label="Prepare outreach" title="Prepare outreach">${icon("contact_mail")}</button>
    <button class="icon-button" type="button" data-toast="Business marked as contacted" aria-label="Mark contacted" title="Mark contacted">${icon("call")}</button>
    <button class="icon-button" type="button" data-toast="Follow-up added" aria-label="Follow up" title="Follow up">${icon("event_repeat")}</button>
  `;
}

function filterBar(filters, placeholder) {
  return `
    <div class="filter-bar">
      <label class="search-box">${icon("search")}<input class="page-search" type="search" placeholder="${placeholder}" /></label>
      ${filters.map((filter) => `<button class="button" type="button">${icon("filter_list")} ${filter}</button>`).join("")}
      <select aria-label="Sort results">
        <option>Sort: Recently Found</option>
        <option>Sort: Followers</option>
        <option>Sort: Engagement</option>
        <option>Sort: Relevance Score</option>
      </select>
    </div>
  `;
}

function activityTable() {
  if (!state.activityLog.length) {
    return emptyState("No scraper activity yet", "Start a scraping job to see live browser and job events here.");
  }

  return `
    <div class="table-wrap activity-log">
      <table class="activity-table">
        <thead><tr><th>Timestamp</th><th>Event Type</th><th>Status</th><th>Message</th></tr></thead>
        <tbody>
          ${state.activityLog
            .map(
              ([time, type, status, message]) => `
                <tr><td>${escapeHtml(time)}</td><td>${escapeHtml(type)}</td><td><span class="status-pill is-${status.toLowerCase()}">${escapeHtml(status)}</span></td><td>${escapeHtml(message)}</td></tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function profileTable(rows, selectable = true) {
  return `
    <div class="table-wrap">
      <table class="lead-table">
        <thead>
          <tr>${selectable ? "<th><input type='checkbox' /></th>" : ""}<th>Name</th><th>Platform</th><th>Category</th><th>Location</th><th>Followers</th><th>Status</th></tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (profile) => `
                <tr>
                  ${selectable ? "<td><input type='checkbox' /></td>" : ""}
                  <td><strong>${profile.name}</strong><small>${profile.owner}</small></td>
                  <td><span class="badge">${profile.platform}</span></td>
                  <td>${profile.category}</td>
                  <td>${profile.location}</td>
                  <td>${number(profile.followers)}</td>
                  <td><span class="status-pill ${statusClass(profile.status)}">${profile.status}</span></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function resultsTable(rows) {
  return `
    <div class="table-wrap">
      <table class="lead-table">
        <thead>
          <tr><th>Business</th><th>Platforms</th><th>Location</th><th>Contact</th><th>Sources</th><th>First Seen</th><th>Actions</th></tr>
        </thead>
        <tbody>
          ${rows
            .map(
              (profile) => {
                const platforms = profile.platforms || [];
                const emails = profile.emails || [];
                const phones = profile.phones || [];
                const sources = profile.sources || [];
                return `
                <tr data-profile="${escapeHtml(`${profile.name} ${profile.platform} ${profile.location} ${profile.contact}`.toLowerCase())}">
                  <td><strong>${escapeHtml(profile.name)}</strong><small>${escapeHtml(profile.fbUrl || "")}</small></td>
                  <td>${(platforms.length ? platforms : [profile.platform]).map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join(" ")}</td>
                  <td>${escapeHtml(profile.location)}</td>
                  <td><strong>${escapeHtml(profile.contact)}</strong>${emails[0] && phones[0] ? `<small>${escapeHtml(phones[0])}</small>` : ""}</td>
                  <td>${sources.length ? sources.map((s) => `<span class="badge">${escapeHtml(s)}</span>`).join(" ") : "-"}</td>
                  <td>${escapeHtml(profile.found)}</td>
                  <td><div class="table-actions">${businessTableActions(profile)}</div></td>
                </tr>
              `;
              },
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function reviewTable(rows) {
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th><input type="checkbox" /></th><th>Name</th><th>Platform</th><th>Category</th><th>Location</th><th>Followers</th><th>Discovery Date</th><th>Reviewer</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>
          ${rows
            .map(
              (profile) => `
                <tr>
                  <td><input type="checkbox" /></td>
                  <td><strong>${profile.name}</strong><small>${profile.owner}</small></td>
                  <td><span class="badge">${profile.platform}</span></td>
                  <td>${profile.category}</td>
                  <td>${profile.location}</td>
                  <td>${number(profile.followers)}</td>
                  <td>${profile.found}</td>
                  <td>${profile.reviewer}</td>
                  <td><select><option>${profile.status}</option><option>Pending Review</option><option>Ready To Contact</option><option>Rejected</option><option>Needs More Information</option></select></td>
                  <td><button class="button" type="button" data-open-drawer="${profile.id}">${icon("notes")} Comments</button></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function taxableTable(rows) {
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th>Business Name</th><th>Owner Name</th><th>Platform</th><th>Industry</th><th>Location</th><th>Website</th><th>Contact Details</th><th>Review Date</th><th>Priority Score</th><th>Outreach Status</th><th>Actions</th></tr></thead>
        <tbody>
          ${rows
            .map(
              (profile) => `
                <tr>
                  <td><strong>${profile.name}</strong></td>
                  <td>${profile.owner}</td>
                  <td><span class="badge">${profile.platform}</span></td>
                  <td>${profile.industry}</td>
                  <td>${profile.location}</td>
                  <td>${profile.website}</td>
                  <td>${profile.contact}</td>
                  <td>${profile.found}</td>
                  <td><strong>${profile.risk}</strong></td>
                  <td><span class="status-pill is-approved">Ready To Contact</span></td>
                  <td><div class="table-actions">${businessTableActions(profile)}</div></td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

function statusClass(status) {
  if (status === "Ready To Contact") return "is-approved";
  if (status === "Rejected") return "is-rejected";
  if (status === "Needs More Information") return "is-warning";
  return "is-running";
}

function renderDrawer(profileId) {
  const allProfiles = [...state.profiles, ...state.taxable];
  const profile = allProfiles.find((item) => String(item.id) === String(profileId)) || allProfiles[0];
  if (!profile) return;
  const socialLinks = (profile.socialLinks || [])
    .map((link) => `<a href="${escapeHtml(link.url)}" target="_blank" rel="noopener">${escapeHtml(link.platform || link.url)}</a>`)
    .join(" ");
  const emails = profile.emails || [];
  const phones = profile.phones || [];
  const addresses = profile.addresses || [];
  const sources = profile.sources || [];
  drawerRoot.innerHTML = `
    <div class="drawer-backdrop" data-close-drawer></div>
    <aside class="drawer" role="dialog" aria-modal="true" aria-label="Business details">
      <div class="panel__header">
        <div>
          <h2>${escapeHtml(profile.name)}</h2>
          <span class="eyebrow">${escapeHtml(profile.platform)} business detail</span>
        </div>
        <button class="icon-button" type="button" data-close-drawer aria-label="Close details">${icon("close")}</button>
      </div>
      <div class="drawer__body">
        <section class="stat-card">
          <h2>${profile.owner}</h2>
          <p class="muted">${profile.industry} business in ${profile.location}</p>
          <div class="stats-grid compact-grid">
            ${metric("Followers", number(profile.followers), "group")}
            ${metric("Sources", sources.length, "travel_explore")}
          </div>
        </section>
        <section class="form-stack">
          ${evidenceCard("mail", "Emails", emails.length ? escapeHtml(emails.join(", ")) : "No email discovered", "")}
          ${evidenceCard("call", "Phones", phones.length ? escapeHtml(phones.join(", ")) : "No phone discovered", "")}
          ${evidenceCard("location_on", "Addresses", addresses.length ? escapeHtml(addresses.join(" / ")) : "No address discovered", "")}
          ${evidenceCard("link", "Social Links", socialLinks || "No links found", "")}
          ${evidenceCard("payments", "Tax Payment Outreach", "Prepare a clear message about tax revenue payment obligations and next steps.", "is-muted")}
        </section>
      </div>
      <div class="panel__footer">
        <button class="button button--primary" type="button" data-toast="Tax payment outreach prepared">Prepare Outreach</button>
        <button class="button" type="button" data-toast="Business marked as contacted">Mark Contacted</button>
      </div>
    </aside>
  `;

  drawerRoot.querySelectorAll("[data-toast]").forEach((button) => {
    button.onclick = () => showToast(button.dataset.toast);
  });
}

async function login(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const button = form.querySelector("button[type='submit']");
  const data = new FormData(form);

  if (button) button.disabled = true;
  try {
    const user = await apiFetch("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        username: data.get("username"),
        password: data.get("password"),
      }),
    });
    state.user = user;
    window.localStorage.setItem("akirs.user", JSON.stringify(user));
    render();
  } catch (error) {
    renderAuthOverlay(error.message || "Sign in failed");
  } finally {
    if (button) button.disabled = false;
  }
}

function signOut() {
  state.user = null;
  window.localStorage.removeItem("akirs.user");
  render();
}

async function startScraping() {
  const form = document.querySelector("#scraper-config");
  const startButton = document.querySelector("[data-start-scrape], #start-scraping");
  const formData = form ? new FormData(form) : new FormData();
  const city = String(formData.get("city") || defaultConfig.city).trim();
  const searchType = String(formData.get("search_type") || "All").trim();

  if (startButton) startButton.disabled = true;
  addActivity("Browser", "Running", "Opening Facebook login browser. Log in, then close that browser to start scraping.");

  try {
    const job = await apiFetch("/jobs/scrape/after-login", {
      method: "POST",
      body: JSON.stringify({
        country: formData.get("country") || defaultConfig.country,
        locations: city ? [city] : undefined,
        categories: searchType && searchType !== "All" ? [searchType] : undefined,
      }),
    });
    state.currentJob = job;
    await loadJobs(false);
    addActivity("Scraper", "Success", `Login browser closed. Scrape job ${job.job_id} queued.`);
  } catch (error) {
    addActivity("Scraper", "Warning", `Could not start scrape: ${error.message}`);
  } finally {
    if (startButton) startButton.disabled = false;
  }
}

async function updateJobAction(jobId, action) {
  const actionMap = {
    pause: window.akirsApi.pauseJob,
    resume: window.akirsApi.resumeJob,
    stop: window.akirsApi.stopJob,
  };
  const actionLabels = {
    pause: "paused",
    resume: "resumed",
    stop: "ended",
  };
  const request = actionMap[action];
  if (!request) return;

  try {
    state.currentJob = await request(jobId);
    await loadJobs(false);
    addActivity("Scraper", "Success", `Job #${jobId} ${actionLabels[action]}.`);
    render();
  } catch (error) {
    addActivity("Scraper", "Warning", `Could not ${action} job #${jobId}: ${error.message}`);
  }
}

async function deleteScrapeJob(jobId) {
  try {
    await window.akirsApi.deleteJob(jobId);
    if (state.currentJob?.job_id === jobId) state.currentJob = null;
    await loadJobs(false);
    addActivity("Jobs", "Success", `Deleted stopped job #${jobId}.`);
    render();
  } catch (error) {
    addActivity("Jobs", "Warning", `Could not delete job #${jobId}: ${error.message}`);
  }
}

function evidenceCard(iconName, title, body, modifier) {
  return `
    <article class="evidence-card ${modifier}">
      ${icon(iconName)}
      <div><strong>${title}</strong><p class="muted">${body}</p></div>
    </article>
  `;
}

function showToast(message) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.textContent = message;
  document.body.append(toast);
  window.setTimeout(() => toast.remove(), 2600);
}

function bindPageEvents(route) {
  drawerRoot.innerHTML = "";

  document.querySelectorAll("[data-open-drawer]").forEach((button) => {
    button.onclick = () => renderDrawer(button.dataset.openDrawer);
  });

  document.querySelectorAll("[data-toast]").forEach((button) => {
    button.onclick = () => showToast(button.dataset.toast);
  });

  document.querySelectorAll("[data-confirm]").forEach((button) => {
    button.onclick = () => {
      if (window.confirm(button.dataset.confirm)) showToast("Action confirmed");
    };
  });

  const pageSearch = document.querySelector(".page-search");
  if (pageSearch) pageSearch.oninput = () => {
    const query = pageSearch.value.trim().toLowerCase();
    document.querySelectorAll("[data-profile]").forEach((card) => {
      card.style.display = card.dataset.profile.includes(query) ? "" : "none";
    });
  };

  const threadCount = document.querySelector("#thread-count");
  const threadCountValue = document.querySelector("#thread-count-value");
  if (threadCount && threadCountValue) {
    const updateThreadCount = () => {
      const label = threadCount.value === "1" ? "thread" : "threads";
      threadCountValue.textContent = `${threadCount.value} ${label}`;
    };

    threadCount.oninput = updateThreadCount;
    updateThreadCount();
  }

  document.querySelector("#start-scraping")?.addEventListener("click", startScraping);
  document.querySelector("#sign-out")?.addEventListener("click", signOut);
  document.querySelector("[data-pause-job]")?.addEventListener("click", (event) => {
    updateJobAction(Number(event.currentTarget.dataset.pauseJob), "pause");
  });
  document.querySelector("[data-resume-job]")?.addEventListener("click", (event) => {
    updateJobAction(Number(event.currentTarget.dataset.resumeJob), "resume");
  });
  document.querySelector("[data-stop-job]")?.addEventListener("click", (event) => {
    const jobId = Number(event.currentTarget.dataset.stopJob);
    if (window.confirm(`End scraper job #${jobId}?`)) updateJobAction(jobId, "stop");
  });
  document.querySelectorAll("[data-delete-job]").forEach((button) => {
    button.onclick = (event) => {
      event.stopPropagation();
      const jobId = Number(button.dataset.deleteJob);
      if (window.confirm(`Delete stopped scraper job #${jobId}?`)) deleteScrapeJob(jobId);
    };
  });
  document.querySelector("[data-refresh-data]")?.addEventListener("click", loadData);
  document.querySelector("[data-new-scrape]")?.addEventListener("click", () => {
    state.currentJob = null;
    render();
    document.querySelector("#scraper-config input[name='city']")?.focus();
  });
  document.querySelectorAll("[data-select-job]").forEach((button) => {
    button.onclick = async () => {
      const jobId = Number(button.dataset.selectJob);
      const cached = state.jobs.find((job) => job.job_id === jobId);
      if (cached) state.currentJob = cached;
      render();
      try {
        state.currentJob = await window.akirsApi.fetchJob(jobId);
        await loadJobs(false);
        render();
      } catch (error) {
        addActivity("Jobs", "Warning", `Could not open job #${jobId}: ${error.message}`);
      }
    };
  });

  if (route === "results") {
    const tableButton = document.querySelector("[data-view='table']");
    const cardsButton = document.querySelector("[data-view='cards']");

    tableButton.onclick = () => {
      document.querySelector("#results-view").outerHTML = `<div id="results-view" class="panel">${state.profiles.length ? resultsTable(state.profiles) : emptyState("No backend results", "Scraped advertisers will appear here after a scrape completes.")}</div>`;
      tableButton.classList.add("button--primary");
      cardsButton.classList.remove("button--primary");
      bindPageEvents("results");
    };
    cardsButton.onclick = () => {
      document.querySelector("#results-view").outerHTML = `<div id="results-view" class="profile-grid">${state.profiles.length ? state.profiles.map(profileCard).join("") : emptyState("No backend results", "Scraped advertisers will appear here after a scrape completes.")}</div>`;
      cardsButton.classList.add("button--primary");
      tableButton.classList.remove("button--primary");
      bindPageEvents("results");
    };
  }

}

drawerRoot.addEventListener("click", (event) => {
  if (event.target.closest("[data-close-drawer]")) drawerRoot.innerHTML = "";
});

document.querySelector("#theme-toggle")?.addEventListener("click", () => {
  document.body.classList.toggle("light-theme");
  document.querySelector("#theme-toggle .material-symbols-outlined").textContent = document.body.classList.contains("light-theme")
    ? "light_mode"
    : "dark_mode";
});

document.querySelector("#sidebar-toggle")?.addEventListener("click", () => {
  document.body.classList.toggle("sidebar-collapsed");
});

document.querySelector("#auth-toggle")?.addEventListener("click", () => {
  const panel = document.querySelector("#auth-panel");
  const toggle = document.querySelector("#auth-toggle");
  const isOpen = panel && !panel.hidden;

  if (panel && toggle) {
    panel.hidden = isOpen;
    toggle.setAttribute("aria-expanded", String(!isOpen));
  }
});

document.addEventListener("click", (event) => {
  const panel = document.querySelector("#auth-panel");
  const toggle = document.querySelector("#auth-toggle");

  if (!event.target.closest(".auth-menu") && panel && toggle) {
    panel.hidden = true;
    toggle.setAttribute("aria-expanded", "false");
  }
});

window.addEventListener("keydown", (event) => {
  if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
    event.preventDefault();
    document.querySelector("#global-search")?.focus();
  }
});

window.addEventListener("hashchange", render);

if (!window.location.hash) {
  window.location.hash = "#/dashboard";
} else {
  render();
}

loadData();

window.setInterval(async () => {
  if (!window.akirsApi) return;
  await loadJobs(false);
  if (state.currentJob && isScraperActive(state.currentJob)) {
    try {
      state.currentJob = await window.akirsApi.fetchJob(state.currentJob.job_id);
    } catch {
      // Keep the last visible job state if a polling request fails.
    }
  }
  updateTopbarStatus();
  if (getRoute() === "scraper") render();
}, 5000);
