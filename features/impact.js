function impactPage(){const done=state.orders.filter(o=>o.status==="Hoàn thành"),kg=done.reduce((sum,o)=>{const p=productById(o.productId);return sum+(p?p.weight*o.qty:0)},0),value=done.reduce((s,o)=>s+o.total,0);return `<main class="main"><div class="page-head"><div><span class="eyebrow">Đo lường giá trị tuần hoàn</span><h1>Thống kê tác động</h1><p>Chỉ tính giao dịch ở trạng thái hoàn thành. Không quy đổi khối lượng sang CO₂ khi chưa có phương pháp đáng tin cậy.</p></div><span class="pill">Dữ liệu demo / trình duyệt</span></div><div class="kpi-grid">${statCard("⚖","Thực phẩm tận dụng",done.length?kg+" kg":"128 kg",done.length?"Từ đơn hoàn thành":"Số liệu demo minh họa")}${statCard("↔","Lô hàng giao dịch",done.length||"46",done.length?"Giao dịch hoàn thành":"Số liệu demo minh họa")}${statCard("₫","Giá trị giao dịch",done.length?money(value):"8,4 tr",done.length?"Giao dịch hoàn thành":"Số liệu demo minh họa")}${statCard("◉","Đối tác tham gia","18","Số liệu demo minh họa")}</div><div class="chart-grid"><section class="panel"><h2>Khối lượng theo tháng</h2><div class="chart">${[38,55,43,70,62,86,52,74,45,91,65,79].map((n,i)=>`<div class="bar-col"><span class="bar-value">${Math.round(n*1.6)}kg</span><div class="bar" style="height:${n}%"></div><span class="bar-label">${["T1","T2","T3","T4","T5","T6","T7","T8","T9","T10","T11","T12"][i]}</span></div>`).join("")}</div><div class="demo-note">Biểu đồ dữ liệu demo, không lấy từ giao dịch thật trong phiên bản này.</div></section><section class="panel"><h2>Nhóm sản phẩm</h2><div class="donut-wrap"><div class="donut"><div class="donut-center">100%<small>demo</small></div></div><div class="legend"><span><i></i> Rau củ · 48%</span><span><i></i> Trái cây · 27%</span><span><i></i> Thực phẩm khác · 15%</span><span><i></i> Phụ phẩm · 10%</span></div></div></section></div><section class="panel" style="margin-top:17px"><h2>Đối tác đóng góp nổi bật</h2><div class="table-wrap"><table><thead><tr><th>#</th><th>Đối tác</th><th>Khối lượng demo</th><th>Giao dịch demo</th></tr></thead><tbody>${["Bếp Xanh — ĐH Bách Khoa","Căng tin Mầm Xanh","Bếp Cộng Đồng"].map((n,i)=>`<tr><td>${i+1}</td><td>${n}</td><td>${[36,28,21][i]} kg</td><td>${[12,9,7][i]}</td></tr>`).join("")}</tbody></table></div><div class="demo-note">Bảng xếp hạng minh họa, chưa phải kết quả thực tế.</div></section></main>`;}

async function loadImpactStats() {
  if (!backendEnabled) return;
  try {
    const data = await apiRequest("/stats");
    const values = document.querySelectorAll(".kpi-grid .stat-card .stat-value");
    const notes = document.querySelectorAll(".kpi-grid .stat-card .stat-note");
    const actual = [data.completed.kg, data.completed.orders, money(data.completed.value), data.partners];
    actual.forEach((value, i) => { if (values[i]) values[i].textContent = i === 0 ? `${value} kg` : value; });
    notes.forEach(note => { note.textContent = "Giao dịch hoàn thành (backend)"; });
    const pageHeadBadge = document.querySelector(".page-head .pill");
    if (pageHeadBadge) pageHeadBadge.textContent = "Dữ liệu backend";
    const chart = document.querySelector(".chart");
    if (chart) {
      const months = data.monthly.slice(-12);
      const max = Math.max(1, ...months.map(row => Number(row.kg)));
      chart.innerHTML = months.length ? months.map(row => {
        const height = Math.max(5, Number(row.kg) / max * 100);
        return `<div class="bar-col"><span class="bar-value">${Number(row.kg)}kg</span><div class="bar" style="height:${height}%"></div><span class="bar-label">${esc(row.month)}</span></div>`;
      }).join("") : `<div class="empty-state" style="width:100%">Chưa có giao dịch hoàn thành.</div>`;
    }
    const legend = document.querySelector(".legend");
    if (legend) legend.innerHTML = data.categories.length
      ? data.categories.map(row => `<span><i></i> ${esc(row.category)} · ${Number(row.kg)} kg</span>`).join("")
      : "<span>Chưa có giao dịch hoàn thành.</span>";
    const rank = document.querySelector(".panel[style*='margin-top:17px'] tbody");
    if (rank) rank.innerHTML = data.leaderboard.length
      ? data.leaderboard.map((row, i) => `<tr><td>${i + 1}</td><td>${esc(row.name)}</td><td>${Number(row.kg)} kg</td><td>${Number(row.orders)}</td></tr>`).join("")
      : `<tr><td colspan="4">Chưa có giao dịch hoàn thành.</td></tr>`;
    const rankHeaders = document.querySelectorAll(".panel[style*='margin-top:17px'] th");
    if (rankHeaders[2]) rankHeaders[2].textContent = "Khối lượng hoàn thành";
    if (rankHeaders[3]) rankHeaders[3].textContent = "Giao dịch hoàn thành";
    const demoNotes = document.querySelectorAll(".demo-note");
    demoNotes.forEach(note => { note.textContent = "Số liệu lấy từ giao dịch hoàn thành trong hệ thống."; });
  } catch (error) {
    toast(error.message);
  }
}
