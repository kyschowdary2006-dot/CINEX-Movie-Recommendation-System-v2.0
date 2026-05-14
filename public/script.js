/* =============================================
   CINEX  script.js  v3.0
   Backend routes (app/api/routes/):
     /api/users/*         → users.py
     /api/movies/*        → movies.py
     /api/ratings/*       → ratings.py
     /api/ratings/comments/* → ratings.py
     /api/recommend/*     → recommend.py
     /api/agent/chat      → main.py
     /api/ml/*            → main.py
============================================= */

/* ── TMDB ── */
const TMDB_KEY = "9e3656f495ccd03d580d88c34715d4a0";
const TMDB     = "https://api.themoviedb.org/3";
const IMG_W    = "https://image.tmdb.org/t/p/w500";
const IMG_OG   = "https://image.tmdb.org/t/p/original";
const IMG_FACE = "https://image.tmdb.org/t/p/w185";

/* ── API route prefixes ── */
const R = {
  auth:      "/api/users",
  watchlist: "/api/movies",
  ratings:   "/api/ratings",
  recommend: "/api/recommend",
  agent:     "/api/agent",
  ml:        "/api/ml",
};

/* ══════════════════════════════════════════
   EMAILJS — paste your 3 keys from emailjs.com
   1. Sign up free at https://emailjs.com
   2. Email Services → Add Gmail / Outlook
   3. Email Templates → Create template with:
        {{to_email}}  {{to_name}}  {{otp}}
   4. Account → API Keys → copy Public Key
══════════════════════════════════════════ */
const EMAILJS_PUBLIC_KEY  = "nND4Wew7AcSBmNkXn";
const EMAILJS_SERVICE_ID  = "service_vz2h2p6";
const EMAILJS_TEMPLATE_ID = "template_6xnh3sa";

const EMAILJS_CONFIGURED = () =>
  ![EMAILJS_PUBLIC_KEY, EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID]
    .some(v => v.startsWith("YOUR_"));

/* Init EmailJS once at page load */
(function initEmailJS() {
  try {
    if (EMAILJS_CONFIGURED()) {
      emailjs.init({ publicKey: EMAILJS_PUBLIC_KEY });
      console.info("[CINEX] EmailJS initialised ✓");
    }
  } catch (e) { console.warn("[CINEX] EmailJS init:", e); }
})();

/* ─────────────────────────────────────────
   OTP STATE  (in-memory only)
───────────────────────────────────────── */
const otpState = {
  code: null, email: null, expiresAt: null,
  expiryTimer: null, resendTimer: null,
};

/* ─────────────────────────────────────────
   APP STATE
───────────────────────────────────────── */
const state = {
  genre: "", lang: "", page: 1, totalPages: 1,
  mode: "popular", searchQuery: "",
};
let genreMap   = {};
let heroMovies = [], heroIndex = 0, heroTimer = null;
let currentMovieId  = null;
let currentMovieTitle = null;

/* ─────────────────────────────────────────
   DOM REFS
───────────────────────────────────────── */
const container    = document.getElementById("movies");
const spinner      = document.getElementById("loadingSpinner");
const pageInfo     = document.getElementById("pageInfo");
const prevBtn      = document.getElementById("prevPage");
const nextBtn      = document.getElementById("nextPage");
const sectionTitle = document.getElementById("sectionTitle");
const modal        = document.getElementById("modal");
const trailerModal = document.getElementById("trailerModal");
const authModal    = document.getElementById("authModal");
const searchInput  = document.getElementById("searchInput");
const dropdown     = document.getElementById("searchDropdown");

/* ─────────────────────────────────────────
   UTILITIES
───────────────────────────────────────── */
function setLoading(on) { spinner.classList.toggle("hidden", !on); }

function showSkeletons(n = 12) {
  container.innerHTML = Array.from({ length: n }, (_, i) =>
    `<div class="skeleton skeleton-card" style="animation-delay:${i * 0.04}s"></div>`
  ).join("");
}

async function tmdbFetch(path) {
  const r = await fetch(`${TMDB}${path}`);
  if (!r.ok) throw new Error(`TMDB ${r.status}`);
  return r.json();
}

function debounce(fn, ms) {
  let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); };
}

function escHtml(s) {
  return String(s).replace(/&/g,"&amp;").replace(/</g,"&lt;")
                  .replace(/>/g,"&gt;").replace(/"/g,"&quot;");
}

function timeAgo(iso) {
  const d = (Date.now() - new Date(iso)) / 1000;
  if (d < 60)    return "just now";
  if (d < 3600)  return `${Math.floor(d/60)}m ago`;
  if (d < 86400) return `${Math.floor(d/3600)}h ago`;
  return `${Math.floor(d/86400)}d ago`;
}

/* ─────────────────────────────────────────
   BACKEND API HELPER
───────────────────────────────────────── */
function getToken()  { return localStorage.getItem("cinex_token"); }
function getUser() {
  try { return JSON.parse(localStorage.getItem("cinex_user") || "null"); }
  catch { return null; }
}
function setAuth(token, user) {
  localStorage.setItem("cinex_token", token);
  localStorage.setItem("cinex_user",  JSON.stringify(user));
}
function clearAuth() {
  localStorage.removeItem("cinex_token");
  localStorage.removeItem("cinex_user");
}

async function apiFetch(path, opts = {}) {
  const token   = getToken();
  const headers = { "Content-Type": "application/json", ...(opts.headers ?? {}) };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  const res = await fetch(path, { ...opts, headers });

  if (res.status === 401) { clearAuth(); renderAuthState(); throw new Error("Unauthorized"); }
  if (res.status === 204) return null;

  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail ?? data.error ?? `HTTP ${res.status}`);
  return data;
}

/* ─────────────────────────────────────────
   AUTH STATE
───────────────────────────────────────── */
function renderAuthState() {
  const user = getUser();
  document.getElementById("userArea").classList.toggle("hidden", !user);
  document.getElementById("loginTrigger").classList.toggle("hidden", !!user);
  if (user) document.getElementById("userGreeting").textContent = `👤 ${user.username}`;
  renderWatchlistPanel();
}

/* ─────────────────────────────────────────
   AUTH MODAL
───────────────────────────────────────── */
function openAuthModal(tab = "login") { authModal.classList.add("show"); switchAuthTab(tab); }
function closeAuthModal() {
  authModal.classList.remove("show");
  clearOtpTimers(); otpState.code = null;
  document.getElementById("loginError").textContent    = "";
  document.getElementById("registerError").textContent = "";
  setRegStep(1);
}
function switchAuthTab(w) {
  document.querySelectorAll(".auth-tab").forEach(t => t.classList.toggle("active", t.dataset.tab === w));
  document.getElementById("loginForm").classList.toggle("hidden",    w !== "login");
  document.getElementById("registerForm").classList.toggle("hidden", w !== "register");
}

