const name = document.getElementById("name");
const password = document.getElementById("password");

document.getElementById("step1").addEventListener("submit", async (e) => {
  e.preventDefault();
  if (password.value.length < 6)
    return showMsg("error", "Password needs at least 6 characters.");
  const btn = document.getElementById("next");
  btn.disabled = true;
  try {
    const r = await api.register(name.value.trim(), password.value);
    localStorage.setItem("nipcure_token", r.access_token);
    location.href = "profile.html";
  } catch (err) {
    showMsg("error", err.message);
    btn.disabled = false;
  }
});
