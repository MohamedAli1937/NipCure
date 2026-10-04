const name = document.getElementById("name");
const password = document.getElementById("password");

document.getElementById("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const btn = document.getElementById("go");
  btn.disabled = true;
  try {
    const r = await api.login(name.value.trim(), password.value);
    localStorage.setItem("nipcure_token", r.access_token);
    const p = await api.getProfile().catch(() => null);
    location.href = p && p.age ? "dashboard.html" : "profile.html";
  } catch (err) {
    showMsg("error", err.message || "Wrong name or password.");
    btn.disabled = false;
  }
});
