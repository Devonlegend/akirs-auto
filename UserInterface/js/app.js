const mockDefaults = {
  country: "Nigeria",
  state: "Akwaibom",
  city: "Uyo",
  query: "restaurant",
};

// Live scraped advertisers, loaded from the backend. Shape is produced by
// mapAdvertiser() so the existing render helpers keep working.
let profiles = [];
let dataState = "loading"; // loading | ready | empty | error
let dataError = null;

// Chat state (shared by the floating widget and the dedicated assistant page).
let chatHistory = [];
let chatLoading = false;
let chatOpen = false;


const activityLog = [
  ["12:18:44", "Browser", "Success", "Hidden browser launched with residential proxy pool."],
  ["12:19:03", "Search", "Running", `Query: ${mockDefaults.query} near ${mockDefaults.city}, ${mockDefaults.state} with contact links.`],
  ["12:19:41", "Lead", "Success", "Collected Ibom Fresh Foods with website and email."],
  ["12:20:08", "Queue", "Warning", "18 leads require duplicate checks."],
  ["12:20:55", "Outreach", "Success", "Contact list prepared for tax revenue follow-up."],
];

const app = document.querySelector("#app");
const drawerRoot = document.querySelector("#drawer-root");

function icon(name) {
  return `<span class="material-symbols-outlined">${name}</span>`;
}

function number(value) {
  return value.toLocaleString();
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
  dataState = "loading";
  dataError = null;
  render();
  try {
    const raw = await window.akirsApi.fetchAdvertisers();
    profiles = raw.map(mapAdvertiser);
    dataState = profiles.length ? "ready" : "empty";
  } catch (error) {
    dataError = error.message;
    dataState = "error";
  }
  render();
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
    assistant: renderAssistant,
    analytics: renderAnalytics,
    settings: renderSettings,
  };

  const activeRoute = pages[route] ? route : "dashboard";
  setActiveNav(activeRoute);
  const dataRoutes = ["dashboard", "results", "review", "taxable", "analytics"];
  const banner = dataRoutes.includes(activeRoute) ? dataBanner() : "";
  app.innerHTML = banner + (pages[route] || renderDashboard)();
  app.focus({ preventScroll: true });
  bindPageEvents(route);
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
  return `
    <section class="page">
      ${pageHeader(
        "Dashboard",
        "Operational overview for finding business contacts and preparing tax revenue outreach.",
        `<a class="button button--primary" href="#/scraper">${icon("play_arrow")} Launch Scraper</a>
         <button class="button" type="button" data-toast="Saved dashboard filters">${icon("bookmark")} Saved Filters</button>`,
      )}

      <div class="stats-grid">
        ${metric("Leads Collected", number(14209), "group", "+12.4% today")}
        ${metric("Businesses Identified", number(4816), "storefront", "34 categories")}
        ${metric("Outreach Ready", "68%", "fact_check", "1,284 pending contact checks")}
        ${metric("Active Jobs", "3", "settings_remote", "8 browser threads", "is-highlighted")}
      </div>

      <div class="dashboard-grid">
        <section class="panel span-8">
          <div class="panel__header">
            <h2>${icon("history")} Recent Discoveries</h2>
            <a class="button" href="#/results">Open Results</a>
          </div>
          ${profileTable(profiles.slice(0, 4), false)}
        </section>
        <section class="panel span-4">
          <div class="panel__header"><h2>${icon("bolt")} Quick Actions</h2></div>
          <div class="list-stack">
            ${quickAction("Start new scrape", "Launch a hidden browser search job", "play_circle", "#/scraper")}
            ${quickAction("Review pending leads", "Verify contact details before outreach", "rule", "#/review")}
            ${quickAction("Contact taxable businesses", "Open verified contacts ready for tax payment follow-up", "contact_mail", "#/taxable")}
          </div>
        </section>
        <section class="panel span-12">
          <div class="panel__header">
            <h2>${icon("receipt_long")} Live Activity Log</h2>
            <span class="status-chip"><span></span> Streaming</span>
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
  return `
    <section class="page">
      ${pageHeader(
        "Scraper Control Center",
        "Configure platform searches, launch jobs, and monitor the hidden browser worker.",
        `<button class="button button--primary" type="button" data-toast="Scraping job started">${icon("play_arrow")} Start Scraping</button>
         <button class="button" type="button" data-toast="Job paused">${icon("pause")} Pause</button>
         <button class="button" type="button" data-toast="Job resumed">${icon("resume")} Resume</button>
         <button class="button button--danger" type="button" data-confirm="Stop the active scraper job?">${icon("stop")} Stop</button>`,
      )}

      <div class="dashboard-grid">
        <section class="panel span-5">   <span>1</span>
                <span>4</span>
                <span>8</span>
                <span>12</span>
          <div class="panel__header"><h2>${icon("tune")} Scraper Configuration</h2></div>
          <form class="config-form">
            ${selectField("Platform", ["Facebook", "Instagram", "LinkedIn", "X/Twitter", "TikTok", "Other"])}
            ${selectField("Search Type", ["Business Owners", "Business Pages", "Companies", "Entrepreneurs", "Local Services"])}
            <div class="form-grid">
              ${staticField("Target Country", mockDefaults.country)}
              ${staticField("Target State", mockDefaults.state)}
              ${inputField("City", mockDefaults.city)}
            </div>
            ${inputField("Keywords", "restaurant, mechanic, salon, retail")}
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
            ${metric("Browser Status", "Running", "desktop_windows", "Headless Chromium")}
            ${metric("Current Query", mockDefaults.query, "search", `${mockDefaults.city}, ${mockDefaults.state}`)}
            ${metric("Leads Found", "1,842", "group_add", "+248 last hour")}
            ${metric("Pages Scanned", "6,920", "travel_explore", "82/min")}
            ${metric("Success Rate", "94.6%", "check_circle", "Healthy")}
            ${metric("Runtime", "02:18:44", "timer", "Started today")}
            ${metric("Queue Size", "318", "queue", "62 high priority")}
            ${metric("Active Threads", "8", "memory", "Autoscaled")}
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

