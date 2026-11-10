const DEMO_PRODUCTS = [
  {id:"FL-2401",name:"Rau củ hỗn hợp theo mùa",category:"Rau củ",purpose:"human",provider:"Bếp Xanh — ĐH Bách Khoa",weight:8,unit:"kg",price:18000,stock:12,packed:"2026-11-10",expiry:"2026-11-12",storage:"Bảo quản lạnh 2–5°C",checked:"Đã xác nhận thông tin",image:"https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=85",description:"Rau củ tươi được sơ chế tại bếp, đóng gói trong ngày. Thông tin nguồn gốc và thời điểm đóng gói do đơn vị cung cấp khai báo.",place:"Quận 10, TP. Hồ Chí Minh"},
  {id:"FL-2402",name:"Chuối chín tự nhiên",category:"Trái cây",purpose:"human",provider:"Căng tin Mầm Xanh",weight:5,unit:"kg",price:22000,stock:7,packed:"2026-11-10",expiry:"2026-11-11",storage:"Nơi thoáng mát, tránh ánh nắng",checked:"Chờ xác nhận thông tin",image:"https://images.unsplash.com/photo-1571771894821-ce9b6c11b08e?auto=format&fit=crop&w=800&q=85",description:"Chuối chín tự nhiên, phù hợp chế biến trong ngày. Vui lòng kiểm tra tình trạng thực tế khi nhận.",place:"Quận 3, TP. Hồ Chí Minh"},
  {id:"FL-2403",name:"Bã rau củ đã phân loại",category:"Phụ phẩm",purpose:"animal",provider:"Bếp Cộng Đồng",weight:12,unit:"kg",price:5000,stock:5,packed:"2026-11-10",expiry:"2026-11-10",storage:"Sử dụng trong ngày, giữ mát",checked:"Chờ đánh giá phù hợp",image:"https://images.unsplash.com/photo-1518843875459-f738682238a6?auto=format&fit=crop&w=800&q=85",description:"Phụ phẩm sơ chế rau củ, chưa tiếp xúc với người ăn. Bên nhận cần tự đánh giá thành phần và mức độ phù hợp trước khi sử dụng.",place:"Quận 1, TP. Hồ Chí Minh"},
  {id:"FL-2404",name:"Bánh mì trong ngày",category:"Thực phẩm khác",purpose:"human",provider:"Tiệm bánh Nắng",weight:3,unit:"kg",price:15000,stock:9,packed:"2026-11-10",expiry:"2026-11-11",storage:"Đóng kín, nơi khô ráo",checked:"Đã xác nhận thông tin",image:"https://images.unsplash.com/photo-1509440159596-0249088772ff?auto=format&fit=crop&w=800&q=85",description:"Bánh mì còn nguyên bao bì, chưa bán trong ngày. Hạn sử dụng theo thông tin từ đơn vị cung cấp.",place:"Quận 5, TP. Hồ Chí Minh"},
  {id:"FL-2405",name:"Cam sành loại nhỏ",category:"Trái cây",purpose:"human",provider:"Nông trại Hòa Bình",weight:10,unit:"kg",price:12000,stock:18,packed:"2026-11-09",expiry:"2026-11-13",storage:"Thoáng mát, tránh ẩm",checked:"Đã xác nhận thông tin",image:"https://images.unsplash.com/photo-1547514701-42782101795e?auto=format&fit=crop&w=800&q=85",description:"Cam sành loại nhỏ, thu hoạch và đóng gói trong ngày. Có thể dùng ép nước hoặc ăn trực tiếp.",place:"Thành phố Thủ Đức"},
  {id:"FL-2406",name:"Bã đậu nành chưa nấu",category:"Phụ phẩm",purpose:"animal",provider:"Bếp Chay An Lành",weight:6,unit:"kg",price:7000,stock:3,packed:"2026-11-10",expiry:"2026-11-10",storage:"Giữ lạnh, nhận trong ngày",checked:"Chờ đánh giá phù hợp",image:"https://images.unsplash.com/photo-1515543904379-3d757afe72e4?auto=format&fit=crop&w=800&q=85",description:"Phụ phẩm từ quá trình chế biến, chưa tiếp xúc với người ăn. Người nhận cần kiểm tra và chịu trách nhiệm đánh giá phương án sử dụng phù hợp.",place:"Quận Bình Thạnh"}
];
const PARTNERS = [
  {name:"Bếp Xanh — ĐH Bách Khoa",lat:10.772, lng:106.659, area:"Quận 10",items:"Rau củ, bánh mì",qty:"18 kg"},
  {name:"Căng tin Mầm Xanh",lat:10.783,lng:106.687,area:"Quận 3",items:"Trái cây, rau củ",qty:"12 kg"},
  {name:"Bếp Cộng Đồng",lat:10.771,lng:106.699,area:"Quận 1",items:"Phụ phẩm rau củ",qty:"12 kg"},
  {name:"Tiệm bánh Nắng",lat:10.755,lng:106.667,area:"Quận 5",items:"Bánh mì",qty:"3 kg"},
  {name:"Bếp Chay An Lành",lat:10.801,lng:106.714,area:"Bình Thạnh",items:"Phụ phẩm",qty:"6 kg"}
];
const KEY = "foodloop_school_v1";
let state = loadState();
let activeFilter = "all";
let toastTimer;