document.querySelectorAll(".auth-tab").forEach(t => { t.onclick = () => switchAuthTab(t.dataset.tab); });
document.getElementById("loginTrigger").onclick = () => openAuthModal("login");
document.getElementById("closeAuth").onclick     = closeAuthModal;
authModal.onclick = e => { if (e.target === authModal) closeAuthModal(); };
document.getElementById("loginPassword")
  .addEventListener("keydown", e => { if (e.key === "Enter") document.getElementById("loginBtn").click(); });

/* ── LOGIN → POST /api/users/login ── */
document.getElementById("loginBtn").onclick = async () => {
  const btn   = document.getElementById("loginBtn");
  const email = document.getElementById("loginEmail").value.trim();
  const pass  = document.getElementById("loginPassword").value;
  const errEl = document.getElementById("loginError");
  errEl.textContent = "";

  if (!email || !pass) { errEl.textContent = "Please fill in all fields."; return; }

  setSubmitting(btn, true, "Sign In");
  try {
    const data = await apiFetch(`${R.auth}/login`, {
      method: "POST",
      body: JSON.stringify({ email, password: pass }),
    });
    setAuth(data.token, data.user);
    closeAuthModal(); renderAuthState();
    await syncWatchlist();
    if (currentMovieId) refreshRatingAndComments(currentMovieId);
  } catch (err) {
    errEl.textContent = err.message.includes("Unauthorized") ? "Invalid email or password." : err.message;
  } finally { setSubmitting(btn, false, "Sign In"); }
};

/* ── LOGOUT ── */
document.getElementById("logoutBtn").onclick = () => {
  clearAuth(); renderAuthState();
  if (currentMovieId) refreshRatingAndComments(currentMovieId);
};

function setSubmitting(btn, on, label) {
  btn.disabled = on; btn.textContent = on ? "" : label;
  btn.classList.toggle("loading", on);
}

/* ─────────────────────────────────────────
   OTP
───────────────────────────────────────── */
function generateOtp() { return String(Math.floor(100000 + Math.random() * 900000)); }

async function sendOtpEmail(email, username, code) {
  if (!EMAILJS_CONFIGURED()) {
    console.warn(`[CINEX DEV] OTP for ${email}: ${code}`);
    showInlineOtp(code);
    return;
  }
  const result = await emailjs.send(EMAILJS_SERVICE_ID, EMAILJS_TEMPLATE_ID,
    { to_email: email, to_name: username, otp: code });
  if (result.status !== 200) throw new Error(`EmailJS ${result.status}: ${result.text}`);
  console.info(`[CINEX] OTP sent to ${email} ✓`);
}

function showInlineOtp(code) {
  document.getElementById("devOtpBanner")?.remove();
  const b = document.createElement("div");
  b.id = "devOtpBanner";
  b.style.cssText = "background:rgba(232,184,75,0.12);border:1.5px solid rgba(232,184,75,0.5);border-radius:8px;padding:14px 18px;margin:0 0 14px;text-align:center;animation:cardIn 0.3s ease;";
  b.innerHTML = `
    <div style="font-family:var(--font-heading);font-size:0.7rem;color:var(--muted);letter-spacing:2px;text-transform:uppercase;margin-bottom:8px">Dev Mode — EmailJS not configured</div>
    <div style="font-family:var(--font-heading);font-size:2rem;font-weight:700;letter-spacing:8px;color:var(--gold);margin-bottom:6px">${code}</div>
    <div style="font-size:0.75rem;color:var(--muted)">Copy this code and paste it into the boxes below</div>`;
  document.getElementById("regStep2")?.insertBefore(b, document.getElementById("regStep2").firstChild);
}

function startOtpExpiry() {
  clearOtpTimers();
  otpState.expiresAt = Date.now() + 10 * 60 * 1000;
  otpState.expiryTimer = setInterval(() => {
    const left = otpState.expiresAt - Date.now();
    const cd   = document.getElementById("otpCountdown");
    if (!cd) { clearOtpTimers(); return; }
    if (left <= 0) {
      clearOtpTimers(); otpState.code = null;
      cd.textContent = "00:00";
      document.getElementById("otpTimerLabel")?.classList.add("expired");
      showOtpError("Code expired. Go back and resend.");
      document.getElementById("verifyOtpBtn").disabled = true;
      return;
    }
    cd.textContent = `${String(Math.floor(left/60000)).padStart(2,"0")}:${String(Math.floor((left%60000)/1000)).padStart(2,"0")}`;
  }, 1000);
}

function startResendCooldown() {
  let secs = 60;
  const btn  = document.getElementById("resendOtpBtn");
  const disp = document.getElementById("resendCountdown");
  btn.disabled = true;
  otpState.resendTimer = setInterval(() => {
    secs--;
    if (disp) disp.textContent = secs;
    if (secs <= 0) { clearInterval(otpState.resendTimer); if (btn) { btn.disabled = false; btn.textContent = "Resend code"; } }
  }, 1000);
}

function clearOtpTimers() { clearInterval(otpState.expiryTimer); clearInterval(otpState.resendTimer); }

function resetOtpBoxes() {
  document.querySelectorAll(".otp-box").forEach(b => { b.value = ""; b.classList.remove("filled","error"); });
  document.querySelectorAll(".otp-box")[0]?.focus();
}

function getOtpValue() { return [...document.querySelectorAll(".otp-box")].map(b => b.value).join(""); }

function showOtpError(msg) {
  document.getElementById("otpError").textContent = msg;
  document.querySelectorAll(".otp-box").forEach(b => b.classList.add("error"));
  setTimeout(() => document.querySelectorAll(".otp-box").forEach(b => b.classList.remove("error")), 600);
}

function setRegStep(n) {
  ["regStep1","regStep2","regStep3"].forEach((id,i) =>
    document.getElementById(id)?.classList.toggle("hidden", i+1 !== n));
  ["stepDot1","stepDot2","stepDot3"].forEach((id,i) => {
    const el = document.getElementById(id);
    el?.classList.toggle("active", i+1 === n);
    el?.classList.toggle("done",   i+1 < n);
  });
  document.querySelectorAll(".reg-step-line").forEach((l,i) => l.classList.toggle("done", i+1 < n));
}

/* ── Live email check → GET /api/users/check-email ── */
const checkEmailLive = debounce(async (email) => {
  const icon  = document.getElementById("emailStatusIcon");
  const errEl = document.getElementById("registerError");
  if (!icon) return;
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    icon.textContent = email ? "✗" : ""; icon.style.color = "#ff6b6b"; return;
  }
  try {
    const data = await apiFetch(`${R.auth}/check-email?email=${encodeURIComponent(email)}`);
    icon.textContent = data.exists ? "✗" : "✓";
    icon.style.color = data.exists ? "#ff6b6b" : "#22c55e";
    errEl.textContent = data.exists ? "Email already registered. Try signing in." : "";
  } catch { icon.textContent = ""; }
}, 500);

