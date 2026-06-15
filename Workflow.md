# akirs-auto Project Execution Footprint & Master Workflow

## Technical Blueprint & Project Footprint

This document serves as the absolute technical footprint for the `akirs-auto` project.
It traces every stage of construction, testing, data flow, and deployment. Each module maps out what needs to be built, 
how data shifts across execution lines, which precise dependencies are required,
and why those architectural decisions were made.

---

## 🏗️ Section 1: The Code Integration & Deployment Lifecycle (CI/CD)

Before a single line of automation logic runs, the code delivery engine must be locked down. 
This workflow ensures that parallel development branches do not create dependency hell, corrupt the database, 
or break the distributed worker system.

[ Local Developer Workspace ]
│
▼ (uv sync / playwright install)
[ Feature Isolation: feature/name ]
│
▼ (alembic revision --autogenerate)
[ Local Verification: pytest ]
│
▼ (Git Push to Remote)
[ Automated Code Quality Review Gate ]
│
▼ (Squash Merge)
[ Integrated Staging Environment ]
│
▼ (E2E Integration & Load Tests)
[ Main Production Branch Deployment]

### Stage 1.1: Local Environment Alignment & Parity
* **What needs to be done:** Standardize the execution environment across all developer workstations to avoid the
* "it works on my machine" dilemma.
* **Dependencies Needed:**
  * `uv` (Workspace package manager): Fast dependency resolution and deterministic virtual environments.
  * `playwright` (Browser binaries): Local automated browser engines.
* **Why they are needed:** Python's traditional `pip` and `virtualenv` setups often allow silent sub-dependency drifting.
* `uv` uses a cryptographic lockfile (`uv.lock`) that ensures every developer, staging runner, and production container
*  executes exactly the same compiled byte-code. Playwright binaries must be matched explicitly to the software wrapper
*   version to prevent runtime driver mismatches.

### Stage 1.2: Branch Isolation & DB Migration Locking
* **What needs to be done:** Create an ephemeral code branch scoped to a single ticket and
* lock changes to relational database schemas.
* **Dependencies Needed:**
  * `Git`: Version control.
  * `Alembic`: Relational database migration tracking.
  * `SQLAlchemy ORM`: Object-relational mapping.
