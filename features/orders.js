const orderStatuses = ["Chờ xác nhận", "Đã xác nhận", "Đang chuẩn bị", "Đang giao", "Hoàn thành", "Đã hủy"];

function isOrderSeller(order) {
  const product = productById(order.productId);
  return isAdmin() || order.sellerId === safeUser()?.id
    || product?.sellerId === safeUser()?.id
    || product?.provider === safeUser()?.name;
}

function ordersPage() {
  if (!safeUser()) return denied("Đăng nhập để theo dõi đơn hàng.");
  const orders = isAdmin()
    ? state.orders
    : state.orders.filter(order => order.buyer === safeUser().name || isOrderSeller(order));
  return `<main class="main"><div class="page-head"><div><span class="eyebrow">Theo dõi giao dịch</span><h1>Quản lý đơn hàng</h1><p>Quản lý cả đơn mua và đơn bán từ một tài khoản. Hàng được trừ kho khi nhà cung cấp xác nhận.</p></div></div><div class="notice">${backendEnabled ? "Đơn hàng và tồn kho được quản lý bởi backend. Khi xác nhận, số lượng được trừ nguyên tử; hủy đơn được hoàn kho theo trạng thái." : "Mô phỏng demo trên trình duyệt."}</div><section class="panel"><div class="table-wrap"><table><thead><tr><th>Mã đơn</th><th>Sản phẩm</th><th>Đối tác / số lượng</th><th>Tổng tiền</th><th>Ngày</th><th>Trạng thái</th><th>Thao tác</th></tr></thead><tbody>${orders.length ? orders.map(order => `<tr><td>${esc(order.id)}</td><td>${esc(order.productName)}</td><td>${isOrderSeller(order) ? esc(order.buyer) : order.qty}</td><td>${money(order.total)}</td><td>${esc(order.created)}</td><td><span class="pill ${order.status === "Hoàn thành" ? "" : order.status === "Đã hủy" ? "gray" : "warning"}">${esc(order.status)}</span></td><td><div class="table-actions">${orderControls(order)}</div></td></tr>`).join("") : `<tr><td colspan="7"><div class="empty-state"><span>↔</span>Chưa có đơn hàng.</div></td></tr>`}</tbody></table></div></section></main>`;
}

function orderControls(order) {
  if (order.status === "Hoàn thành" || order.status === "Đã hủy") return "—";
  if (isOrderSeller(order) && order.status === "Chờ xác nhận") {
    return `<button class="button primary small" onclick="acceptOrder('${esc(order.id)}')">Xác nhận</button><button class="button danger small" onclick="cancelOrder('${esc(order.id)}')">Từ chối</button>`;
  }
  if (isOrderSeller(order) && order.status !== "Chờ xác nhận") {
    return `<button class="button secondary small" onclick="advanceOrder('${esc(order.id)}')">Cập nhật</button>${order.status !== "Đang giao" ? `<button class="button danger small" onclick="cancelOrder('${esc(order.id)}')">Hủy</button>` : ""}`;
  }
  return `<button class="button danger small" onclick="cancelOrder('${esc(order.id)}')">Hủy yêu cầu</button>`;
}

async function refreshOrders() {
  if (!backendEnabled) return;
  try {
    const [{ orders }, products] = await Promise.all([apiRequest("/orders"), loadProductsForSession()]);
    state.orders = orders;
    state.products = products;
    render();
  } catch (error) {
    toast(error.message);
  }
}

async function acceptOrder(id) {
  if (backendEnabled) {
    try {
      await apiRequest(`/orders/${encodeURIComponent(id)}/accept`, { method: "POST", body: {} });
      toast("Đã xác nhận đơn và giữ hàng.");
      await refreshOrders();
    } catch (error) { toast(error.message); }
    return;
  }
  const order = state.orders.find(item => item.id === id);
  const product = order && productById(order.productId);
  if (!order || !product || order.status !== "Chờ xác nhận") return;
  if (product.stock < order.qty) { toast("Tồn kho không đủ; đơn chưa được xác nhận."); return; }
  product.stock -= order.qty;
  order.held = true;
  order.status = "Đã xác nhận";
  persist();
  render();
  toast("Đã xác nhận đơn và giữ hàng.");
}

async function cancelOrder(id) {
  if (backendEnabled) {
    try {
      await apiRequest(`/orders/${encodeURIComponent(id)}/cancel`, { method: "POST", body: {} });
      toast("Đã hủy đơn và hoàn kho nếu hàng đã được giữ.");
      await refreshOrders();
    } catch (error) { toast(error.message); }
    return;
  }
  const order = state.orders.find(item => item.id === id);
  if (!order || ["Hoàn thành", "Đã hủy"].includes(order.status)) return;
  if (order.held) {
    const product = productById(order.productId);
    if (product) product.stock += order.qty;
    order.held = false;
  }
  order.status = "Đã hủy";
  persist();
  render();
  toast("Đã hủy đơn.");
}

async function advanceOrder(id) {
  if (backendEnabled) {
    try {
      await apiRequest(`/orders/${encodeURIComponent(id)}/advance`, { method: "POST", body: {} });
      toast("Trạng thái đơn hàng đã được cập nhật.");
      await refreshOrders();
    } catch (error) { toast(error.message); }
    return;
  }
  const order = state.orders.find(item => item.id === id);
  if (!order) return;
  const index = orderStatuses.indexOf(order.status);
  if (index < 1 || index >= orderStatuses.length - 2) return;
  order.status = orderStatuses[index + 1];
  if (order.status === "Hoàn thành") order.held = false;
  persist();
  render();
  toast("Trạng thái đơn hàng đã được cập nhật.");
}
