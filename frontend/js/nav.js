/**
 * nav.js — mobile hamburger menu (shared across all pages)
 * EcoComply Regulatory Radar | IBM Bobathon 2025
 */
document.addEventListener("DOMContentLoaded", () => {
  const btn    = document.getElementById("navHamburger");
  const drawer = document.getElementById("navDrawer");
  if (!btn || !drawer) return;

  btn.addEventListener("click", () => {
    const open = drawer.classList.toggle("open");
    btn.setAttribute("aria-expanded", open);
  });

  // Close drawer when a link is clicked
  drawer.querySelectorAll("a").forEach(a =>
    a.addEventListener("click", () => drawer.classList.remove("open"))
  );

  // Close on outside tap
  document.addEventListener("click", e => {
    if (!btn.contains(e.target) && !drawer.contains(e.target))
      drawer.classList.remove("open");
  });
});
