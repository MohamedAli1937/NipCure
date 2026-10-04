const API_URL =
  window.nipcure_API ||
  localStorage.getItem("nipcure_API") ||
  (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1"
    ? "http://127.0.0.1:8000"
    : window.location.origin);

const ICONS = {
  user: '<circle cx="12" cy="8" r="4"/><path d="M4 21c0-4 4-6 8-6s8 2 8 6"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/>',
  upload:
    '<path d="M12 16V4m0 0L7 9m5-5 5 5"/><path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3"/>',
  file: '<path d="M7 3h7l5 5v12a1 1 0 0 1-1 1H7a1 1 0 0 1-1-1V4a1 1 0 0 1 1-1z"/><path d="M14 3v5h5M9 13h6M9 17h6"/>',
  pill: '<rect x="2.5" y="8.5" width="19" height="7" rx="3.5" transform="rotate(-45 12 12)"/><path d="m8.5 8.5 7 7"/>',
  check: '<circle cx="12" cy="12" r="9"/><path d="m8 12 3 3 5-6"/>',
  ban: '<circle cx="12" cy="12" r="9"/><path d="m5.6 5.6 12.8 12.8"/>',
  food: '<path d="M12 7c-3-2-8-1-8 5 0 5 3 9 5 9 1.500 0 2-.7 3-.7s1.500.7 3 .7c2 0 5-4 5-9 0-6-5-7-8-5z"/><path d="M12 7c0-2 1-4 3-4"/>',
  alert: '<path d="M12 3 2 20h20L12 3z"/><path d="M12 10v5M12 18v.5"/>',
  calendar:
    '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 10h18M8 3v4M16 3v4"/>',
  help: '<circle cx="12" cy="12" r="9"/><path d="M9.500 9.500a2.500 2.500 0 1 1 3.500 2.300c-.7.400-1 1-1 1.700M12 17v.5"/>',
  speaker:
    '<path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16 9a4 4 0 0 1 0 6M18.500 6.500a8 8 0 0 1 0 11"/>',
  globe:
    '<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c3 3 3 15 0 18M12 3c-3 3-3 15 0 18"/>',
  search:
    '<circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>',
  out: '<path d="M9 4H5a1 1 0 0 0-1 1v14a1 1 0 0 0 1 1h4M16 8l4 4-4 4M20 12H9"/>',
  back: '<path d="M15 5 8 12l7 7"/>',
  arrow: '<path d="M5 12h14m-6-6 6 6-6 6"/>',
  chev: '<path d="m6 9 6 6 6-6"/>',
  save: '<path d="M5 4h11l3 3v13H5z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
  trash: '<path d="M3 6h18M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/><line x1="10" y1="11" x2="10" y2="17"/><line x1="14" y1="11" x2="14" y2="17"/>',
  refresh: '<path d="M21.5 2v6h-6M2.5 22v-6h6M2 11.5a10 10 0 0 1 18.8-4.3M22 12.5a10 10 0 0 1-18.8 4.2"/>',
  sparkle:
    '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.500 2.500M15.500 15.500 18 18M18 6l-2.500 2.500M8.500 15.500 6 18"/>',
};
const icon = (n, cls = "") =>
  `<svg class="ico ${cls}" viewBox="0 0 24 24" aria-hidden="true">${ICONS[n] || ""}</svg>`;

function hydrate() {
  document
    .querySelectorAll("[data-i]")
    .forEach((el) =>
      el.insertAdjacentHTML(
        el.dataset.pos === "end" ? "beforeend" : "afterbegin",
        icon(el.dataset.i),
      ),
    );
  document.querySelectorAll("[data-logo]").forEach((el) => {
    el.innerHTML = '<img src="assets/logo.svg" alt="" /><span>nipcure</span>';
    el.setAttribute("aria-label", "nipcure");
  });
}

const api = {
  token: () => localStorage.getItem("nipcure_token"),
  logout() {
    localStorage.removeItem("nipcure_token");
    location.href = "register.html";
  },
  requireAuth() {
    if (!api.token()) location.href = "login.html";
  },
  async request(path, opts = {}) {
    const headers = opts.headers || {};
    if (api.token()) headers.Authorization = "Bearer " + api.token();
    if (opts.json) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(opts.json);
    }
    let res;
    try {
      res = await fetch(API_URL + path, { ...opts, headers });
    } catch {
      throw new Error(
        "Can't reach the server. Check your internet and try again.",
      );
    }
    if (res.status === 401 && api.token()) api.logout();
    const data = await res.json().catch(() => ({}));
    if (!res.ok)
      throw new Error(data.detail || "Something went wrong. Please try again.");
    return data;
  },
  register: (name, password) =>
    api.request("/api/auth/register", {
      method: "POST",
      json: { name, password },
    }),

  login: (name, password) =>
    api.request("/api/auth/login", {
      method: "POST",
      json: { name, password },
    }),
  getProfile: () => api.request("/profile"),
  saveProfile: (p) => api.request("/profile", { method: "PUT", json: p }),
  reports: () => api.request("/reports"),
  report: (id) => api.request("/reports/" + id),
  deleteReport: (id) => api.request("/reports/" + id, { method: "DELETE" }),
  reexamineReport: (id) =>
    api.request("/reports/" + id + "/reexamine", { method: "POST" }),
  async voiceReport(id, text = null, section = null) {
    const headers = {};
    if (api.token()) headers.Authorization = "Bearer " + api.token();
    const opts = {
      method: "POST",
      headers,
    };
    if (text || section) {
      headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify({ text, section });
    }
    let res;
    try {
      res = await fetch(API_URL + "/reports/" + id + "/voice", opts);
    } catch {
      throw new Error("Can't reach the server. Check your connection.");
    }
    if (res.status === 401 && api.token()) api.logout();
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || "Voice generation failed.");
    }
    return res.blob();
  },
  researchReport: (id) => api.request("/reports/" + id + "/research"),
  upload(file) {
    const f = new FormData();
    f.append("file", file);
    return api.request("/reports", { method: "POST", body: f });
  },
};

function showMsg(type, text) {
  const el = document.getElementById("msg");
  el.className = "msg show " + type;
  el.innerHTML = icon(type === "error" ? "alert" : "check");
  const s = document.createElement("span");
  s.textContent = text;
  el.append(s);
  el.setAttribute("role", type === "error" ? "alert" : "status");
  el.scrollIntoView({ block: "nearest" });
}
const showBox = document.getElementById("show");
if (showBox)
  showBox.onchange = () =>
    document
      .querySelectorAll("input[type=password],input[data-pw]")
      .forEach((i) => {
        i.type = showBox.checked ? "text" : "password";
        i.dataset.pw = 1;
      });
hydrate();
