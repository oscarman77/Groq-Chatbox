/* Chatbox frontend: talks to the REST API, keeps no state beyond the DOM. */

const $ = (selector) => document.querySelector(selector);

const state = {
  user: null,
  mode: "login", // "login" | "register"
  conversations: [],
  activeId: null,
  sending: false,
};

/* ---------- API helper ---------- */

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });

  if (response.status === 204) return null;

  const data = await response.json().catch(() => null);
  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    const detail = data && data.detail;
    if (typeof detail === "string") message = detail;
    else if (Array.isArray(detail) && detail[0]) message = detail[0].msg || message;
    throw new Error(message);
  }
  return data;
}

/* ---------- auth ---------- */

function setAuthMode(mode) {
  state.mode = mode;
  const isLogin = mode === "login";
  $("#auth-submit").textContent = isLogin ? "Log in" : "Create account";
  $("#auth-hint").textContent = isLogin ? "No account yet?" : "Already have an account?";
  $("#auth-toggle").textContent = isLogin ? "Create one" : "Log in";
  $("#password").autocomplete = isLogin ? "current-password" : "new-password";
  $("#auth-error").textContent = "";
}

async function submitAuth(event) {
  event.preventDefault();
  const email = $("#email").value.trim();
  const password = $("#password").value;
  const button = $("#auth-submit");

  $("#auth-error").textContent = "";
  button.disabled = true;
  try {
    const path = state.mode === "login" ? "/api/auth/login" : "/api/auth/register";
    state.user = await api(path, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    await enterApp();
  } catch (error) {
    $("#auth-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
}

async function logout() {
  await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  state.user = null;
  state.conversations = [];
  state.activeId = null;
  $("#app").classList.add("hidden");
  $("#auth").classList.remove("hidden");
  $("#password").value = "";
}

/* ---------- conversations ---------- */

function renderConversations() {
  const nav = $("#conversations");
  nav.innerHTML = "";

  if (state.conversations.length === 0) {
    nav.innerHTML = '<p class="muted small" style="padding:6px">No chats yet.</p>';
    return;
  }

  for (const conversation of state.conversations) {
    const row = document.createElement("div");
    row.className = "conv" + (conversation.id === state.activeId ? " active" : "");

    const label = document.createElement("button");
    label.className = "label";
    label.style.cssText = "border:none;background:transparent;color:inherit;padding:0;text-align:left;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1";
    label.textContent = conversation.title;
    label.addEventListener("click", () => selectConversation(conversation.id));

    const remove = document.createElement("button");
    remove.className = "del";
    remove.title = "Delete chat";
    remove.textContent = "×";
    remove.addEventListener("click", (event) => {
      event.stopPropagation();
      deleteConversation(conversation.id);
    });

    row.append(label, remove);
    nav.append(row);
  }
}

function upsertConversation(conversation) {
  const index = state.conversations.findIndex((item) => item.id === conversation.id);
  if (index === -1) state.conversations.unshift(conversation);
  else state.conversations[index] = conversation;
  renderConversations();
}

async function loadConversations() {
  state.conversations = await api("/api/conversations");
}

async function newChat() {
  const conversation = await api("/api/conversations", {
    method: "POST",
    body: JSON.stringify({}),
  });
  upsertConversation(conversation);
  await selectConversation(conversation.id);
  $("#input").focus();
}

async function deleteConversation(id) {
  await api(`/api/conversations/${id}`, { method: "DELETE" });
  state.conversations = state.conversations.filter((item) => item.id !== id);

  if (state.activeId === id) {
    state.activeId = null;
    $("#chat-title").textContent = "New chat";
    $("#messages").innerHTML = "";
    renderEmpty();
    if (state.conversations[0]) await selectConversation(state.conversations[0].id);
  }
  renderConversations();
}

/* ---------- messages ---------- */

function renderEmpty() {
  if ($("#messages").children.length > 0) return;
  const empty = document.createElement("div");
  empty.className = "empty";
  empty.innerHTML =
    "<p>Start a conversation. Everything you send is stored in SQLite under your account.</p>";
  $("#messages").append(empty);
}

function addMessage(message) {
  const wrapper = document.createElement("div");
  wrapper.className = `msg ${message.role}`;

  const role = document.createElement("div");
  role.className = "role";
  role.textContent = message.role === "user" ? "You" : "Assistant";

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = message.content;

  wrapper.append(role, bubble);
  $("#messages").append(wrapper);
  return wrapper;
}

function showTyping() {
  const wrapper = document.createElement("div");
  wrapper.className = "msg assistant typing";
  wrapper.innerHTML = '<div class="role">Assistant</div><div class="bubble"><i></i><i></i><i></i></div>';
  $("#messages").append(wrapper);
  return wrapper;
}

function scrollToBottom() {
  const box = $("#messages");
  box.scrollTop = box.scrollHeight;
}

async function selectConversation(id) {
  state.activeId = id;
  const conversation = state.conversations.find((item) => item.id === id);
  $("#chat-title").textContent = conversation ? conversation.title : "Chat";
  renderConversations();

  const messages = await api(`/api/conversations/${id}/messages`);
  $("#messages").innerHTML = "";
  if (messages.length === 0) renderEmpty();
  for (const message of messages) addMessage(message);
  scrollToBottom();
}

/* ---------- sending ---------- */

async function sendMessage(event) {
  event?.preventDefault();
  const input = $("#input");
  const content = input.value.trim();
  if (!content || state.sending) return;

  // Lock and clear synchronously, before any await, so a fast double
  // Enter/click can never post the same message twice.
  state.sending = true;
  $("#send").disabled = true;
  input.value = "";
  autoGrow(input);

  let typing = null;
  try {
    if (!state.activeId) await newChat();
    if (!state.activeId) throw new Error("Could not open a chat");

    $("#messages").querySelector(".empty")?.remove();
    addMessage({ role: "user", content });
    typing = showTyping();
    scrollToBottom();

    const chat = await api(`/api/conversations/${state.activeId}/messages`, {
      method: "POST",
      body: JSON.stringify({ content }),
    });

    const reply = chat.messages.find((message) => message.role === "assistant");
    if (reply) addMessage(reply);
    upsertConversation(chat.conversation);
    $("#chat-title").textContent = chat.conversation.title;
  } catch (error) {
    addMessage({ role: "assistant", content: `Something went wrong: ${error.message}` });
  } finally {
    if (typing) typing.remove();
    state.sending = false;
    $("#send").disabled = false;
    input.focus();
    scrollToBottom();
  }
}

/* ---------- wiring ---------- */

function autoGrow(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = Math.min(textarea.scrollHeight, 160) + "px";
}

async function enterApp() {
  $("#auth").classList.add("hidden");
  $("#app").classList.remove("hidden");
  $("#who").textContent = state.user.email;

  const health = await api("/api/health").catch(() => null);
  if (health?.mock_mode) $("#mode-badge").classList.remove("hidden");

  await loadConversations();
  renderConversations();

  if (state.conversations[0]) {
    await selectConversation(state.conversations[0].id);
  } else {
    renderEmpty();
  }
  $("#input").focus();
}

async function boot() {
  $("#auth-form").addEventListener("submit", submitAuth);
  $("#auth-toggle").addEventListener("click", (event) => {
    event.preventDefault();
    setAuthMode(state.mode === "login" ? "register" : "login");
  });
  $("#logout").addEventListener("click", logout);
  $("#new-chat").addEventListener("click", newChat);
  $("#composer").addEventListener("submit", sendMessage);
  $("#input").addEventListener("input", (event) => autoGrow(event.target));
  $("#input").addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      $("#composer").requestSubmit(); // one path: the form submit handler
    }
  });

  try {
    state.user = await api("/api/auth/me");
    await enterApp();
  } catch {
    setAuthMode("login");
    $("#auth").classList.remove("hidden");
  }
}

boot();