document.getElementById("regEmail").addEventListener("input", e => checkEmailLive(e.target.value.trim()));

/* ── SEND OTP ── */
document.getElementById("sendOtpBtn").onclick = async () => {
  const btn      = document.getElementById("sendOtpBtn");
  const username = document.getElementById("regUsername").value.trim();
  const email    = document.getElementById("regEmail").value.trim();
  const password = document.getElementById("regPassword").value;
  const errEl    = document.getElementById("registerError");
  errEl.textContent = "";

  if (!username || !email || !password) { errEl.textContent = "Please fill in all fields."; return; }
  if (username.length < 3) { errEl.textContent = "Username must be at least 3 characters."; return; }
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) { errEl.textContent = "Invalid email address."; return; }
  if (password.length < 6) { errEl.textContent = "Password must be at least 6 characters."; return; }

  setSubmitting(btn, true, "Send Verification Code");
  try {
    const code = generateOtp();
    await sendOtpEmail(email, username, code);
    otpState.code = code; otpState.email = email;
    document.getElementById("otpTargetEmail").textContent = email;
    setRegStep(2); resetOtpBoxes(); startOtpExpiry(); startResendCooldown(); wireOtpBoxes();
  } catch (err) {
    errEl.textContent = "Failed to send code: " + err.message;
  } finally { setSubmitting(btn, false, "Send Verification Code"); }
};

function wireOtpBoxes() {
  const boxes = [...document.querySelectorAll(".otp-box")];
  boxes.forEach((box, i) => {
    box.oninput = () => {
      box.value = box.value.replace(/\D/g,"").slice(0,1);
      box.classList.toggle("filled", !!box.value);
      document.getElementById("otpError").textContent = "";
      if (box.value && i < boxes.length - 1) boxes[i+1].focus();
      if (i === boxes.length - 1 && getOtpValue().length === 6)
        document.getElementById("verifyOtpBtn").click();
    };
    box.onkeydown = e => {
      if (e.key === "Backspace" && !box.value && i > 0) {
        boxes[i-1].focus(); boxes[i-1].value = ""; boxes[i-1].classList.remove("filled");
      }
    };
    box.onpaste = e => {
      e.preventDefault();
      const text = e.clipboardData.getData("text").replace(/\D/g,"").slice(0,6);
      boxes.forEach((b,j) => { b.value = text[j]||""; b.classList.toggle("filled",!!b.value); });
      if (text.length >= 6) document.getElementById("verifyOtpBtn").click();
      else boxes[Math.min(text.length,5)].focus();
    };
  });
}

/* ── VERIFY OTP → POST /api/users/register ── */
document.getElementById("verifyOtpBtn").onclick = async () => {
  const entered = getOtpValue();
  if (entered.length < 6) { showOtpError("Enter all 6 digits."); return; }
  if (!otpState.code || Date.now() > otpState.expiresAt) {
    otpState.code = null; showOtpError("Code expired. Go back and resend."); return;
  }
  if (entered !== otpState.code) { showOtpError("Incorrect code. Try again."); return; }

  const btn = document.getElementById("verifyOtpBtn");
  setSubmitting(btn, true, "Verify & Create Account");
  try {
    const data = await apiFetch(`${R.auth}/register`, {
      method: "POST",
      body: JSON.stringify({
        username: document.getElementById("regUsername").value.trim(),
        email:    otpState.email,
        password: document.getElementById("regPassword").value,
      }),
    });
    clearOtpTimers(); otpState.code = null;
    setAuth(data.token, data.user);
    setRegStep(3);
    setTimeout(() => { closeAuthModal(); renderAuthState(); }, 1800);
  } catch (err) {
    showOtpError(err.message);
    const regErr = document.getElementById("registerError");
    if (regErr) { regErr.textContent = err.message; setRegStep(1); }
  } finally { setSubmitting(btn, false, "Verify & Create Account"); }
};

document.getElementById("resendOtpBtn").onclick = async () => {
  const btn = document.getElementById("resendOtpBtn");
  btn.disabled = true; btn.textContent = "Sending…";
  try {
    const code = generateOtp();
    await sendOtpEmail(otpState.email, document.getElementById("regUsername").value.trim(), code);
    otpState.code = code; otpState.expiresAt = Date.now() + 10*60*1000;
    document.getElementById("otpTimerLabel")?.classList.remove("expired");
    document.getElementById("verifyOtpBtn").disabled = false;
    clearInterval(otpState.expiryTimer); startOtpExpiry(); startResendCooldown(); resetOtpBoxes();
  } catch {
    document.getElementById("otpError").textContent = "Failed to resend.";
    btn.disabled = false; btn.textContent = "Resend code";
  }
};

document.getElementById("backToStep1Btn").onclick = () => {
  clearOtpTimers(); otpState.code = null; setRegStep(1);
  document.getElementById("registerError").textContent = "";
};

/* ─────────────────────────────────────────
   WATCHLIST  →  /api/movies/watchlist
───────────────────────────────────────── */
function wlKey() { const u = getUser(); return u ? `cinex_wl_${u.id}` : "cinex_wl_guest"; }
function getWl() { try { return JSON.parse(localStorage.getItem(wlKey()) || "[]"); } catch { return []; } }
function setWl(list) { localStorage.setItem(wlKey(), JSON.stringify(list)); document.getElementById("watchlistCount").textContent = list.length; }

async function syncWatchlist() {
  if (!getToken()) { renderWatchlistPanel(); return; }
  try {
    const rows = await apiFetch(`${R.watchlist}/watchlist`);
    setWl(rows.map(r => ({ id: r.movie_id, title: r.title, poster_path: r.poster_path })));
  } catch {}
  renderWatchlistPanel();
}

async function toggleWatchlist(movie) {
  const list   = getWl();
  const exists = list.some(m => m.id === movie.id);
  if (getToken()) {
    try {
      if (exists) await apiFetch(`${R.watchlist}/watchlist/${movie.id}`, { method:"DELETE" });
      else await apiFetch(`${R.watchlist}/watchlist`, { method:"POST",
        body: JSON.stringify({ movie_id: movie.id, title: movie.title, poster_path: movie.poster_path }) });
      await syncWatchlist();
    } catch { setWl(exists ? list.filter(m => m.id !== movie.id) : [...list, { id:movie.id, title:movie.title, poster_path:movie.poster_path }]); }
  } else {
    setWl(exists ? list.filter(m => m.id !== movie.id) : [...list, { id:movie.id, title:movie.title, poster_path:movie.poster_path }]);
  }
  updateWatchlistBtn(movie); renderWatchlistPanel();
}

