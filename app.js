function render() {
  const page = route();
  const id = new URLSearchParams(location.search).get("id") || "";
  let content;
  switch (page) {
    case "market": content = marketPage(); break;
    case "product": content = productPage(id); break;
    case "map": content = mapPage(); break;
    case "sell": content = sellPage(); break;
    case "dashboard": content = dashboardPage(); break;
    case "inventory": content = inventoryPage(); break;
    case "orders": content = ordersPage(); break;
    case "impact": content = impactPage(); break;
    case "knowledge": content = knowledgePage(); break;
    case "auth": content = authPage(); break;
    case "scan": content = qrPage(); break;
    case "qr": content = qrPage(id); break;
    case "admin": content = adminPage(); break;
    default: content = homePage();
  }
  document.getElementById("app").innerHTML = `<div class="shell">${header()}${content}${footer()}</div>`;
  if (page === "map") setupMap();
  if (page === "product" && id) {
    const target = document.getElementById("detail-qr");
    if (target && window.QRCode) new QRCode(target,{text:new URL("scan.html?id="+encodeURIComponent(id),location.href).href,width:76,height:76,colorDark:"#176b45",colorLight:"#ffffff"});
  }
  if (page === "qr" && id) renderQR(id);
  if (page === "scan" && id) lookupQR(id);
}
render();
initializeBackend();
