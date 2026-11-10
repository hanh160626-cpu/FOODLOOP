let authMode = "login";

function authPage() {
  const register = authMode === "register";
  return `<main class="main"><div class="auth-wrap"><section class="auth-card"><span class="eyebrow">Tham gia vòng tuần hoàn</span><h1>${register ? "Tạo tài khoản FoodLoop" : "Chào mừng đến FoodLoop"}</h1><p>${register ? "Đăng ký vai trò người mua hoặc người bán để tham gia cộng đồng." : "Đăng nhập để kết nối cộng đồng thực phẩm xanh."}</p><form id="auth-form" onsubmit="loginSubmit(event)"><div class="form-grid">${register ? `<div class="form-field"><label>Họ và tên</label><input name="name" required maxlength="120" placeholder="Tên hiển thị"></div>` : ""}<div class="form-field"><label>Email</label><input name="email" type="email" required autocomplete="email" placeholder="ban@email.com"></div><div class="form-field"><label>Mật khẩu</label><input name="password" type="password" required minlength="${register ? "10" : "1"}" autocomplete="${register ? "new-password" : "current-password"}" placeholder="${register ? "Ít nhất 10 ký tự" : "Mật khẩu"}"></div>${register ? `<div class="form-field"><label>Loại tài khoản</label><select name="role"><option value="buyer">Người mua</option><option value="seller">Người bán</option></select><span class="help">Tài khoản quản trị được tạo riêng bởi người vận hành hệ thống.</span></div>` : ""}</div><button class="button primary" style="width:100%;margin-top:19px">${register ? "Tạo tài khoản" : "Đăng nhập"}&nbsp; →</button></form><div class="auth-switch">${register ? "Đã có tài khoản?" : "Chưa có tài khoản?"} <a href="#" onclick="event.preventDefault();authMode='${register ? "login" : "register"}';render()"> ${register ? "Đăng nhập" : "Đăng ký"}</a></div>${backendEnabled ? "" : `<div class="notice" style="margin-bottom:0">Khi chạy backend, mật khẩu được băm và không hiển thị trong trang quản trị.</div>`}</section></div></main>`;
}

async function loginSubmit(event) {
  event.preventDefault();
  const form = new FormData(event.currentTarget);
  const values = Object.fromEntries(form.entries());
  if (backendEnabled) {
    try {
      const { user } = await apiRequest(authMode === "register" ? "/auth/register" : "/auth/login", {
        method: "POST",
        body: values,
      });
      state.user = { ...user, role: user.roleLabel };
      state.products = await loadProductsForSession();
      toast(authMode === "register" ? "Tạo tài khoản thành công." : "Đăng nhập thành công.");
      go(isAdmin() ? "admin" : isSeller() ? "dashboard" : "market");
    } catch (error) {
      toast(error.message);
    }
    return;
  }
  if (authMode === "register") {
    toast("Khởi động backend để tạo tài khoản thật.");
    return;
  }
  state.user = { name: values.name || values.email.split("@")[0], email: values.email, role: values.role || "Người mua" };
  persist();
  toast("Đăng nhập demo thành công.");
  go(isAdmin() ? "admin" : isSeller() ? "dashboard" : "market");
}