function updateWatchlistBtn(movie) {
  const btn    = document.getElementById("watchlistAdd");
  const inList = getWl().some(m => m.id === movie.id);
  btn.textContent = inList ? "✓ In Watchlist" : "🔖 Add to Watchlist";
  btn.classList.toggle("in-watchlist", inList);
}

function renderWatchlistPanel() {
  const list   = getWl();
  const el     = document.getElementById("watchlistItems");
  const isAuth = !!getUser();
  document.getElementById("watchlistCount").textContent = list.length;

  let html = "";
  if (!isAuth) html += `<div class="watchlist-login-prompt">Sign in to save your watchlist.<br><button onclick="openAuthModal('login')">Sign In / Register</button></div>`;

  if (!list.length) { html += `<p class="watchlist-empty">No movies saved yet.<br><br>Open any movie and tap "Add to Watchlist".</p>`; el.innerHTML = html; return; }

  html += list.map(m => `
    <div class="watchlist-item" data-id="${m.id}">
      <img src="${m.poster_path ? IMG_W + m.poster_path : ""}" alt="${escHtml(m.title)}" loading="lazy"/>
      <span class="watchlist-item-title">${escHtml(m.title)}</span>
      <button class="watchlist-item-remove" data-id="${m.id}">✕</button>
    </div>`).join("");
  el.innerHTML = html;

  el.querySelectorAll(".watchlist-item").forEach(item => {
    item.onclick = e => { if (!e.target.classList.contains("watchlist-item-remove")) showDetails(+item.dataset.id); };
  });
  el.querySelectorAll(".watchlist-item-remove").forEach(btn => {
    btn.onclick = async e => {
      e.stopPropagation(); const id = +btn.dataset.id;
      if (getToken()) { try { await apiFetch(`${R.watchlist}/watchlist/${id}`, { method:"DELETE" }); } catch {} }
      setWl(getWl().filter(m => m.id !== id)); renderWatchlistPanel();
    };
  });
}

document.getElementById("watchlistToggle").onclick = () => {
  document.getElementById("watchlistPanel").classList.toggle("hidden"); renderWatchlistPanel();
};
document.getElementById("closeWatchlist").onclick = () =>
  document.getElementById("watchlistPanel").classList.add("hidden");

/* ─────────────────────────────────────────
   AI AGENT  →  POST /api/agent/chat
───────────────────────────────────────── */
const agentPanel = document.getElementById("agentPanel");
const agentInput = document.getElementById("agentInput");
const agentSend  = document.getElementById("agentSend");
const agentCharCount = document.getElementById("agentCharCount");

document.getElementById("agentTrigger").onclick = () => {
  agentPanel.classList.toggle("hidden");
  if (!agentPanel.classList.contains("hidden")) agentInput.focus();
};
document.getElementById("closeAgent").onclick = () => agentPanel.classList.add("hidden");

document.getElementById("clearAgentBtn").onclick = async () => {
  try { if (getToken()) await apiFetch(`${R.agent}/memory`, { method:"DELETE" }); } catch {}
  document.getElementById("agentMessages").innerHTML = `
    <div class="agent-msg bot">
      <div class="agent-avatar-mini">
        <svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" stroke="url(#miniC)" stroke-width="1.5"/><circle cx="7.5" cy="9" r="1.5" fill="#F5C518"/><circle cx="12.5" cy="9" r="1.5" fill="#F5C518"/><path d="M7 13c.8.8 2 1.2 3 1.2s2.2-.4 3-1.2" stroke="#F5C518" stroke-width="1.2" stroke-linecap="round"/><defs><linearGradient id="miniC" x1="0" y1="0" x2="20" y2="20"><stop stop-color="#F5C518"/><stop offset="1" stop-color="#e87c2a"/></linearGradient></defs></svg>
      </div>
      <div class="agent-bubble">
        <p>New conversation started. What would you like to discover? 🎬</p>
        <div class="agent-chips">
          <button class="chip" onclick="sendAgentMessage('Recommend me something great to watch')">🎬 Recommend</button>
          <button class="chip" onclick="sendAgentMessage('Show my ratings')">⭐ My ratings</button>
        </div>
      </div>
    </div>`;
};

agentInput.addEventListener("input", () => {
  if (agentCharCount) agentCharCount.textContent = agentInput.value.length;
});
agentInput.addEventListener("keydown", e => {
  if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); agentSend.click(); }
});
agentSend.onclick = () => sendAgentMessage();

async function sendAgentMessage(prefill) {
  const msg = (prefill ?? agentInput.value).trim();
  if (!msg) return;

  agentInput.value = "";
  if (agentCharCount) agentCharCount.textContent = "0";
  agentPanel.classList.remove("hidden");
  agentSend.disabled = true;

  appendAgentMsg("user", msg);

  if (!getToken()) {
    appendAgentMsg("bot", `Please <a href="#" onclick="openAuthModal('login');return false;" style="color:#F5C518;text-decoration:underline">sign in</a> to use CINEX AI.`, false);
    agentSend.disabled = false;
    return;
  }

  const typing = appendTyping();
  try {
    const data = await apiFetch(`${R.agent}/chat`, {
      method: "POST",
      body: JSON.stringify({ message: msg }),
    });
    typing.remove();
    appendAgentMsg("bot", data.reply);
  } catch (err) {
    typing.remove();
    const isAuth = err.message?.includes("Unauthorized") || err.message?.includes("401");
    appendAgentMsg("bot",
      isAuth
        ? `Please <a href="#" onclick="openAuthModal('login');return false;" style="color:#F5C518">sign in</a> to continue.`
        : "Something went wrong — please try again in a moment.",
      !isAuth
    );
  } finally {
    agentSend.disabled = false;
    agentInput.focus();
  }
}

function _botAvatarSvg(gradId) {
  return `<div class="agent-avatar-mini"><svg viewBox="0 0 20 20" fill="none"><circle cx="10" cy="10" r="9" stroke="url(#${gradId})" stroke-width="1.5"/><circle cx="7.5" cy="9" r="1.5" fill="#F5C518"/><circle cx="12.5" cy="9" r="1.5" fill="#F5C518"/><path d="M7 13c.8.8 2 1.2 3 1.2s2.2-.4 3-1.2" stroke="#F5C518" stroke-width="1.2" stroke-linecap="round"/><defs><linearGradient id="${gradId}" x1="0" y1="0" x2="20" y2="20"><stop stop-color="#F5C518"/><stop offset="1" stop-color="#e87c2a"/></linearGradient></defs></svg></div>`;
}

