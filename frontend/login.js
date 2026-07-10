const API = "http://127.0.0.1:8000";

if (localStorage.getItem("aurum_token")) {
  window.location.replace("index.html");
}

document.getElementById("login-form").addEventListener("submit", async (e) => {
  e.preventDefault();

  const username = document.getElementById("username").value.trim();
  const password = document.getElementById("password").value;
  const btn      = document.getElementById("login-btn");
  const errEl    = document.getElementById("login-error");

  btn.disabled    = true;
  btn.textContent = "Masuk...";
  errEl.classList.add("hidden");

  try {
    const res = await fetch(`${API}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.detail || "Login gagal");
    }

    const { access_token } = await res.json();
    localStorage.setItem("aurum_token", access_token);
    window.location.replace("index.html");
  } catch (err) {
    errEl.textContent = err.message;
    errEl.classList.remove("hidden");
    btn.disabled    = false;
    btn.textContent = "Masuk";
  }
});
