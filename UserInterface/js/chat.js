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

  async function send() {
    const input = root().querySelector(".chat-input");
    if (!input || sending) return;
    const question = input.value.trim();
    if (!question) return;

    if (!window.akirsApi?.sendChat) {
      messages.push({
        role: "assistant",
        text: "The assistant isn't available right now. Please reload the page once the backend is running.",
      });
      renderMessages();
      return;
    }

    sending = true;
    input.value = "";
    input.style.height = "auto";
    messages.push({ role: "user", text: question });
    const placeholder = { role: "assistant", text: "", pending: true };
    messages.push(placeholder);
    renderMessages();
    updateSendButton();

    try {
      const result = await window.akirsApi.sendChat(question, KB_COLLECTION);
      placeholder.pending = false;
      placeholder.text = (result && result.answer) || "I couldn't generate a response.";
      placeholder.sources = (result && result.sources) || [];
    } catch (error) {
      placeholder.pending = false;
      placeholder.text =
        "The AKIRS Assistant is unavailable. Please confirm the backend is running and the local model (Ollama) is up, then try again.";
      placeholder.error = String(error?.message || error);
    } finally {
      sending = false;
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

  window.akirsChat = { mount, open, close, toggle };

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", mount);
  } else {
    mount();
  }
})();
