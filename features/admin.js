let adminUsers = [];

function adminPage() {
  if (!isAdmin()) return denied("Khu vực chỉ dành cho quản trị viên.");
  return `<main class="main"><div class="page-head"><div><span class="eyebrow">Quản trị nền tảng</span><h1>Trang quản trị viên</h1><p>Quản lý tài khoản, kiểm duyệt bài đăng, đơn hàng và số liệu giao dịch hoàn thành.</p></div></div><div class="kpi-grid">${statCard("◉","Tài khoản",adminUsers.length)}${statCard("▣","Lô hàng",state.products.length)}${statCard("↔","Đơn hàng",state.orders.length)}${statCard("◷","Chờ kiểm duyệt",state.products.filter(p=>p.status==="pending"||p.checked?.includes("Chờ")).length)}</div><div class="admin-layout"><nav class="side-nav"><a class="active" href="admin.html">▦ Tổng quan</a><a href="inventory.html">▣ Quản lý lô hàng</a><a href="orders.html">↔ Quản lý đơn hàng</a><a href="impact.html">◴ Thống kê</a></nav><div><section class="panel"><div class="panel-head"><h2>Quản lý tài khoản</h2><span class="pill">${adminUsers.length} tài khoản</span></div><div class="notice">Mật khẩu không được hiển thị hoặc lưu dạng đọc được. Cơ sở dữ liệu chỉ lưu bản băm; quản trị viên có thể khóa tài khoản, cập nhật tên/vai trò hoặc đặt mật khẩu mới.</div><div class="table-wrap"><table><thead><tr><th>Tên tài khoản</th><th>Email</th><th>Mật khẩu</th><th>Vai trò</th><th>Trạng thái</th><th>Đăng nhập gần nhất</th><th>Thao tác</th></tr></thead><tbody>${adminUsers.length?adminUsers.map(u=>`<tr><td><input class="field" id="user-name-${esc(u.id)}" value="${esc(u.name)}" style="min-width:120px;padding:7px"></td><td>${esc(u.email)}</td><td><span class="pill gray">Đã mã hóa · không xem được</span></td><td>${u.role==="admin"?"Quản trị viên":`<select class="select" id="user-role-${esc(u.id)}" onchange="updateUserRole('${esc(u.id)}',this.value)"><option value="buyer" ${u.role==="buyer"?"selected":""}>Người mua</option><option value="seller" ${u.role==="seller"?"selected":""}>Người bán</option></select>`}</td><td><span class="pill ${u.status==="active"?"":"red"}">${u.status==="active"?"Hoạt động":"Đã khóa"}</span></td><td>${esc(u.lastLogin||"Chưa đăng nhập")}</td><td><div class="table-actions"><button class="button secondary small" onclick="updateUserName('${esc(u.id)}')">Lưu tên</button><button class="button soft small" onclick="resetUserPassword('${esc(u.id)}')">Đặt mật khẩu</button>${u.id!==safeUser().id?`<button class="button ${u.status==="active"?"danger":"primary"} small" onclick="toggleUserStatus('${esc(u.id)}','${u.status==="active"?"suspended":"active"}')">${u.status==="active"?"Khóa":"Mở khóa"}</button>`:""}</div></td></tr>`).join(""):`<tr><td colspan="7"><div class="empty-state">Chưa có tài khoản để hiển thị.</div></td></tr>`}</tbody></table></div></section><section class="panel" style="margin-top:16px"><div class="panel-head"><h2>Kiểm duyệt bài đăng</h2></div><div class="table-wrap"><table><thead><tr><th>Sản phẩm</th><th>Đơn vị</th><th>Phân loại</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${state.products.length?state.products.map(p=>`<tr><td>${esc(p.name)}<small style="display:block;color:#839087">${esc(p.id)}</small></td><td>${esc(p.provider)}</td><td>${p.purpose==="animal"?"Phụ phẩm":"Dùng cho người"}</td><td><span class="pill ${(p.status==="pending"||p.checked?.includes("Chờ"))?"warning":p.status==="inactive"?"gray":""}">${esc(p.status||p.checked)}</span></td><td><div class="table-actions">${(p.status==="pending"||p.checked?.includes("Chờ"))?`<button class="button primary small" onclick="verifyListing('${esc(p.id)}')">Duyệt</button>`:""}<button class="button danger small" onclick="deleteListing('${esc(p.id)}')">Xóa</button></div></td></tr>`).join(""):`<tr><td colspan="5"><div class="empty-state">Chưa có bài đăng.</div></td></tr>`}</tbody></table></div><div class="notice">Duyệt bài chỉ cho phép hiển thị; không phải xác nhận an toàn thực phẩm.</div></section></div></div></main>`;
}