* **Why they are needed:** Direct pushes to primary branches disrupt stability.
* Branches must use the naming convention `feature/short-description`. When modifications are made to data tables, developers must run:
  ```bash
  alembic revision --autogenerate -m "add_indices_to_advertiser_table"
### Stage 1.3: The Staging Integration & Review Gate
What needs to be done: Merge tested feature code into a unified integration environment (staging) before final deployment.
Dependencies Needed:
* 'pytest': Test execution engine.
* 'Ruff': Ultra-fast Python linter and code formatter.
Why they are needed: Human review can miss structural regressions. Pull requests (PRs) targeting staging automatically trigger code checks.
Ruff enforces style guide consistency and catches syntax smells. pytest executes the entire suite in isolation. 
A PR cannot be merged into staging without passing these automated gates and receiving at least one senior engineer's sign-off.

### ⚙️ Section: End-to-End Application Data Flow Architecture
This matrix traces how a user parameter configuration shifts through memory, automated browsers,
network fallbacks, and onto the local disk as an enriched asset.

[ FastAPI Ingress Endpoint ]
                     │ (Validates Input Schema via Pydantic)
                     ▼
          [ Redis Message Broker ]
                     │ (Task Distributed to Available Worker Thread)
                     ▼
       [ Phase 1: Playwright Engine ] ──► Extracts Target data vectors from Meta Library
                     │
                     ▼
       [ Phase 2: Tiered Recon Module ]
                     │
                     ├──► [ Tier 1: Website Miner ] ────► Scrapes live corporate sites
                     │                                    (Short-circuit if complete)
                     │
                     ├──► [ Tier 2: Open Directory ] ───► DuckDuckGo Snippets & OSM Maps
                     │                                    (Short-circuit if complete)
                     │
                     └──► [ Tier 3: Premium B2B APIs ] ─► Hunter.io, TomTom, Apollo.io
                                                          (Graceful degradation check)
                     │
                     ▼
       [ Phase 3: Consolidation Matrix ] ─► 1:1 Normalization (Advertiser x Social URL)
                     │
                     ▼
       [ PostgreSQL DB / Local Storage ] ─► Updates operational boards and emits Enriched CSV

### 🗂️ Section 3: Detailed Breakdowns of Execution Sub-Units
To parallelize development, the project is divided into 5 independent technical building blocks. 
Each block lists its internal file paths, required dependencies, and core development requirements.
Sub-Unit 1: Core Infrastructure & Data Persistence
Target Components: alembic/, pyproject.toml, .env.example, backend/akirs/models.py

**Dependencies & Tooling Stack:**
SQLAlchemy >= 2.0.0: Modern, type-safe Python SQL toolkit.
psycopg2-binary: PostgreSQL database adapter layer.
pydantic-settings: Advanced environment variable structure management.
Why these dependencies are needed: SQLAlchemy 2.0 provides native type-hinting support, 
which helps prevent runtime database typing exceptions during intense background writes. 
pydantic-settings parses raw values from .env and turns them into strictly typed Python objects, failing
fast at launch if a structural configuration variable is missing or formatted incorrectly.

**Step-by-Step Blueprint:**
Initialize the project directory and generate the foundational dependency configuration file using uv init.
Configure alembic.ini and set up alembic/env.py to point directly to the declarative target metadata models.
Construct database models to support a unified relational schema layout.
Expose an explicit 1:1 relational matrix mapping structure where each single output row represents exactly one distinct business 
profile merged with one unique social account connection. 
This structure prevents messy, hard-to-parse comma-separated list values within table cells.

**Sub-Unit 2:** Phase 1 Ingestion & Browser Automation Engine
Target Components: src/scraper/, main.py
Dependencies & Tooling Stack:
playwright >= 1.40.0: Async browser automation framework.
beautifulsoup4: High-efficiency document object model (DOM) parsing.

Why these dependencies are needed: Traditional scraping packages like requests cannot execute client-side JavaScript applications, 
making them ineffective against modern Single Page Apps (SPAs) 
like the Meta Ads Library.
Playwright orchestrates full headless Chromium engines, handling infinite scrolling, 
dynamic event bindings, and complex DOM rendering. Passing the
raw static string tree to beautifulsoup4 for local regex lookups speeds
up parsing and frees up the browser instance to pull the next page layout.

### Step-by-Step Blueprint:
Build an asynchronous browser orchestration engine context manager inside src/scraper/browser.py.
Write robust UI navigation handlers that input search criteria keywords based on localized geographical coordinates
(e.g., target landmarks, commercial zones).
Implement defensive selectors to pull core data blocks safely: unique target identifiers (ad_id), 
target brand strings (advertiser_name), 
and origin web tracking redirects (advertiser_url).

Build an automated UI layout handler: Wrap parsing routines in an explicit try/except block.
If a layout property changes, capture an image screenshot and dump the raw tree state directly into .temp/debug/error_snapshots/. 
The system should log a warning, discard the single corrupted lead element, and continue parsing the remaining queue items.
Sub-Unit 3: Phase 2 Enrichment Engine (The Waterfall Engine)
Target Components: src/recon/

**Dependencies & Tooling Stack:**
* 'httpx': Next-generation asynchronous HTTP client framework.
* 'geopy': Geographic coordinate alignment mapping library.
Why these dependencies are needed: Standard synchronous networking libraries block worker processes during external I/O requests.
httpx lets the system trigger dozens of separate enrichment calls concurrently using async event loops.
geopy cleans up unstructured address strings by cross-referencing global coordinate arrays.

* **Blueprint:**
* 'Tier 1 Setup (Direct Domain Mining)': Use httpx to fetch the destination target website collected in Phase 1.
* Run strict regex patterns to find emails, clean formatting strings from phone signatures,
* and pull peripheral social media tracking extensions (e.g., Instagram or X profiles).
* 
* 'Tier 2 Setup (Free OSINT Engines)': Build scraping connections to extract text from DuckDuckGo HTML snippet layouts and query
*  OpenStreetMap Nominatim for open geographic tracking records.
*  
* Tier 3 Setup (Commercial Integrations) : Connect dedicated API wrappers for premium enrichment layers (TomTom Places,
*  Hunter.io, Apollo.io).

  **Short-Circuit Evaluation Logic**: Program an evaluation gate between each verification layer.
* If an operational tracking block successfully resolves both a valid email and phone entry,
* short-circuit the execution flow immediately and pass the lead forward to save API credits.

  **Graceful Degradation Handler**: Wrap all third-party commercial modules in an exception check.
* If an API credential key is missing or an account balance is exhausted, catch the exception,
*  write a diagnostic trace log,
* and pass the lead forward rather than crashing the execution thread.

  **Sub-Unit 4: Asynchronous Task Queue & API Layer**
  Target Components: backend/akirs/api/, backend/akirs/tasks/, alembic.ini.

**Dependencies & Tooling Stack:**
fastapi: Modern, high-performance web framework.
celery: Distributed task worker architecture.
redis: High-speed message broker and in-memory key-value engine.
uvicorn: Production-ready ASGI server engine.

**Why these dependencies are needed:** Web scraping can take minutes or hours, which exceeds standard web browser timeout windows. 
FastAPI catches incoming search metrics shifts instantly and passes them as lightweight execution messages to Redis. 
Celery workers pick up these messages from the Redis queue and process the tasks as background threads. 
This keeps the frontend UI snappy and responsive, no matter how many scraping passes are running in the background.

**Step-by-Step Blueprint:**
1. Create a FastAPI application inside backend/akirs/api/app.py that exposes runtime criteria inputs
     (locations, target_limit). Validate incoming inputs using Pydantic validation rules.
2.Configure the Celery messaging worker queue engine mapping tasks to a background execution pool:
celery_app = Celery("akirs", broker="redis://localhost:6379/0", backend="redis://localhost:6379/0")

3. Build an export script that triggers as soon as Celery marks a job state as SUCCESS. This script flattens relational
    data tables,builds an enriched .csv file asset,and stores it in a secure download directory.
   
**Sub-Unit 5:** Operational Dashboard UI & Chatbot Core
Target Components: UserInterface/, chatbot/

**Dependencies & Tooling Stack:**
jinja2 / HTML5 / TailwindCSS: Frontend template generation and styling engine.
openai / langchain (or lightweight text classifier alternatives): Text indexing and entity extraction framework.
Why these dependencies are needed: Non-technical managers need a clean interface to run jobs and download reports without using the command line.
An integrated text classifier processes noisy, unformatted ad text or website snippet dumps, automatically categorizing new businesses into operational sectors (e.g., Logistics, Retail, Real Estate).

 ### Step-by-Step Blueprint:
Build an operational dashboard page that queries the backend status endpoint via async JavaScript polling.
Expose progress indicators that map active worker state transitions:
PENDING: Task is queued in the message broker.
PROCESSING: Playwright browser has launched and is extracting data.
ENRICHING: Tiered waterfall recon modules are processing fields.
SUCCESS: The run is complete and the download button for the generated CSV file is active.
Build a text processing pipeline inside the chatbot/ directory. Feed the text blocks collected during scraping into the engine to automatically clean up and tag target businesses with accurate industry classification codes.

### 🛟 Section 4: Operational Edge-Case & Error Recovery Manual
Scrapers operate in dynamic environments where external interfaces can change without warning. The application must identify and recover from execution problems automatically.
4.1 Anti-Bot Mitigation & Evasion
When an external target returns an HTTP 429 Too Many Requests or triggers security challenge pages, the worker must execute an Exponential Jitter Backoff Routine. 
The worker goes to sleep, changing its request patterns before trying again

**Sub-Unit 5:** Operational Dashboard UI & Chatbot Core
Target Components: UserInterface/, chatbot/

**Dependencies & Tooling Stack:**
jinja2 / HTML5 / TailwindCSS: Frontend template generation and styling engine.
openai / langchain (or lightweight text classifier alternatives): Text indexing and entity extraction framework.
Why these dependencies are needed: Non-technical managers need a clean interface to run jobs and download reports without using the command line. An integrated text classifier processes noisy, unformatted ad text or website snippet dumps, automatically categorizing new businesses into operational sectors (e.g., Logistics, Retail, Real Estate).

**Step-by-Step Blueprint:**
Build an operational dashboard page that queries the backend status endpoint via async JavaScript polling.
Expose progress indicators that map active worker state transitions:
PENDING: Task is queued in the message broker.
PROCESSING: Playwright browser has launched and is extracting data.
ENRICHING: Tiered waterfall recon modules are processing fields.
SUCCESS: The run is complete and the download button for the generated CSV file is active.
Build a text processing pipeline inside the chatbot/ directory. Feed the text blocks collected during scraping into the engine to automatically 
clean up and tag target businesses with accurate industry classification codes
If heavy write loads exhaust database connection capacity, background tasks will fail.
**Remediation:** Configure the database connectivity pool layer with strict lifetime parameters:
engine = create_engine(
    DATABASE_URL,
    pool_size=20,          # Holds 20 persistent socket pipelines
    max_overflow=10,       # Spawns 10 temporary overflow connections
    pool_recycle=1800      # Recycles zombie database sockets every 30 minutes
)

## 📅 Section 5: Master Sprint Dependency Mapping Matrix

| Sequence | Core Engineering Component | Upstream Dependencies | Target Area Focus | Critical Quality Check Target |
| :--- | :--- | :--- | :--- | :--- |
| **Milestone 1** | Sub-Unit 1: Data Model Design | None | Backend Engineers | Verify that running `alembic upgrade head` correctly generates the local database structure. |
| **Milestone 2** | Sub-Unit 2: Target Scraper | Milestone 1 | Automation Team | Run headless Playwright scripts and verify that output targets land safely in `.temp/debug/`. |
| **Milestone 3** | Sub-Unit 3: Waterfall Module | Milestone 1 | Data Engineering | Test external network APIs with missing keys to confirm the graceful degradation logic works without crashing. |
| **Milestone 4** | Sub-Unit 4: Distributed Systems Infra | Milestone 2 & 3 | Workers | Confirm that killing a running Celery worker causes the task to recycle back into the Redis queue safely. |
| **Milestone 5** | Sub-Unit 5: User Interface | Milestone 4 | Frontend Engineers | Confirm that real-time status changes shift predictably across the monitoring dashboard. |



