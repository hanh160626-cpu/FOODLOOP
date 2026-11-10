let backendEnabled = false;

async function apiRequest(path, options = {}) {
  const headers = { "Content-Type": "application/json", ...(options.headers || {}) };
  const response = await fetch(`/api${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
    body: options.body && typeof options.body !== "string" ? JSON.stringify(options.body) : options.body,
  });
  const result = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(result.error || `Yêu cầu thất bại (${response.status}).`);
  return result;
}

async function loadProductsForSession() {
  if (isAdmin()) return (await apiRequest("/admin/products")).products;
  const [publicData, ownData] = await Promise.all([
    apiRequest("/products"), safeUser() ? apiRequest("/products?mine=true") : Promise.resolve({ products: [] }),
  ]);
  return [...new Map([...(publicData.products || []), ...(ownData.products || [])]
    .map(product => [product.id, product])).values()];
}

async function initializeBackend() {
  if (location.protocol === "file:") return;
  try {
    await apiRequest("/health");
    backendEnabled = true;
    try {
      const { user } = await apiRequest("/auth/me");
      state.user = { ...user, role: user.roleLabel };
    } catch {
      state.user = null;
    }
    state.products = await loadProductsForSession();
    state.orders = [];
    if (state.user) {
      const { orders } = await apiRequest("/orders");
      state.orders = orders.map(o => ({ ...o, statusCode: o.statusCode }));
    }
    render();
    if (route() === "admin" && isAdmin()) loadAdminUsers();
    if (route() === "impact") loadImpactStats();
    if (route() === "home") loadHomeStats();
    if (route() === "market") {
      const note = document.querySelector(".main > .demo-note");
      if (note) note.textContent = "Nguồn cung được lấy từ các bài đăng đã được duyệt.";
    }
  } catch (error) {
    backendEnabled = false;
    console.error("FoodLoop backend connection failed:", error);
    toast("Không kết nối được backend. Đang hiển thị giao diện demo.");
  }
}

function clearApiSession() {
  return;
}

async function loadHomeStats() {
  if (!backendEnabled) return;
  try {
    const data = await apiRequest("/stats");
    const values = document.querySelectorAll(".stats-grid .stat-card .stat-value");
    const notes = document.querySelectorAll(".stats-grid .stat-card .stat-note");
    const actual = [`${data.completed.kg} kg`, data.completed.orders, data.partners, money(data.completed.value)];
    actual.forEach((value, i) => { if (values[i]) values[i].textContent = value; });
    notes.forEach(note => { note.textContent = "Số liệu backend"; });
    const note = document.querySelector(".stats-grid + .demo-note");
    if (note) note.textContent = "Thống kê giao dịch hoàn thành trong hệ thống; không quy đổi khối lượng sang CO₂.";
  } catch (error) {
    toast(error.message);
  }
}
