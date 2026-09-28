// Floating AKIRS Assistant chat widget.
// Mounts into #chat-widget (OUTSIDE #app) so the dashboard's periodic
// re-render of #app never wipes an open conversation. Talks to the backend
// RAG chatbot via window.akirsApi.sendChat against the "akirs_tax" collection.
(function () {
  const KB_COLLECTION = "akirs_tax";
  const messages = []; // { role: "user" | "assistant", text, sources?, pending? }
  let mounted = false;
  let isOpen = false;
  let sending = false;

  // Resolve the backend base without depending on api.js (which may load later
  // or fail). An empty string means same-origin, which is correct when the UI
  // is served from /ui by the backend itself.
  function apiBase() {
    if (window.akirsApi && typeof window.akirsApi.API_BASE === "string") {
      return window.akirsApi.API_BASE;
    }
    if (window.AKIRS_API_BASE) return window.AKIRS_API_BASE;
    if (window.location.pathname.startsWith("/ui")) return "";
    return "http://127.0.0.1:8000";
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

  function icon(name) {
    return `<span class="material-symbols-outlined">${name}</span>`;
  }

  function root() {
    let el = document.querySelector("#chat-widget");
    if (!el) {
      el = document.createElement("div");
      el.id = "chat-widget";
      document.body.appendChild(el);
    }
    return el;
  }

  function sourceLabel(src) {
    const topic = src?.metadata?.topic || src?.doc_id || "source";
    const score = typeof src?.score === "number" ? ` (${src.score.toFixed(2)})` : "";
    return `${escapeHtml(topic)}${score}`;
  }

  function renderSources(sources) {
    if (!sources || !sources.length) return "";
    const pills = sources
      .map((s) => `<span class="chat-source">${icon("description")} ${sourceLabel(s)}</span>`)
      .join("");
    return `<div class="chat-sources"><span class="chat-sources__label">Sources</span>${pills}</div>`;
  }

  function renderMessage(msg) {
    if (msg.pending) {
      return `
        <div class="chat-msg chat-msg--assistant">
          <div class="chat-bubble chat-bubble--typing"><span></span><span></span><span></span></div>
        </div>`;
    }
    const cls = msg.role === "user" ? "chat-msg--user" : "chat-msg--assistant";
    const text = escapeHtml(msg.text).replace(/\n/g, "<br />");
    return `
      <div class="chat-msg ${cls}">
        <div class="chat-bubble">${text}</div>
        ${msg.role === "assistant" ? renderSources(msg.sources) : ""}
      </div>`;
  }

  function renderMessages() {
    const list = root().querySelector(".chat-messages");
    if (!list) return;
    if (!messages.length) {
      list.innerHTML = `
        <div class="chat-empty">
          ${icon("forum")}
          <p>Hello! I'm the <strong>AKIRS Assistant</strong>. Ask me about PAYE,
          Withholding Tax, AISTIN registration, TCC validation, and more.</p>
        </div>`;
    } else {
      list.innerHTML = messages.map(renderMessage).join("");
    }
    list.scrollTop = list.scrollHeight;
  }

  async function send(preset) {
    const input = root().querySelector(".chat-input");
    if (sending) return;
    const question = (typeof preset === "string" ? preset : input ? input.value : "").trim();
    if (!question) return;

    const base = apiBase();

    sending = true;
    if (input) {
      input.value = "";
      input.style.height = "auto";
    }
    messages.push({ role: "user", text: question });
    const placeholder = { role: "assistant", text: "", pending: true, streaming: true };
    messages.push(placeholder);
    renderMessages();
    updateSendButton();

    try {
      // Stream the answer token-by-token (newline-delimited JSON per frame).
      const resp = await fetch(`${base}/chatbot/chat/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question, collection: KB_COLLECTION }),
      });
      if (!resp.ok || !resp.body) {
        throw new Error(`HTTP ${resp.status}`);
      }

      placeholder.pending = false;
      let buffer = "";
      const reader = resp.body.getReader();
      const decoder = new TextDecoder("utf-8");
      // Throttle re-renders to ~10/s so typing isn't repainted on every token.
      let lastRender = 0;

      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });

        let nl;
        while ((nl = buffer.indexOf("\n")) !== -1) {
          const line = buffer.slice(0, nl).trim();
          buffer = buffer.slice(nl + 1);
          if (!line) continue;

          let frame;
          try {
            frame = JSON.parse(line);
          } catch (_) {
            continue;
          }

          if (frame.type === "sources") {
            placeholder.sources = frame.sources || [];
            renderMessages();
          } else if (frame.type === "delta" && frame.text) {
            placeholder.text += frame.text;
            const now = performance.now();
            if (now - lastRender > 100 || placeholder.text.length - (placeholder._lastLen || 0) > 40) {
              lastRender = now;
              placeholder._lastLen = placeholder.text.length;
              renderMessages();
            }
          } else if (frame.type === "error") {
            throw new Error(frame.detail || "Streaming error");
          }
        }
      }
      if (!placeholder.text) {
        placeholder.text = "I couldn't generate a response.";
      }
    } catch (error) {
      placeholder.pending = false;
      placeholder.text =
        "The AKIRS Assistant is unavailable. Please confirm the backend is running and the local model (Ollama) is up, then try again.";
      placeholder.error = String(error?.message || error);
    } finally {
      sending = false;
      delete placeholder._lastLen;
      renderMessages();
      updateSendButton();
    }
  }

  function updateSendButton() {
    const btn = root().querySelector(".chat-send");
    if (btn) btn.disabled = sending;
  }

  function open() {
    isOpen = true;
    const panel = root().querySelector(".chat-panel");
    const launcher = root().querySelector(".chat-launcher");
    if (panel) panel.classList.add("is-open");
    if (launcher) launcher.setAttribute("aria-expanded", "true");
    const input = root().querySelector(".chat-input");
    if (input) input.focus();
  }

  function close() {
    isOpen = false;
    const panel = root().querySelector(".chat-panel");
    const launcher = root().querySelector(".chat-launcher");
    if (panel) panel.classList.remove("is-open");
    if (launcher) launcher.setAttribute("aria-expanded", "false");
  }

  function toggle() {
    if (isOpen) close();
    else open();
  }

  // Open the panel (mounting it first if needed) and immediately ask *question*.
  // Used by the in-app "Try asking" shortcuts on the assistant page.
  function ask(question) {
    if (question === undefined || question === null) return;
    mount();
    open();
    send(String(question));
  }

  function mount() {
    if (mounted) return;
    const el = root();
    el.innerHTML = `
      <button class="chat-launcher" type="button" aria-label="Open AKIRS Assistant" aria-expanded="false">
        ${icon("forum")}
      </button>
      <section class="chat-panel" role="dialog" aria-label="AKIRS Assistant">
        <header class="chat-panel__header">
          <div class="chat-panel__title">
            ${icon("support_agent")}
            <div>
              <strong>AKIRS Assistant</strong>
              <small>Akwa Ibom State Internal Revenue Service</small>
            </div>
          </div>
          <button class="icon-button chat-close" type="button" aria-label="Close assistant">
            ${icon("close")}
          </button>
        </header>
        <div class="chat-messages" aria-live="polite"></div>
        <form class="chat-input-row">
          <textarea class="chat-input" rows="1" placeholder="Ask about PAYE, WHT, AISTIN, TCC..." aria-label="Message the AKIRS Assistant"></textarea>
          <button class="button button--primary chat-send" type="submit" aria-label="Send message">
            ${icon("send")}
          </button>
        </form>
      </section>
    `;

    el.querySelector(".chat-launcher")?.addEventListener("click", toggle);
    el.querySelector(".chat-close")?.addEventListener("click", close);
    el.querySelector(".chat-input-row")?.addEventListener("submit", (event) => {
      event.preventDefault();
      send();
    });

    const input = el.querySelector(".chat-input");
    if (input) {
      input.addEventListener("keydown", (event) => {
        if (event.key === "Enter" && !event.shiftKey) {
          event.preventDefault();
          send();
        }
      });
      input.addEventListener("input", () => {
        input.style.height = "auto";
        input.style.height = `${Math.min(input.scrollHeight, 120)}px`;
      });
    }

    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && isOpen) close();
    });

    mounted = true;
    renderMessages();
  }

  function removeAssistantNav() {
    document.querySelector('[data-route="assistant"]')?.remove();
    if (window.location.hash.startsWith("#/assistant")) {
      window.location.hash = "#/dashboard";
    }
  }

  // The backend exposes whether the assistant is plugged in (CHATBOT_ENABLED)
  // via /health. Only mount the widget when it is; otherwise strip the nav entry
  // so there is no dead UI pointing at a disabled feature.
  async function boot() {
    let enabled = window.akirsChatbotEnabled;
    if (enabled === undefined) {
      try {
        const res = await fetch(`${apiBase()}/health`);
        const status = res.ok ? await res.json() : null;
        enabled = status ? status.chatbot !== false : true;
      } catch (_) {
        // Backend unreachable — assume enabled so the widget can report the error.
        enabled = true;
      }
    }
    window.akirsChatbotEnabled = enabled;
    if (!enabled) {
      removeAssistantNav();
      return;
    }
    mount();
  }

  window.akirsChat = { mount, open, close, toggle, ask };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