async function loadAdminUsers() {
  if (!backendEnabled || !isAdmin()) return;
  try {
    const [{ users }, { products }] = await Promise.all([
      apiRequest("/admin/users"), apiRequest("/admin/products"),
    ]);
    adminUsers = users;
    state.products = products;
    render();
    const values = document.querySelectorAll(".kpi-grid .stat-card .stat-value");
    const notes = document.querySelectorAll(".kpi-grid .stat-card .stat-note");
    [users.length, products.length, state.orders.length, products.filter(p => p.status === "pending").length]
      .forEach((value, i) => { if (values[i]) values[i].textContent = value; });
    notes.forEach(note => { note.textContent = "Dữ liệu backend"; });
  } catch (error) {
    toast(error.message);
  }
}

async function toggleUserStatus(id, status) {
  try {
    await apiRequest(`/admin/users/${encodeURIComponent(id)}/status`, { method: "PATCH", body: { status } });
    await loadAdminUsers();
    toast(status === "active" ? "Đã mở khóa tài khoản." : "Đã khóa tài khoản.");
  } catch (error) { toast(error.message); }
}

async function updateUserName(id) {
  const name = document.getElementById(`user-name-${id}`)?.value.trim();
  try {
    await apiRequest(`/admin/users/${encodeURIComponent(id)}`, { method: "PATCH", body: { name } });
    await loadAdminUsers();
    toast("Đã cập nhật tên tài khoản.");
  } catch (error) { toast(error.message); }
}

async function updateUserRole(id, role) {
  try {
    await apiRequest(`/admin/users/${encodeURIComponent(id)}`, { method: "PATCH", body: { role } });
    await loadAdminUsers();
    toast("Đã cập nhật vai trò tài khoản.");
  } catch (error) {
    toast(error.message);
    await loadAdminUsers();
  }
}

async function resetUserPassword(id) {
  const newPassword = window.prompt("Nhập mật khẩu mới (ít nhất 10 ký tự). Mật khẩu hiện tại không thể xem được:");
  if (newPassword === null) return;
  try {
    await apiRequest(`/admin/users/${encodeURIComponent(id)}/password`, {
      method: "PATCH", body: { newPassword },
    });
    toast("Đã đặt mật khẩu mới và đăng xuất các phiên hiện tại của tài khoản.");
  } catch (error) { toast(error.message); }
}

async function verifyListing(id) {
  if (backendEnabled) {
    try {
      await apiRequest(`/admin/products/${encodeURIComponent(id)}/approve`, { method: "PATCH", body: {} });
      await loadAdminUsers();
      toast("Đã duyệt bài đăng.");
    } catch (error) { toast(error.message); }
    return;
  }
  const p = productById(id);
  if (p) { p.checked = "Đã xác nhận thông tin"; persist(); render(); toast("Đã cập nhật trạng thái thông tin (demo)."); }
}

async function deleteListing(id) {
  if (!backendEnabled) {
    state.products = state.products.filter(p => p.id !== id);
    persist();
    render();
    return;
  }
  if (!window.confirm("Xóa hoặc ngừng hiển thị bài đăng này?")) return;
  try {
    await apiRequest(`/admin/products/${encodeURIComponent(id)}`, { method: "DELETE" });
    await loadAdminUsers();
    toast("Đã xóa hoặc ngừng hiển thị bài đăng.");
  } catch (error) { toast(error.message); }
}