let _msgIdx = 0;
function appendAgentMsg(role, text, isError = false) {
  const msgs = document.getElementById("agentMessages");
  const wrap = document.createElement("div");
  wrap.className = `agent-msg ${role}`;

  const avatarHtml = role === "bot" ? _botAvatarSvg(`miniM${_msgIdx++}`) : "";
  const formatted  = _formatBotText(text);

  wrap.innerHTML = `${avatarHtml}<div class="agent-bubble${isError ? " error" : ""}">${formatted}</div>`;
  msgs.appendChild(wrap);
  msgs.scrollTop = msgs.scrollHeight;
  return wrap;
}

function _formatBotText(text) {
  return text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>")
    .replace(/^/, "<p>").replace(/$/, "</p>")
    .replace(/<p><\/p>/g, "");
}

function appendTyping() {
  const msgs = document.getElementById("agentMessages");
  const div  = document.createElement("div");
  div.className = "agent-msg bot";
  div.innerHTML  = `${_botAvatarSvg(`miniT${_msgIdx++}`)}<div class="agent-bubble"><div class="agent-typing"><span></span><span></span><span></span></div></div>`;
  msgs.appendChild(div);
  msgs.scrollTop = msgs.scrollHeight;
  return div;
}

/* ─────────────────────────────────────────
   ML TRAINING BANNER  →  /api/ml/training-status
───────────────────────────────────────── */
let _mlWasTraining = false, _mlPollTimer = null;

async function pollMlStatus() {
  try {
    const d       = await apiFetch(`${R.ml}/training-status`);
    const banner  = document.getElementById("mlTrainingBanner");
    const txt     = document.getElementById("mlBannerText");

    if (d.training) {
      _mlWasTraining = true;
      banner.classList.remove("hidden");
      txt.innerHTML = `<b>Training recommendation engine</b> &nbsp;— this takes ~2 min on first run`;
    } else if (_mlWasTraining && d.models_ready) {
      _mlWasTraining = false;
      banner.classList.remove("hidden");
      txt.innerHTML = `✓ &nbsp;<b>Recommendations ready!</b> &nbsp;Refresh a movie to see AI picks.`;
      setTimeout(() => banner.classList.add("hidden"), 5000);
      if (currentMovieId) loadRecommendations(currentMovieId);
    } else if (!d.models_ready && !d.training) {
      banner.classList.remove("hidden");
      txt.innerHTML = `⏳ &nbsp;Warming up recommendation engine…`;
    } else {
      banner.classList.add("hidden");
    }
  } catch {}
}

function startMlPolling() {
  pollMlStatus();
  _mlPollTimer = setInterval(async () => {
    await pollMlStatus();
    clearInterval(_mlPollTimer);
    _mlPollTimer = setInterval(pollMlStatus, _mlWasTraining ? 8000 : 60000);
  }, 8000);
}

/* ─────────────────────────────────────────
   AUTOCOMPLETE
───────────────────────────────────────── */
let acFocusIndex = -1;

const fetchSuggestions = debounce(async (q) => {
  if (!q || q.length < 2) { closeDropdown(); return; }
  dropdown.classList.remove("hidden");
  dropdown.innerHTML = `<div class="ac-loading">Searching…</div>`;
  acFocusIndex = -1;

  try {
    const data = await tmdbFetch(`/search/movie?api_key=${TMDB_KEY}&query=${encodeURIComponent(q)}&page=1`);
    const hits  = (data.results ?? []).filter(m => m.title).slice(0, 6);
    if (!hits.length) { dropdown.innerHTML = `<div class="ac-empty">No results for "${escHtml(q)}"</div>`; return; }

    dropdown.innerHTML = hits.map((m,i) => `
      <div class="ac-item" data-id="${m.id}" data-index="${i}">
        <img class="ac-poster" src="${m.poster_path ? IMG_W+m.poster_path : ""}" alt="${escHtml(m.title)}" loading="lazy" onerror="this.style.visibility='hidden'"/>
        <div class="ac-info">
          <div class="ac-title">${escHtml(m.title)}</div>
          <div class="ac-meta">
            <span>${m.release_date?.slice(0,4) ?? "—"}</span>
            ${m.vote_average ? `<span class="ac-rating">⭐ ${m.vote_average.toFixed(1)}</span>` : ""}
          </div>
        </div>
      </div>`).join("") +
      `<div class="ac-footer" id="acSeeAll">See all results for "${escHtml(q)}" →</div>`;

    dropdown.querySelectorAll(".ac-item").forEach(item => {
      item.onclick = () => { searchInput.value = item.querySelector(".ac-title").textContent; closeDropdown(); showDetails(+item.dataset.id); };
    });
    document.getElementById("acSeeAll").onclick = () => { closeDropdown(); doSearch(); };
  } catch { dropdown.innerHTML = `<div class="ac-empty">Search unavailable</div>`; }
}, 300);

function closeDropdown() { dropdown.classList.add("hidden"); dropdown.innerHTML = ""; acFocusIndex = -1; }

searchInput.addEventListener("input",  e => fetchSuggestions(e.target.value.trim()));
searchInput.addEventListener("focus",  e => { if (e.target.value.trim().length >= 2) fetchSuggestions(e.target.value.trim()); });
searchInput.addEventListener("keydown", e => {
  const items = [...dropdown.querySelectorAll(".ac-item")];
  if (e.key === "ArrowDown")  { e.preventDefault(); acFocusIndex = Math.min(acFocusIndex+1, items.length-1); }
  else if (e.key === "ArrowUp")  { e.preventDefault(); acFocusIndex = Math.max(acFocusIndex-1, 0); }
  else if (e.key === "Enter") { if (acFocusIndex >= 0 && items[acFocusIndex]) { items[acFocusIndex].click(); return; } closeDropdown(); doSearch(); return; }
  else if (e.key === "Escape") { closeDropdown(); return; }
  items.forEach((el,i) => el.classList.toggle("focused", i === acFocusIndex));
  if (items[acFocusIndex]) items[acFocusIndex].scrollIntoView({ block:"nearest" });
});
document.addEventListener("click", e => { if (!e.target.closest(".search-wrapper")) closeDropdown(); });

/* ─────────────────────────────────────────
   SEARCH
───────────────────────────────────────── */
function doSearch() {
  const q = searchInput.value.trim(); if (!q) return;
  state.searchQuery = q; state.mode = "search"; state.page = 1;
  closeDropdown(); fetchAndDisplay();
}
document.getElementById("searchBtn").onclick = doSearch;

/* ─────────────────────────────────────────
   GENRES
───────────────────────────────────────── */
async function loadGenres() {
  try {
    const data = await tmdbFetch(`/genre/movie/list?api_key=${TMDB_KEY}`);
    const div  = document.getElementById("genreButtons");
    const allBtn = mkBtn("All", true, () => { state.genre=""; state.page=1; state.mode=state.lang?"discover":"popular"; setActive(div,allBtn); fetchAndDisplay(); });
    div.appendChild(allBtn);
    data.genres.forEach(g => {
      genreMap[g.id] = g.name;
      const btn = mkBtn(g.name, false, () => { state.genre=g.id; state.page=1; state.mode="discover"; setActive(div,btn); fetchAndDisplay(); });
      div.appendChild(btn);
    });
  } catch (err) { console.error("Genres:", err); }
}