function selectField(label, options) {
  return `
    <label>
      <span class="label">${label}</span>
      <select>${options.map((option) => `<option>${option}</option>`).join("")}</select>
    </label>
  `;
}

function inputField(label, value) {
  return `
    <label>
      <span class="label">${label}</span>
      <input type="text" value="${value}" />
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
  return `
    <section class="page">
      ${pageHeader(
        "Results Explorer",
        "Search, filter, and triage business contact details before tax revenue outreach.",
        `<button class="button" type="button" data-view="cards">${icon("view_module")} Cards</button>
         <button class="button button--primary" type="button" data-view="table">${icon("table_rows")} Table</button>`,
      )}
      ${filterBar(["Platform", "Follower Count", "Category", "Location", "Verification Status", "Date Found"], "Search all collected leads...")}
      <div id="results-view" class="panel">${resultsTable(profiles)}</div>
    </section>
  `;
}

function profileCard(profile) {
  const website = profile.website || profile.fbUrl || "";
  return `
    <article class="profile-card" data-profile="${escapeHtml(`${profile.name} ${profile.platform} ${profile.location} ${profile.contact}`.toLowerCase())}">
      <div class="profile-card__header">
        <div>
          <h2>${escapeHtml(profile.name)}</h2>
          <div class="tag-row">
            ${(profile.platforms.length ? profile.platforms : [profile.platform]).map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join(" ")}
          </div>
        </div>
        <span class="score-ring">${number(profile.followers)}</span>
      </div>
      <dl class="detail-list">
        <div><dt>Location</dt><dd>${escapeHtml(profile.location)}</dd></div>
        <div><dt>Email</dt><dd>${escapeHtml(profile.emails[0] || "Not found")}</dd></div>
        <div><dt>Phone</dt><dd>${escapeHtml(profile.phones[0] || "Not found")}</dd></div>
        <div><dt>Sources</dt><dd>${profile.sources.length ? escapeHtml(profile.sources.join(", ")) : "—"}</dd></div>
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
        ${reviewTable()}
        <div class="panel__footer">
          <span class="label">Showing 1-5 of 1,284 records. Virtualized table handoff ready for backend paging.</span>
          ${pagination()}
        </div>
      </div>
    </section>
  `;
}

function renderTaxable() {
  const approved = profiles.filter((profile) => profile.status === "Ready To Contact");
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
        ${metric("Contacts Ready", number(approved.length * 618), "contact_mail")}
        ${metric("Payment Outreach Due", number(approved.length * 482), "request_quote")}
        ${metric("High Priority Calls", "147", "priority_high", "Risk score above 80", "is-highlighted")}
        ${metric("Recently Contacted", "38", "verified", "Last 24 hours")}
      </div>
      <div class="panel">
        ${taxableTable(approved)}
        <div class="panel__footer"><span class="label">Verified businesses with usable contact details</span>${pagination()}</div>
      </div>
    </section>
  `;
}

