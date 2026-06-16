(function() {
  const currentScript = document.currentScript;
  const embedKey = currentScript ? currentScript.getAttribute('data-embed-key') : null;
  
  if (!embedKey) {
    console.error("AKIRS Widget: Missing data-embed-key attribute on script tag.");
    return;
  }
  
  const baseUrl = currentScript.getAttribute('data-base-url') || "http://localhost:8000/widget-api";
  
  // Inject scoped styles
  const style = document.createElement("style");
  style.textContent = `
    #akirs-widget-container {
      position: fixed;
      bottom: 20px;
      right: 20px;
      z-index: 999999;
      font-family: system-ui, -apple-system, sans-serif;
    }
    #akirs-widget-launcher {
      width: 60px;
      height: 60px;
      border-radius: 50%;
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      border: none;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: transform 0.2s, box-shadow 0.2s;
    }
    #akirs-widget-launcher:hover {
      transform: scale(1.05);
      box-shadow: 0 6px 16px rgba(0,0,0,0.2);
    }
    #akirs-widget-launcher svg {
      width: 32px;
      height: 32px;
      fill: currentColor;
    }
    #akirs-widget-chat {
      position: absolute;
      bottom: 80px;
      right: 0;
      width: 350px;
      height: 500px;
      background: #ffffff;
      border-radius: 12px;
      box-shadow: 0 8px 24px rgba(0,0,0,0.15);
      display: flex;
      flex-direction: column;
      overflow: hidden;
      transform-origin: bottom right;
      transition: opacity 0.3s, transform 0.3s;
      opacity: 0;
      transform: scale(0.95);
      pointer-events: none;
      border: 1px solid #e5e7eb;
    }
    #akirs-widget-chat.akirs-open {
      opacity: 1;
      transform: scale(1);
      pointer-events: auto;
    }
    .akirs-header {
      background: linear-gradient(135deg, #2563eb, #1d4ed8);
      color: white;
      padding: 16px;
      font-weight: 600;
      display: flex;
      justify-content: space-between;
      align-items: center;
    }
    .akirs-close {
      background: none;
      border: none;
      color: white;
      cursor: pointer;
      opacity: 0.8;
      transition: opacity 0.2s;
    }
    .akirs-close:hover {
      opacity: 1;
    }
    .akirs-messages {
      flex: 1;
      padding: 16px;
      overflow-y: auto;
      display: flex;
      flex-direction: column;
      gap: 12px;
      background: #f9fafb;
    }
    .akirs-msg {
      max-width: 85%;
      padding: 10px 14px;
      border-radius: 12px;
      font-size: 14px;
      line-height: 1.4;
      word-wrap: break-word;
    }
    .akirs-msg.akirs-user {
      align-self: flex-end;
      background: #2563eb;
      color: white;
      border-bottom-right-radius: 4px;
    }
    .akirs-msg.akirs-bot {
      align-self: flex-start;
      background: #ffffff;
      color: #1f2937;
      border: 1px solid #e5e7eb;
      border-bottom-left-radius: 4px;
    }
    .akirs-input-area {
      padding: 12px;
      background: #ffffff;
      border-top: 1px solid #e5e7eb;
      display: flex;
      gap: 8px;
    }
    .akirs-input {
      flex: 1;
      border: 1px solid #e5e7eb;
      border-radius: 20px;
      padding: 8px 16px;
      font-size: 14px;
      outline: none;
      transition: border-color 0.2s;
    }
    .akirs-input:focus {
      border-color: #2563eb;
    }
    .akirs-send {
      background: #2563eb;
      color: white;
      border: none;
      border-radius: 50%;
      width: 36px;
      height: 36px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      transition: background 0.2s;
    }
    .akirs-send:hover {
      background: #1d4ed8;
    }
    .akirs-send:disabled {
      background: #9ca3af;
      cursor: not-allowed;
    }
    .akirs-loading {
      align-self: flex-start;
      display: flex;
      gap: 4px;
      padding: 12px 14px;
      background: #ffffff;
      border: 1px solid #e5e7eb;
      border-radius: 12px;
      border-bottom-left-radius: 4px;
    }
    .akirs-dot {
      width: 6px;
      height: 6px;
      background: #9ca3af;
      border-radius: 50%;
      animation: akirs-bounce 1.4s infinite ease-in-out both;
    }
    .akirs-dot:nth-child(1) { animation-delay: -0.32s; }
    .akirs-dot:nth-child(2) { animation-delay: -0.16s; }
    @keyframes akirs-bounce {
      0%, 80%, 100% { transform: scale(0); }
      40% { transform: scale(1); }
    }
  `;
  document.head.appendChild(style);

  // Inject UI
  const container = document.createElement("div");
  container.id = "akirs-widget-container";
  container.innerHTML = `
    <div id="akirs-widget-chat">
      <div class="akirs-header">
        AKIRS Assistant
        <button class="akirs-close">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
        </button>
      </div>
      <div class="akirs-messages">
        <div class="akirs-msg akirs-bot">Hello! How can I help you today?</div>
      </div>
      <form class="akirs-input-area">
        <input type="text" class="akirs-input" placeholder="Type a message..." required autocomplete="off">
        <button type="submit" class="akirs-send">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
        </button>
      </form>
    </div>
    <button id="akirs-widget-launcher">
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>
    </button>
  `;
  document.body.appendChild(container);

  // Logic
  const launcher = container.querySelector("#akirs-widget-launcher");
  const chat = container.querySelector("#akirs-widget-chat");
  const closeBtn = container.querySelector(".akirs-close");
  const form = container.querySelector("form");
  const input = container.querySelector(".akirs-input");
  const messagesList = container.querySelector(".akirs-messages");
  const submitBtn = container.querySelector(".akirs-send");

  function toggleChat() {
    chat.classList.toggle("akirs-open");
    if (chat.classList.contains("akirs-open")) {
      input.focus();
    }
  }

  launcher.addEventListener("click", toggleChat);
  closeBtn.addEventListener("click", toggleChat);

  function appendMessage(text, isUser) {
    const div = document.createElement("div");
    div.className = `akirs-msg ${isUser ? 'akirs-user' : 'akirs-bot'}`;
    div.textContent = text;
    messagesList.appendChild(div);
    messagesList.scrollTop = messagesList.scrollHeight;
  }

  function appendLoading() {
    const div = document.createElement("div");
    div.className = "akirs-loading";
    div.innerHTML = '<div class="akirs-dot"></div><div class="akirs-dot"></div><div class="akirs-dot"></div>';
    messagesList.appendChild(div);
    messagesList.scrollTop = messagesList.scrollHeight;
    return div;
  }

  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = input.value.trim();
    if (!text) return;

    input.value = "";
    appendMessage(text, true);
    const loadingEl = appendLoading();
    input.disabled = true;
    submitBtn.disabled = true;

    try {
      const response = await fetch(`${baseUrl}/chatbot/chat`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "x-embed-key": embedKey
        },
        body: JSON.stringify({
          question: text,
          collection: "akirs_kb",
          top_k: 5,
          temperature: 0.1
        })
      });

      if (!response.ok) {
        throw new Error("API request failed");
      }

      const data = await response.json();
      loadingEl.remove();
      appendMessage(data.answer, false);
    } catch (err) {
      console.error(err);
      loadingEl.remove();
      appendMessage("Sorry, an error occurred while connecting to the assistant.", false);
    } finally {
      input.disabled = false;
      submitBtn.disabled = false;
      input.focus();
    }
  });

})();