function mkBtn(label, active, onClick) {
  const btn = document.createElement("button");
  btn.textContent = label; if (active) btn.classList.add("active"); btn.onclick = onClick; return btn;
}
function setActive(parent, activeBtn) {
  parent.querySelectorAll("button").forEach(b => b.classList.remove("active")); activeBtn.classList.add("active");
}

document.querySelectorAll("#industryButtons button").forEach(btn => {
  btn.onclick = () => {
    state.lang = btn.getAttribute("data-lang"); state.page = 1;
    if (state.mode === "search") { state.mode = state.lang?"discover":"popular"; state.searchQuery=""; }
    else if (!state.genre) { state.mode = state.lang?"discover":"popular"; }
    setActive(document.getElementById("industryButtons"), btn); fetchAndDisplay();
  };
});

/* ─────────────────────────────────────────
   HERO SLIDER
───────────────────────────────────────── */
async function loadHero() {
  try {
    const data = await tmdbFetch(`/trending/movie/week?api_key=${TMDB_KEY}`);
    heroMovies = data.results.filter(m => m.backdrop_path).slice(0,5);
    heroIndex  = 0; renderHero();
    if (heroTimer) clearInterval(heroTimer);
    heroTimer = setInterval(() => { heroIndex = (heroIndex+1) % heroMovies.length; renderHero(); }, 5000);
  } catch (err) { console.error("Hero:", err); }
}

function renderHero() {
  const hero = document.getElementById("hero"), movie = heroMovies[heroIndex];
  hero.innerHTML = `
    <div class="hero-slide">
      <img src="${IMG_OG+movie.backdrop_path}" alt="${escHtml(movie.title)}" loading="lazy"/>
      <div class="hero-overlay">
        <h2>${escHtml(movie.title)}</h2>
        <div class="hero-meta">
          <span class="rating">⭐ ${movie.vote_average?.toFixed(1)??"N/A"}</span>
          &nbsp;•&nbsp; 📅 ${movie.release_date?.slice(0,4)??"N/A"}
        </div>
        <p>${escHtml((movie.overview?.slice(0,160)??"No description")+"…")}</p>
        <button class="hero-btn" id="heroBtn">View Details</button>
      </div>
    </div>
    <div class="hero-dots" id="heroDots"></div>`;
  document.getElementById("heroBtn").onclick = () => showDetails(movie.id);
  const dotsEl = document.getElementById("heroDots");
  heroMovies.forEach((_,i) => {
    const dot = document.createElement("div");
    dot.className = `hero-dot${i===heroIndex?" active":""}`;
    dot.onclick   = () => { heroIndex=i; renderHero(); };
    dotsEl.appendChild(dot);
  });
}

/* ─────────────────────────────────────────
   FETCH & DISPLAY
───────────────────────────────────────── */
async function fetchAndDisplay() {
  setLoading(true); showSkeletons();
  try {
    let path, title;
    if (state.mode === "search" && state.searchQuery) {
      path  = `/search/movie?api_key=${TMDB_KEY}&query=${encodeURIComponent(state.searchQuery)}&page=${state.page}`;
      title = `Results for "${state.searchQuery}"`;
    } else if (state.genre || state.lang) {
      path  = `/discover/movie?api_key=${TMDB_KEY}&page=${state.page}&sort_by=popularity.desc`;
      if (state.genre) path += `&with_genres=${state.genre}`;
      if (state.lang)  path += `&with_original_language=${state.lang}`;
      title = "Filtered Movies";
    } else {
      path  = `/movie/popular?api_key=${TMDB_KEY}&page=${state.page}`;
      title = "Popular Movies";
    }
    const data = await tmdbFetch(path);
    state.totalPages        = Math.min(data.total_pages??1, 500);
    sectionTitle.textContent = title;
    displayMovies(data.results??[]);
    updatePagination();
  } catch (err) {
    container.innerHTML = `<p class="error-msg">⚠ Failed to load movies. Check your connection.</p>`;
    console.error(err);
  } finally { setLoading(false); }
}

function displayMovies(movies) {
  const valid = movies.filter(m => m.poster_path);
  if (!valid.length) { container.innerHTML = `<p class="error-msg">No movies found.</p>`; return; }
  container.innerHTML = "";
  valid.forEach((m,i) => {
    const card = document.createElement("div");
    card.className = "movie-card"; card.style.animationDelay = `${i*0.04}s`;
    card.innerHTML = `
      <img src="${IMG_W+m.poster_path}" alt="${escHtml(m.title)}" loading="lazy"/>
      <div class="movie-card-overlay"><span class="movie-card-overlay-text">View Details</span></div>
      <div class="movie-card-info">
        <div class="movie-card-title">${escHtml(m.title)}</div>
        <div class="movie-card-rating">⭐ ${m.vote_average?.toFixed(1)??"N/A"}</div>
      </div>`;
    card.onclick = () => showDetails(m.id);
    container.appendChild(card);
  });
}

/* ─────────────────────────────────────────
   PAGINATION
───────────────────────────────────────── */
function updatePagination() {
  pageInfo.textContent = `Page ${state.page} of ${state.totalPages}`;
  prevBtn.disabled = state.page <= 1; nextBtn.disabled = state.page >= state.totalPages;
}
prevBtn.onclick = () => { if (state.page > 1)                { state.page--; window.scrollTo(0,0); fetchAndDisplay(); } };
nextBtn.onclick = () => { if (state.page < state.totalPages) { state.page++; window.scrollTo(0,0); fetchAndDisplay(); } };

