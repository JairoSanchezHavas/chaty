(function () {
  "use strict";

  // ── Config ──────────────────────────────────────────────────────────────
  const API_BASE = "http://localhost:8000";
  const script = document.currentScript || document.querySelector("script[data-tenant]");
  const TENANT_ID = script ? script.getAttribute("data-tenant") : "pharmagen";

  // ── Helpers ──────────────────────────────────────────────────────────────
  function uuidv4() {
    return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, function (c) {
      const r = (Math.random() * 16) | 0;
      return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
    });
  }

  const storageKey = `chaty_session_${TENANT_ID}`;
  let sessionId = localStorage.getItem(storageKey);
  if (!sessionId) {
    sessionId = uuidv4();
    localStorage.setItem(storageKey, sessionId);
  }

  // ── Shadow DOM host ──────────────────────────────────────────────────────
  const host = document.createElement("div");
  host.id = "chaty-widget-host";
  document.body.appendChild(host);
  const shadow = host.attachShadow({ mode: "open" });

  // ── Styles ───────────────────────────────────────────────────────────────
  const style = document.createElement("style");
  style.textContent = `
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    #chaty-bubble {
      position: fixed;
      bottom: 24px;
      right: 24px;
      width: 56px;
      height: 56px;
      border-radius: 50%;
      background: var(--brand-color, #1A1A2E);
      box-shadow: 0 4px 16px rgba(0,0,0,0.25);
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 9999;
      transition: transform .2s ease;
    }
    #chaty-bubble:hover { transform: scale(1.08); }
    #chaty-bubble svg { width: 26px; height: 26px; fill: #fff; }

    #chaty-panel {
      position: fixed;
      bottom: 92px;
      right: 24px;
      width: 360px;
      max-height: 560px;
      display: flex;
      flex-direction: column;
      border-radius: 16px;
      background: #fff;
      box-shadow: 0 8px 32px rgba(0,0,0,0.18);
      z-index: 9998;
      overflow: hidden;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      font-size: 14px;
      opacity: 0;
      transform: translateY(16px) scale(0.97);
      pointer-events: none;
      transition: opacity .22s ease, transform .22s ease;
    }
    #chaty-panel.open {
      opacity: 1;
      transform: translateY(0) scale(1);
      pointer-events: all;
    }

    #chaty-header {
      background: var(--brand-color, #1A1A2E);
      color: #fff;
      padding: 14px 18px;
      display: flex;
      align-items: center;
      gap: 10px;
    }
    #chaty-header .avatar {
      width: 36px;
      height: 36px;
      border-radius: 50%;
      background: var(--brand-accent, #E94560);
      display: flex;
      align-items: center;
      justify-content: center;
      font-weight: 700;
      font-size: 16px;
      flex-shrink: 0;
    }
    #chaty-header .info { flex: 1; }
    #chaty-header .name { font-weight: 600; font-size: 15px; }
    #chaty-header .status { font-size: 11px; opacity: .75; }
    #chaty-header .close-btn {
      background: none;
      border: none;
      color: #fff;
      cursor: pointer;
      font-size: 20px;
      opacity: .8;
      padding: 0 4px;
    }
    #chaty-header .close-btn:hover { opacity: 1; }

    #chaty-messages {
      flex: 1;
      overflow-y: auto;
      padding: 16px;
      display: flex;
      flex-direction: column;
      gap: 10px;
      background: #f7f8fa;
    }
    .msg {
      max-width: 84%;
      padding: 10px 14px;
      border-radius: 14px;
      line-height: 1.5;
      word-break: break-word;
    }
    .msg.bot {
      background: #fff;
      border: 1px solid #e5e7eb;
      border-bottom-left-radius: 4px;
      align-self: flex-start;
    }
    .msg.user {
      background: var(--brand-color, #0A2E5C);
      color: #fff;
      border-bottom-right-radius: 4px;
      align-self: flex-end;
    }
    .msg.typing { opacity: .6; font-style: italic; }

    /* Markdown rendering dentro del bot */
    .msg.bot p { margin: 0 0 6px 0; }
    .msg.bot p:last-child { margin-bottom: 0; }
    .msg.bot strong { font-weight: 700; }
    .msg.bot em { font-style: italic; }
    .msg.bot ul, .msg.bot ol { padding-left: 18px; margin: 4px 0; }
    .msg.bot li { margin-bottom: 2px; }
    .msg.bot a { color: var(--brand-accent, #00A878); text-decoration: underline; }
    .msg.bot a:hover { opacity: .8; }
    .msg.bot hr { border: none; border-top: 1px solid #e5e7eb; margin: 8px 0; }

    /* Imágenes de producto */
    .msg.bot .product-img {
      display: block;
      max-width: 100%;
      width: 220px;
      border-radius: 8px;
      margin: 8px 0 4px 0;
      border: 1px solid #e5e7eb;
      box-shadow: 0 2px 8px rgba(0,0,0,.08);
    }

    #chaty-input-area {
      padding: 12px 14px;
      display: flex;
      gap: 8px;
      border-top: 1px solid #e5e7eb;
      background: #fff;
    }
    #chaty-input {
      flex: 1;
      border: 1px solid #d1d5db;
      border-radius: 10px;
      padding: 9px 14px;
      font-size: 14px;
      outline: none;
      resize: none;
      line-height: 1.4;
      font-family: inherit;
      transition: border-color .15s;
    }
    #chaty-input:focus { border-color: var(--brand-accent, #E94560); }
    #chaty-send {
      background: var(--brand-color, #1A1A2E);
      color: #fff;
      border: none;
      border-radius: 10px;
      width: 40px;
      height: 40px;
      cursor: pointer;
      display: flex;
      align-items: center;
      justify-content: center;
      flex-shrink: 0;
      transition: opacity .15s;
    }
    #chaty-send:hover { opacity: .85; }
    #chaty-send:disabled { opacity: .4; cursor: not-allowed; }
    #chaty-send svg { width: 18px; height: 18px; fill: #fff; }

    #chaty-footer {
      text-align: center;
      font-size: 10px;
      color: #9ca3af;
      padding: 6px;
      background: #fff;
    }

    @media (max-width: 420px) {
      #chaty-panel {
        width: calc(100vw - 16px);
        right: 8px;
        bottom: 80px;
      }
    }
  `;
  shadow.appendChild(style);

  // ── Markup ────────────────────────────────────────────────────────────────
  const bubble = document.createElement("div");
  bubble.id = "chaty-bubble";
  bubble.innerHTML = `<svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
    <path d="M20 2H4a2 2 0 0 0-2 2v18l4-4h14a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2z"/>
  </svg>`;

  const panel = document.createElement("div");
  panel.id = "chaty-panel";
  panel.innerHTML = `
    <div id="chaty-header">
      <div class="avatar">T</div>
      <div class="info">
        <div class="name">Rep. Médico Pharmagen</div>
        <div class="status">En línea</div>
      </div>
      <button class="close-btn" aria-label="Cerrar chat">✕</button>
    </div>
    <div id="chaty-messages"></div>
    <div id="chaty-input-area">
      <textarea id="chaty-input" rows="1" placeholder="Escribe tu mensaje…" maxlength="500"></textarea>
      <button id="chaty-send" aria-label="Enviar">
        <svg viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>
      </button>
    </div>
    <div id="chaty-footer">Powered by <strong>Chaty</strong></div>
  `;

  shadow.appendChild(bubble);
  shadow.appendChild(panel);

  // ── State ─────────────────────────────────────────────────────────────────
  let isOpen = false;
  let isWaiting = false;
  let config = { name: "Rep. Médico Pharmagen", greeting: "Buenos días, Doctor/a. ¿En qué puedo orientarle?", brand_color: "#0A2E5C", brand_accent: "#00A878" };

  // ── Apply branding ────────────────────────────────────────────────────────
  function applyBranding(cfg) {
    config = cfg;
    const root = shadow.host;
    root.style.setProperty("--brand-color", cfg.brand_color || "#1A1A2E");
    root.style.setProperty("--brand-accent", cfg.brand_accent || "#E94560");

    const nameEl = shadow.querySelector(".name");
    const avatarEl = shadow.querySelector(".avatar");
    if (nameEl) nameEl.textContent = cfg.name || "Asistente";
    if (avatarEl) avatarEl.textContent = (cfg.name || "A")[0].toUpperCase();
  }

  // ── Load config from API ──────────────────────────────────────────────────
  fetch(`${API_BASE}/api/widget/config/${TENANT_ID}`)
    .then((r) => r.ok ? r.json() : null)
    .then((cfg) => {
      if (cfg) {
        applyBranding(cfg);
        // Mostrar mensaje de bienvenida al abrir por primera vez
        config = cfg;
      }
    })
    .catch(() => {});

  // ── Chat messages ─────────────────────────────────────────────────────────
  const messagesEl = shadow.getElementById("chaty-messages");
  const inputEl = shadow.getElementById("chaty-input");
  const sendBtn = shadow.getElementById("chaty-send");

  // Convierte markdown básico + imágenes a HTML seguro
  function renderMarkdown(text) {
    let html = text
      // Escapar HTML primero
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      // Imágenes: ![alt](url) — ANTES de otros patrones
      .replace(/!\[([^\]]*)\]\((https?:\/\/[^)]+|\/[^)]+)\)/g,
        '<img src="$2" alt="$1" class="product-img" loading="lazy">')
      // Links: [text](url)
      .replace(/\[([^\]]+)\]\((https?:\/\/[^)]+)\)/g,
        '<a href="$2" target="_blank" rel="noopener">$1</a>')
      // Negrita **text**
      .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
      // Cursiva *text*
      .replace(/\*([^*]+)\*/g, "<em>$1</em>")
      // HR ---
      .replace(/^---$/gm, "<hr>")
      // Listas — líneas que empiezan con "- " o "• "
      .replace(/^[•\-]\s+(.+)$/gm, "<li>$1</li>")
      // Listas numeradas
      .replace(/^\d+\.\s+(.+)$/gm, "<li>$1</li>")
      // Saltos de línea dobles → párrafo
      .replace(/\n\n+/g, "</p><p>")
      // Saltos simples → <br>
      .replace(/\n/g, "<br>");

    // Envolver <li> consecutivos en <ul>
    html = html.replace(/(<li>.*?<\/li>)(\s*<br>\s*)*(<li>|$)/g, "$1$3");
    html = html.replace(/(<li>[\s\S]*?<\/li>)+/g, "<ul>$&</ul>");

    return `<p>${html}</p>`;
  }

  function addMessage(text, role) {
    const div = document.createElement("div");
    div.className = `msg ${role}`;
    if (role === "bot" || role === "bot typing") {
      div.innerHTML = role === "bot" ? renderMarkdown(text) : text;
    } else {
      div.textContent = text;
    }
    messagesEl.appendChild(div);
    messagesEl.scrollTop = messagesEl.scrollHeight;
    return div;
  }

  function updateMessage(el, text, role) {
    if (role === "bot") {
      el.innerHTML = renderMarkdown(text);
    } else {
      el.textContent = text;
    }
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  function showTyping() {
    return addMessage("Escribiendo…", "bot typing");
  }

  function removeTyping(el) {
    if (el && el.parentNode) el.parentNode.removeChild(el);
  }

  // ── Send message ──────────────────────────────────────────────────────────
  async function sendMessage() {
    const text = inputEl.value.trim();
    if (!text || isWaiting) return;

    inputEl.value = "";
    inputEl.style.height = "auto";
    addMessage(text, "user");
    isWaiting = true;
    sendBtn.disabled = true;

    const typingEl = showTyping();

    try {
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
        body: JSON.stringify({ tenant_id: TENANT_ID, session_id: sessionId, message: text }),
      });

      if (!response.ok) throw new Error(`Error ${response.status}`);

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let botReply = "";
      let botMsgEl = null;

      removeTyping(typingEl);

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop();

        let currentEvent = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            currentEvent = line.slice(7).trim();
            continue;
          }
          if (line.startsWith("data: ")) {
            const data = line.slice(6);
            if (data === "" || data === "[DONE]") continue;

            if (currentEvent === "token") {
              // Acumular tokens de streaming
              botReply += data;
            } else if (currentEvent === "message") {
              // Mensaje completo (fallback retrocompatible)
              try {
                const parsed = JSON.parse(data);
                botReply = parsed.content || data;
              } catch {
                botReply = data;
              }
            } else {
              continue;
            }

            if (!botMsgEl) {
              botMsgEl = addMessage(botReply, "bot");
            } else {
              updateMessage(botMsgEl, botReply, "bot");
              messagesEl.scrollTop = messagesEl.scrollHeight;
            }
          }
        }
      }

      if (!botMsgEl && botReply) {
        addMessage(botReply, "bot");
      }
    } catch (err) {
      removeTyping(typingEl);
      addMessage("Lo siento, hubo un error. Por favor intenta de nuevo.", "bot");
      console.error("[Chaty]", err);
    } finally {
      isWaiting = false;
      sendBtn.disabled = false;
      inputEl.focus();
    }
  }

  // ── Toggle panel ──────────────────────────────────────────────────────────
  function openPanel() {
    if (isOpen) return;
    isOpen = true;
    panel.classList.add("open");
    inputEl.focus();

    if (messagesEl.children.length === 0) {
      addMessage(config.greeting || "¡Hola! ¿En qué puedo ayudarte?", "bot");
    }
  }

  function closePanel() {
    isOpen = false;
    panel.classList.remove("open");
  }

  // ── Events ────────────────────────────────────────────────────────────────
  bubble.addEventListener("click", () => (isOpen ? closePanel() : openPanel()));
  shadow.querySelector(".close-btn").addEventListener("click", closePanel);
  sendBtn.addEventListener("click", sendMessage);

  inputEl.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  });

  // Auto-resize textarea
  inputEl.addEventListener("input", () => {
    inputEl.style.height = "auto";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 96) + "px";
  });
})();