function route() { return document.body.dataset.page || "home"; }
function go(where) {
  const [page, ...rest] = String(where).split("/");
  const file = page === "home" ? "index.html" : `${page}.html`;
  const id = rest.join("/");
  location.href = `${file}${id ? `?id=${encodeURIComponent(decodeURIComponent(id))}` : ""}`;
}
async function logout() {
  if (typeof backendEnabled !== "undefined" && backendEnabled) {
    try { await apiRequest("/auth/logout", { method: "POST", body: {} }); }
    catch (error) { console.error("Logout request failed:", error); }
  }
  if (typeof clearApiSession === "function") clearApiSession();
  state.user = null;
  persist();
  toast("Đã đăng xuất.");
  go("home");
}

function loadState() {
  try {
    const saved = JSON.parse(localStorage.getItem(KEY) || "{}");
    return {products:saved.products || DEMO_PRODUCTS,orders:saved.orders || [],user:saved.user || null, filterText:""};
  } catch (e) { return {products:DEMO_PRODUCTS,orders:[],user:null,filterText:""}; }
}

function persist() { if (typeof backendEnabled !== "undefined" && backendEnabled) return; localStorage.setItem(KEY, JSON.stringify({products:state.products,orders:state.orders,user:state.user})); }

function esc(s="") { return String(s).replace(/[&<>"']/g,c=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c])); }

function money(n) { return new Intl.NumberFormat("vi-VN").format(Number(n)||0)+"đ"; }

function toast(msg) { const el=document.getElementById("toast"); el.textContent=msg; el.classList.add("show"); clearTimeout(toastTimer); toastTimer=setTimeout(()=>el.classList.remove("show"),2600); }

function safeUser() { return state.user; }

function isAdmin() { return safeUser()?.role==="Quản trị viên"; }

function canSell() { return !!safeUser(); }

function humanProducts() { return state.products.filter(p=>p.purpose==="human" && p.stock>0 && (!backendEnabled || p.status==="approved")); }

function productById(id) { return state.products.find(p=>p.id===id); }

function productCard(p) {
  return `<article class="product-card"><img class="product-photo" src="${esc(p.image)}" alt="${esc(p.name)}" onerror="this.src='https://images.unsplash.com/photo-1540420773420-3366772f4999?auto=format&fit=crop&w=800&q=80'"><div class="product-info"><div class="product-meta"><span class="pill ${p.purpose==="animal"?"animal":""}">${p.purpose==="animal"?"♧ Phụ phẩm — chăn nuôi":"✓ Dùng cho người"}</span><span class="pill ${p.checked.includes("Chờ")?"warning":""}">${esc(p.checked)}</span></div><h3>${esc(p.name)}</h3><div class="product-provider">◉ ${esc(p.provider)}</div><div class="product-facts"><span>⚖ ${p.weight} ${esc(p.unit)}</span><span>▣ Còn ${p.stock} phần</span><span>◷ HSD ${esc(p.expiry)}</span></div><div class="product-bottom"><div class="price">${money(p.price)} <small>/ ${esc(p.unit)}</small></div><div class="card-actions"><button class="button secondary small" onclick="go('product/${encodeURIComponent(p.id)}')">Chi tiết</button><button class="button primary small" onclick="quickOrder('${esc(p.id)}')">Đặt hàng</button></div></div></div></article>`;
}

function statCard(icon,label,value,note="Dữ liệu demo") { return `<div class="stat-card"><div class="stat-top"><span>${label}</span><span class="stat-icon">${icon}</span></div><div class="stat-value">${value}</div><div class="stat-note">${note}</div></div>`; }

function denied(message){return `<main class="main"><div class="auth-wrap"><section class="auth-card"><span class="eyebrow">Khu vực giới hạn</span><h1>Cần đăng nhập</h1><p>${esc(message)}</p><button class="button primary" onclick="go('auth')">Đăng nhập / chọn vai trò</button></section></div></main>`;}

function header() {
  const r = route(), logged = !!safeUser();
  const nav = [["home","Trang ch&#7911;","index.html"],["market","Ch&#7907; th&#7921;c ph&#7849;m","market.html"],["map","B&#7843;n &#273;&#7891;","map.html"],["knowledge","Ki&#7871;n th&#7913;c","knowledge.html"]];
  return `<header class="topbar"><a class="brand" href="index.html"><span class="brand-mark">&#x21bb;</span><span class="brand-name">FoodLoop<small>SCHOOL &#183; CIRCULAR FOOD</small></span></a><button class="icon-btn mobile-menu" onclick="document.querySelector('.nav').classList.toggle('open')" aria-label="M&#7903; menu">&#9776;</button><nav class="nav">${nav.map(([key,label,url])=>`<a class="${r===key?'active':''}" href="${url}">${label}</a>`).join("")}${logged&&!isAdmin()?`<a class="${r==='sell'?'active':''}" href="sell.html">&#272;&#259;ng b&#225;n</a><a class="${r==='dashboard'?'active':''}" href="dashboard.html">Qu&#7843;n l&#253;</a>`:""}${logged&&isAdmin()?`<a class="${r==='admin'?'active':''}" href="admin.html">Qu&#7843;n tr&#7883;</a>`:""}</nav><div class="top-actions"><button class="icon-btn" title="Qu&#233;t QR" onclick="go('scan')">&#9638;</button>${logged?`<button class="button secondary" onclick="go('${isAdmin()?"admin":"dashboard"}')">&#9673; ${esc(safeUser().name.split(" ")[0])}</button><button class="button primary" onclick="logout()">&#272;&#259;ng xu&#7845;t</button>`:`<button class="button primary" onclick="go('auth')">&#272;&#259;ng nh&#7853;p</button>`}</div></header>`;
}
function footer() { return `<footer class="footer"><a class="brand" href="index.html"><span class="brand-mark">&#x21bb;</span><span class="brand-name">FoodLoop<small>SCHOOL &#183; CIRCULAR FOOD</small></span></a><span>&#169; 2026 FoodLoop School &#183; N&#7873;n t&#7843;ng demo kinh t&#7871; tu&#7847;n ho&#224;n</span><div class="footer-links"><a href="knowledge.html">An to&#224;n th&#7921;c ph&#7849;m</a><a href="map.html">&#272;&#7889;i t&#225;c</a><a href="auth.html">Tham gia</a></div></footer>`; }