/* ─────────────────────────────────────────
   DETAIL MODAL
───────────────────────────────────────── */
async function showDetails(id) {
  currentMovieId = id;
  modal.style.display = "block";

  document.getElementById("modal-title").textContent     = "Loading…";
  document.getElementById("modal-img").src               = "";
  ["modal-date","modal-rating","modal-lang","modal-genres","modal-desc","modal-ott"]
    .forEach(el => { document.getElementById(el).textContent = ""; });
  document.getElementById("castGrid").innerHTML           = "";
  document.getElementById("commentList").innerHTML        = "";
  document.getElementById("ratingSummary").textContent    = "";
  document.getElementById("recGrid").innerHTML            = `<div class="rec-loading">Finding recommendations…</div>`;
  document.getElementById("recBadge").className           = "rec-badge hidden";
  document.getElementById("recTitle").textContent         = "Recommended For You";
  resetStars();
  const tBtn = document.getElementById("trailerBtn");
  tBtn.disabled = true; tBtn.textContent = "▶ Watch Trailer";

  try {
    const [movie, credits, watchProviders, videos, ratingData, commentsData] = await Promise.all([
      tmdbFetch(`/movie/${id}?api_key=${TMDB_KEY}`),
      tmdbFetch(`/movie/${id}/credits?api_key=${TMDB_KEY}`),
      tmdbFetch(`/movie/${id}/watch/providers?api_key=${TMDB_KEY}`),
      tmdbFetch(`/movie/${id}/videos?api_key=${TMDB_KEY}`),
      apiFetch(`${R.ratings}/${id}`).catch(() => ({ avg:0, total:0, my_rating:null })),
      apiFetch(`${R.ratings}/comments/${id}`).catch(() => []),
    ]);

    currentMovieTitle = movie.title;

    if (movie.poster_path) document.getElementById("modal-img").src = IMG_W + movie.poster_path;
    document.getElementById("modal-title").textContent   = movie.title ?? "N/A";
    document.getElementById("modal-date").textContent    = "📅 " + (movie.release_date ?? "N/A");
    document.getElementById("modal-rating").textContent  = "⭐ " + (movie.vote_average?.toFixed(1) ?? "N/A");
    document.getElementById("modal-lang").textContent    = "🌐 " + (movie.spoken_languages?.map(l => l.english_name).join(", ") || "N/A");
    document.getElementById("modal-genres").textContent  = movie.genres?.map(g => g.name).join(" · ") ?? "";
    document.getElementById("modal-desc").textContent    = movie.overview ?? "No description available.";

    const flatrate = watchProviders.results?.IN?.flatrate ?? watchProviders.results?.US?.flatrate;
    document.getElementById("modal-ott").textContent = flatrate?.length
      ? "📺 " + flatrate.map(p => p.provider_name).join(", ")
      : "📺 Not currently streaming";

    const trailer = videos.results?.find(v => v.type==="Trailer" && v.site==="YouTube");
    tBtn.disabled    = !trailer;
    tBtn.textContent = trailer ? "▶ Watch Trailer" : "▶ No Trailer";
    tBtn.onclick     = trailer ? () => openTrailer(trailer.key) : null;

    updateWatchlistBtn(movie);
    document.getElementById("watchlistAdd").onclick = () => toggleWatchlist(movie);

    /* Ask AI button — pre-fills agent input */
    document.getElementById("askAgentBtn").onclick = () => {
      sendAgentMessage(`Tell me about "${movie.title}" (movie #${id})`);
    };

    renderCastGrid(credits.cast?.slice(0,12) ?? []);
    renderRating(id, ratingData);
    renderComments(id, commentsData);
    loadRecommendations(id);

  } catch (err) {
    document.getElementById("modal-title").textContent = "Failed to load details.";
    console.error(err);
  }
}

/* ── Cast Grid ── */
const PLACEHOLDER = `data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 72 72'%3E%3Crect width='72' height='72' fill='%2318181f'/%3E%3Ctext x='36' y='44' text-anchor='middle' font-size='28' fill='%237a7a8a'%3E👤%3C/text%3E%3C/svg%3E`;

function renderCastGrid(cast) {
  const grid = document.getElementById("castGrid");
  if (!cast.length) { grid.innerHTML = `<p style="color:var(--muted);font-size:.82rem">No cast data.</p>`; return; }
  grid.innerHTML = cast.map(c => `
    <div class="cast-card">
      <img class="cast-photo" src="${c.profile_path ? IMG_FACE+c.profile_path : PLACEHOLDER}"
           alt="${escHtml(c.name)}" loading="lazy" onerror="this.src='${PLACEHOLDER}'"/>
      <div class="cast-name">${escHtml(c.name)}</div>
      <div class="cast-character">${escHtml(c.character||"")}</div>
    </div>`).join("");
}

/* ── ML Recommendations → /api/recommend/{id} ── */
async function loadRecommendations(movieId) {
  const grid  = document.getElementById("recGrid");
  const title = document.getElementById("recTitle");
  const badge = document.getElementById("recBadge");

  try {
    const data = await apiFetch(`${R.recommend}/${movieId}?n=12`);

    if (data.model === "not_trained") {
      grid.innerHTML = `<div class="rec-train-prompt">
        ML model training on startup — recommendations will appear once ready.
        The gold banner at the top shows progress.
      </div>`; return;
    }

    const recs = data.recommendations ?? [];
    if (!recs.length) { await fallbackTmdbSimilar(movieId, grid, title); return; }

    const source   = recs[0]?.source ?? data.model;
    const badgeMap = {
      hybrid:         { cls:"badge-hybrid",        label:"AI Hybrid" },
      content:        { cls:"badge-content",        label:"Content AI" },
      collaborative:  { cls:"badge-collaborative",  label:"Personalised" },
      popular:        { cls:"badge-popular",         label:"Popular" },
    };
    const b = badgeMap[source] ?? badgeMap.content;
    badge.textContent = b.label; badge.className = `rec-badge ${b.cls}`;
    title.textContent = getUser() ? "Recommended For You" : "You Might Also Like";
    grid.innerHTML    = recs.filter(m => m.id).map(m => buildRecCard(m)).join("");
    wireRecCards(grid);
  } catch { await fallbackTmdbSimilar(movieId, grid, title); }
}

async function fallbackTmdbSimilar(movieId, grid, title) {
  try {
    const fallback = await tmdbFetch(`/movie/${movieId}/similar?api_key=${TMDB_KEY}`);
    const movies   = (fallback.results??[]).filter(m => m.poster_path).slice(0,12);
    title.textContent = "Similar Movies";
    grid.innerHTML    = movies.length ? movies.map(m => buildRecCard(m)).join("") : `<div class="rec-empty">No recommendations found.</div>`;
    wireRecCards(grid);
  } catch { grid.innerHTML = `<div class="rec-empty">Could not load recommendations.</div>`; }
}

function buildRecCard(m) {
  const img   = m.poster_path ? IMG_W+m.poster_path : "";
  const score = m.hybrid_score
    ? `<div class="rec-card-score">Match ${(m.hybrid_score*100).toFixed(0)}%</div>`
    : m.predicted_rating ? `<div class="rec-card-score">⭐ ${m.predicted_rating}</div>` : "";
  return `<div class="rec-card" data-id="${m.id}" title="${escHtml(m.title??"")}">
    <img src="${img}" alt="${escHtml(m.title??"")}" loading="lazy" onerror="this.style.opacity='0.3'"/>
    <div class="rec-card-title">${escHtml(m.title??"")}</div>${score}
  </div>`;
}

function wireRecCards(scope) { scope.querySelectorAll(".rec-card").forEach(c => { c.onclick = () => showDetails(+c.dataset.id); }); }

/* ── Star Rating → /api/ratings ── */
function resetStars() {
  document.querySelectorAll(".star").forEach(s => s.classList.remove("selected","hovered"));
  document.getElementById("starRow").classList.remove("readonly");
}