function renderAnalytics() {
  return `
    <section class="page">
      ${pageHeader("Analytics Dashboard", "Performance and distribution metrics for collected leads and reviewers.")}
      <div class="stats-grid">
        ${metric("Total Leads Collected", number(14209), "group")}
        ${metric("Businesses Identified", number(4816), "storefront")}
        ${metric("Outreach Ready Businesses", number(1236), "verified")}
        ${metric("Rejected Businesses", number(408), "block")}
      </div>
      <div class="dashboard-grid">
        ${chartPanel("Businesses By Industry", [["Beauty", 88], ["Construction", 64], ["Restaurant", 72], ["Local Services", 94]])}
        ${chartPanel("Platform Distribution", [["Facebook", 82], ["Instagram", 76], ["LinkedIn", 58], ["TikTok", 46]])}
        ${chartPanel("Contact Readiness", [["Mon", 54], ["Tue", 68], ["Wed", 74], ["Thu", 61], ["Fri", 79]])}
        ${chartPanel("Reviewer Performance", [["Ada", 92], ["Chris", 86], ["Nora", 74], ["Sam", 68]])}
      </div>
    </section>
  `;
}

function chartPanel(title, rows) {
  return `
    <section class="panel span-6">
      <div class="panel__header"><h2>${icon("bar_chart")} ${title}</h2></div>
      <div class="chart-list">
        ${rows
          .map(
            ([label, value]) => `
              <div class="chart-row">
                <span>${label}</span>
                <div class="progress"><span style="width:${value}%"></span></div>
                <strong>${value}%</strong>
              </div>
            `,
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
  return `
    <div class="table-wrap activity-log">
      <table class="activity-table">
        <thead><tr><th>Timestamp</th><th>Event Type</th><th>Status</th><th>Message</th></tr></thead>
        <tbody>
          ${activityLog
            .map(
              ([time, type, status, message]) => `
                <tr><td>${time}</td><td>${type}</td><td><span class="status-pill is-${status.toLowerCase()}">${status}</span></td><td>${message}</td></tr>
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
              (profile) => `
                <tr data-profile="${escapeHtml(`${profile.name} ${profile.platform} ${profile.location} ${profile.contact}`.toLowerCase())}">
                  <td><strong>${escapeHtml(profile.name)}</strong><small>${escapeHtml(profile.fbUrl || "")}</small></td>
                  <td>${(profile.platforms.length ? profile.platforms : [profile.platform]).map((p) => `<span class="badge">${escapeHtml(p)}</span>`).join(" ")}</td>
                  <td>${escapeHtml(profile.location)}</td>
                  <td><strong>${escapeHtml(profile.contact)}</strong>${profile.emails[0] && profile.phones[0] ? `<small>${escapeHtml(profile.phones[0])}</small>` : ""}</td>
                  <td>${profile.sources.length ? profile.sources.map((s) => `<span class="badge">${escapeHtml(s)}</span>`).join(" ") : "—"}</td>
                  <td>${escapeHtml(profile.found)}</td>
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

function reviewTable() {
  return `
    <div class="table-wrap">
      <table>
        <thead><tr><th><input type="checkbox" /></th><th>Name</th><th>Platform</th><th>Category</th><th>Location</th><th>Followers</th><th>Discovery Date</th><th>Reviewer</th><th>Status</th><th>Notes</th></tr></thead>
        <tbody>
          ${profiles
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

function pagination() {
  return `
    <div class="pagination">
      <button class="icon-button" type="button" aria-label="Previous page">${icon("chevron_left")}</button>
      <button class="button button--primary" type="button">1</button>
      <button class="button" type="button">2</button>
      <button class="button" type="button">3</button>
      <button class="icon-button" type="button" aria-label="Next page">${icon("chevron_right")}</button>
    </div>
  `;
}

function statusClass(status) {
  if (status === "Ready To Contact") return "is-approved";
  if (status === "Rejected") return "is-rejected";
  if (status === "Needs More Information") return "is-warning";
  return "is-running";
}

function renderDrawer(id) {
  const profile = profiles.find((item) => String(item.id) === String(id)) || profiles[0];
  if (!profile) return;
  const links = (profile.socialLinks || [])
    .map((l) => `<a href="${escapeHtml(l.url)}" target="_blank" rel="noopener">${escapeHtml(capitalize(l.platform))}: ${escapeHtml(l.url.slice(0, 48))}…</a>`)
    .join("");
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
          <p class="muted">${escapeHtml(profile.location)}</p>
          <div class="stats-grid compact-grid">
            ${metric("Followers", number(profile.followers), "group")}
            ${metric("Sources", profile.sources.length, "travel_explore")}
          </div>
        </section>
        <section class="form-stack">
          ${evidenceCard("mail", "Emails", profile.emails.length ? escapeHtml(profile.emails.join(", ")) : "No email discovered", "")}
          ${evidenceCard("call", "Phones", profile.phones.length ? escapeHtml(profile.phones.join(", ")) : "No phone discovered", "")}
          ${evidenceCard("location_on", "Addresses", profile.addresses.length ? escapeHtml(profile.addresses.join(" • ")) : "No address discovered", "")}
          ${evidenceCard("link", "Social Links", links || "No links found", "")}
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

/* ---------------------------------------------------------------- Chatbot */

function renderAssistant() {
  return `
    <section class="page assistant-page">
      ${pageHeader(
        "AI Assistant",
        "Chat with the RAG assistant over your scraped business data.",
        `<button class="button" type="button" id="chat-sync">${icon("sync")} Sync knowledge base</button>`,
      )}
      <div class="panel chat-page">
        <div class="chat-page__messages" data-chat-messages></div>
        <form class="chat-input" id="chat-form-page">
          <input type="text" placeholder="Ask about a business, contact, or location..." autocomplete="off" />
          <button class="button button--primary" type="submit">${icon("send")} Send</button>
        </form>
      </div>
    </section>
  `;
}

function chatMessageHtml(msg) {
  if (msg.role === "user") {
    return `<div class="chat-msg is-user"><div class="chat-msg__bubble">${escapeHtml(msg.text)}</div></div>`;
  }
  const sources =
    msg.sources && msg.sources.length
      ? `<details class="chat-sources">
           <summary>${msg.sources.length} source${msg.sources.length > 1 ? "s" : ""}</summary>
           ${msg.sources
             .map(
               (s) => `<div class="chat-source"><span class="chat-source__score">${Math.round((s.score || 0) * 100)}%</span><p>${escapeHtml(s.excerpt || "")}</p></div>`,
             )
             .join("")}
         </details>`
      : "";
  return `<div class="chat-msg is-bot${msg.error ? " is-error" : ""}"><div class="chat-msg__bubble">${escapeHtml(msg.text)}</div>${sources}</div>`;
}

function chatListHtml() {
  const empty = `<div class="chat-empty">${icon("smart_toy")}<p>Ask about scraped businesses, contacts, or locations.</p></div>`;
  const typing = chatLoading
    ? `<div class="chat-msg is-bot"><div class="chat-msg__bubble chat-typing"><span></span><span></span><span></span></div></div>`
    : "";
  return (chatHistory.length ? chatHistory.map(chatMessageHtml).join("") : empty) + typing;
}

function refreshChatViews() {
  document.querySelectorAll("[data-chat-messages]").forEach((el) => {
    el.innerHTML = chatListHtml();
    el.scrollTop = el.scrollHeight;
  });
}

async function submitChat(text) {
  const question = (text || "").trim();
  if (!question || chatLoading) return;
  chatHistory.push({ role: "user", text: question });
  chatLoading = true;
  refreshChatViews();
  try {
    const res = await window.akirsApi.sendChat(question);
    chatHistory.push({ role: "bot", text: res.answer || "(no answer returned)", sources: res.sources || [] });
  } catch (error) {
    chatHistory.push({
      role: "bot",
      text: `Sorry — ${error.message}. Make sure the backend and Ollama are running, and that the knowledge base has been synced.`,
      error: true,
    });
  } finally {
    chatLoading = false;
    refreshChatViews();
  }
}

function bindChatForm(form) {
  if (!form) return;
  form.onsubmit = (event) => {
    event.preventDefault();
    const input = form.querySelector("input");
    submitChat(input.value);
    input.value = "";
  };
}

function renderChatWidget() {
  const root = document.querySelector("#chat-widget");
  if (!root) return;
  root.innerHTML = `
    <button id="chat-fab" class="chat-fab" type="button" aria-label="Open AI assistant">${icon("forum")}</button>
    <section id="chat-panel" class="chat-panel" aria-label="AI assistant" ${chatOpen ? "" : "hidden"}>
      <header class="chat-panel__header">
        <strong>${icon("smart_toy")} AKIRS Assistant</strong>
        <button class="icon-button" type="button" id="chat-close" aria-label="Close assistant">${icon("close")}</button>
      </header>
      <div class="chat-panel__messages" data-chat-messages></div>
      <form class="chat-input" id="chat-form-widget">
        <input type="text" placeholder="Ask about a business..." autocomplete="off" />
        <button class="button button--primary" type="submit" aria-label="Send">${icon("send")}</button>
      </form>
    </section>
  `;

  const panel = root.querySelector("#chat-panel");
  const setOpen = (open) => {
    chatOpen = open;
    panel.hidden = !open;
    if (open) {
      refreshChatViews();
      panel.querySelector("input")?.focus();
    }
  };
  root.querySelector("#chat-fab").onclick = () => setOpen(panel.hidden);
  root.querySelector("#chat-close").onclick = () => setOpen(false);
  bindChatForm(root.querySelector("#chat-form-widget"));
  refreshChatViews();
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

  if (route === "results") {
    const tableButton = document.querySelector("[data-view='table']");
    const cardsButton = document.querySelector("[data-view='cards']");

    tableButton.onclick = () => {
      document.querySelector("#results-view").outerHTML = `<div id="results-view" class="panel">${resultsTable(profiles)}</div>`;
      tableButton.classList.add("button--primary");
      cardsButton.classList.remove("button--primary");
      bindPageEvents("results");
    };
    cardsButton.onclick = () => {
      document.querySelector("#results-view").outerHTML = `<div id="results-view" class="profile-grid">${profiles.map(profileCard).join("")}</div>`;
      cardsButton.classList.add("button--primary");
      tableButton.classList.remove("button--primary");
      bindPageEvents("results");
    };
  }

  if (route === "assistant") {
    bindChatForm(document.querySelector("#chat-form-page"));
    refreshChatViews();
    const syncBtn = document.querySelector("#chat-sync");
    if (syncBtn) {
      syncBtn.onclick = async () => {
        syncBtn.disabled = true;
        showToast("Syncing knowledge base…");
        try {
          const r = await window.akirsApi.ingestFromScraper();
          showToast(`Synced ${r.advertisers_processed} businesses (${r.chunks_created} chunks)`);
        } catch (error) {
          showToast(`Sync failed: ${error.message}`);
        } finally {
          syncBtn.disabled = false;
        }
      };
    }
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
}

render();
renderChatWidget();
loadData();
