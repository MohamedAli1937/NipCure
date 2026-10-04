api.requireAuth();
const $ = (id) => document.getElementById(id);
const MAP = {
  age: "age",
  allergies: "allergies",
  food_likes: "likes",
  food_dislikes: "dislikes",
  dietary_restrictions: "diet",
  notes: "notes",
};

(async () => {
  try {
    const p = await api.getProfile();
    if (p && p.age) {
      for (const [key, id] of Object.entries(MAP)) $(id).value = p[key] ?? "";
      $("title").textContent = "Your profile";
      $("back").classList.remove("hidden");
    }
  } catch (e) {
    showMsg("error", e.message);
  }
})();

$("form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const age = Number($("age").value);
  if (!age || age < 1 || age > 120)
    return showMsg("error", "Please enter your age as a number.");
  $("save").disabled = true;
  try {
    await api.saveProfile({
      age: Number($("age").value),
      allergies: allergies.value,
      food_likes: likes.value,
      food_dislikes: dislikes.value,
      dietary_restrictions: diet.value,
      notes: notes.value,
    });
    showMsg("success", "Saved.");
    setTimeout(() => (location.href = "dashboard.html"), 900);
  } catch (err) {
    showMsg("error", err.message);
    $("save").disabled = false;
  }
});