function renderRating(movieId, data) {
  const { avg, total, my_rating } = data;
  const user    = getUser();
  const summary = document.getElementById("ratingSummary");
  const starRow = document.getElementById("starRow");
  const loginP  = document.getElementById("ratingLoginPrompt");

  summary.innerHTML = avg > 0
    ? `Community: <b>${avg} ★</b> &nbsp;(${total} vote${total!==1?"s":""})`
    : `Be the first to rate this movie`;

  if (user) {
    loginP.classList.add("hidden"); starRow.classList.remove("readonly");
    if (my_rating) paintStars(my_rating, "selected");

    document.querySelectorAll(".star").forEach(star => {
      star.onmouseenter = () => paintStars(+star.dataset.value, "hovered");
      star.onmouseleave = () => { document.querySelectorAll(".star").forEach(s => s.classList.remove("hovered")); if (data.my_rating) paintStars(data.my_rating, "selected"); };
      star.onclick = async () => {
        const val = +star.dataset.value; paintStars(val, "selected");
        try {
          const res = await apiFetch(`${R.ratings}`, { method:"POST", body:JSON.stringify({ movie_id:movieId, rating:val }) });
          summary.innerHTML = `Community: <b>${res.avg} ★</b> &nbsp;(${res.total} vote${res.total!==1?"s":""})`;
          data.my_rating = val;
        } catch (err) { console.error("Rate:", err); }
      };
    });
  } else {
    loginP.classList.remove("hidden"); starRow.classList.add("readonly");
    document.getElementById("ratingLoginLink").onclick = e => { e.preventDefault(); openAuthModal("login"); };
  }
}

function paintStars(value, cls) {
  document.querySelectorAll(".star").forEach(s => {
    s.classList.remove("selected","hovered");
    if (+s.dataset.value <= value) s.classList.add(cls);
  });
}

/* ── Comments → /api/ratings/comments ── */
function renderComments(movieId, comments) {
  const user        = getUser();
  const commentForm = document.getElementById("commentForm");
  const commentP    = document.getElementById("commentLoginPrompt");
  const input       = document.getElementById("commentInput");
  const charCount   = document.getElementById("commentCharCount");
  const submitBtn   = document.getElementById("submitComment");
  const list        = document.getElementById("commentList");

  if (user) {
    commentForm.classList.remove("hidden"); commentP.classList.add("hidden");
    input.oninput = () => {
      const len = input.value.length;
      charCount.textContent = `${len} / 500`;
      charCount.className   = `char-count${len>450?(len>=500?" at-limit":" near-limit"):""}`;
    };
    submitBtn.onclick = async () => {
      const text = input.value.trim(); if (!text) return;
      submitBtn.disabled = true;
      try {
        const c = await apiFetch(`${R.ratings}/comments`, { method:"POST", body:JSON.stringify({ movie_id:movieId, text }) });
        input.value = ""; charCount.textContent = "0 / 500"; charCount.className = "char-count";
        prependComment(c, list, user.id); list.querySelector(".comment-empty")?.remove();
      } catch (err) { console.error("Comment:", err); }
      finally { submitBtn.disabled = false; }
    };
  } else {
    commentForm.classList.add("hidden"); commentP.classList.remove("hidden");
    document.getElementById("commentLoginLink").onclick = e => { e.preventDefault(); openAuthModal("login"); };
  }

  if (!comments.length) { list.innerHTML = `<p class="comment-empty">No comments yet. Be the first!</p>`; return; }
  list.innerHTML = comments.map(c => buildCommentHTML(c, user?.id)).join("");
  wireDeleteButtons(list, movieId);
}

async function refreshRatingAndComments(movieId) {
  try {
    const [ratingData, commentsData] = await Promise.all([
      apiFetch(`${R.ratings}/${movieId}`).catch(() => ({ avg:0, total:0, my_rating:null })),
      apiFetch(`${R.ratings}/comments/${movieId}`).catch(() => []),
    ]);
    renderRating(movieId, ratingData);
    renderComments(movieId, commentsData);
  } catch {}
}

function buildCommentHTML(c, myUserId) {
  const canDelete = myUserId !== null && c.user_id === myUserId;
  return `<div class="comment-item" data-id="${c.id}">
    <div class="comment-header">
      <span class="comment-author">@${escHtml(c.username)}</span>
      <span style="display:flex;align-items:center;gap:4px">
        <span class="comment-date">${timeAgo(c.created_at)}</span>
        ${canDelete ? `<button class="comment-delete" data-id="${c.id}">✕</button>` : ""}
      </span>
    </div>
    <p class="comment-text">${escHtml(c.text)}</p>
  </div>`;
}

function prependComment(c, list, myUserId) {
  const div = document.createElement("div");
  div.innerHTML = buildCommentHTML(c, myUserId);
  list.prepend(div.firstElementChild);
  wireDeleteButtons(list.firstElementChild, currentMovieId);
}

function wireDeleteButtons(scope, movieId) {
  scope.querySelectorAll(".comment-delete").forEach(btn => {
    btn.onclick = async () => {
      const id = +btn.dataset.id;
      try {
        await apiFetch(`${R.ratings}/comments/${id}`, { method:"DELETE" });
        btn.closest(".comment-item").remove();
        if (!document.querySelector(".comment-item"))
          document.getElementById("commentList").innerHTML = `<p class="comment-empty">No comments yet. Be the first!</p>`;
      } catch {}
    };
  });
}

document.getElementById("close").onclick = () => { modal.style.display = "none"; currentMovieId = null; };
modal.onclick = e => { if (e.target === modal) { modal.style.display = "none"; currentMovieId = null; } };

/* ─────────────────────────────────────────
   TRAILER
───────────────────────────────────────── */
function openTrailer(key) {
  document.getElementById("trailerFrame").innerHTML =
    `<iframe src="https://www.youtube.com/embed/${key}?autoplay=1" allow="autoplay; fullscreen" allowfullscreen></iframe>`;
  trailerModal.classList.add("show");
}
function closeTrailer() { trailerModal.classList.remove("show"); document.getElementById("trailerFrame").innerHTML = ""; }
document.getElementById("closeTrailer").onclick = closeTrailer;
trailerModal.onclick = e => { if (e.target === trailerModal) closeTrailer(); };

/* ─────────────────────────────────────────
   INIT
───────────────────────────────────────── */
async function init() {
  setRegStep(1);

  /* Restore session */
  if (getToken()) {
    try { await apiFetch(`${R.auth}/me`); }
    catch { clearAuth(); }
  }

  renderAuthState();
  startMlPolling();
  await syncWatchlist();
  await Promise.all([loadGenres(), loadHero()]);
  await fetchAndDisplay();
}

init();