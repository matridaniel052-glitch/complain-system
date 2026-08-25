/**
 * main.js — CKT-UTAS Student Complaint Management System
 * Author: Matri Daniel | ID: 20220404014
 * Handles: role selector, modal, flash auto-dismiss, form validation
 */

document.addEventListener("DOMContentLoaded", function () {

  // ── Role selector on login page ───────────────────────────────────
  const roleOptions = document.querySelectorAll(".role-option");
  roleOptions.forEach(opt => {
    opt.addEventListener("click", function () {
      roleOptions.forEach(o => o.classList.remove("selected"));
      this.classList.add("selected");
      this.querySelector("input").checked = true;
    });
  });

  // ── Auto-dismiss flash messages after 4 seconds ───────────────────
  const flashes = document.querySelectorAll(".flash-msg");
  flashes.forEach(f => {
    setTimeout(() => {
      f.style.transition = "opacity .5s";
      f.style.opacity = "0";
      setTimeout(() => f.remove(), 500);
    }, 4000);
  });

  // ── Respond modal open/close ──────────────────────────────────────
  window.openRespondModal = function (id, subject, currentStatus) {
    const modal = document.getElementById("respond-modal");
    if (!modal) return;
    document.getElementById("modal-subject").textContent = subject;
    document.getElementById("modal-complaint-id").value = id;
    document.getElementById("modal-status").value = currentStatus || "In Progress";
    modal.style.display = 'block';
  };

  window.closeRespondModal = function () {
    const modal = document.getElementById("respond-modal");
    if (modal) modal.style.display = 'none';
  };

  // Close modal on overlay click
  const overlay = document.getElementById("respond-modal");
  if (overlay) {
    overlay.addEventListener("click", function (e) {
      if (e.target === this) closeRespondModal();
    });
  }

  // ── Complaint form validation (Section 3.13 pseudocode) ───────────
  const complaintForm = document.getElementById("complaint-form");
  if (complaintForm) {
    complaintForm.addEventListener("submit", function (e) {
      const subject = document.getElementById("subject")?.value.trim();
      const dept    = document.getElementById("department_id")?.value;
      const desc    = document.getElementById("complaint")?.value.trim();
      const errBox  = document.getElementById("form-error");

      if (!subject || !dept || !desc) {
        e.preventDefault();
        if (errBox) {
          errBox.textContent = "Please complete all required fields.";
          errBox.style.display = "block";
        }
      }
    });
  }

  // ── Sidebar active link highlight ────────────────────────────────
  const path = window.location.pathname;
  document.querySelectorAll(".nav-link").forEach(link => {
    const href = link.getAttribute("href");
    if (href && path.startsWith(href) && href !== "/") {
      link.classList.add("active");
    } else if (href === "/" && path === "/") {
      link.classList.add("active");
    }
  });

  // ── Confirm before delete actions ────────────────────────────────
  document.querySelectorAll(".confirm-action").forEach(btn => {
    btn.addEventListener("click", function (e) {
      if (!confirm("Are you sure you want to proceed?")) {
        e.preventDefault();
      }
    });
  });

  // ── Status quick-update auto-submit ──────────────────────────────
  document.querySelectorAll(".status-select").forEach(sel => {
    sel.addEventListener("change", function () {
      this.closest("form").submit();
    });
  });

  // ── Mobile sidebar drawer (hamburger toggle) ──────────────────────
  window.toggleSidebar = function () {
    document.body.classList.toggle("sidebar-open");
  };

  const sidebarOverlay = document.createElement("div");
  sidebarOverlay.className = "sidebar-overlay";
  sidebarOverlay.addEventListener("click", function () {
    document.body.classList.remove("sidebar-open");
  });
  document.body.appendChild(sidebarOverlay);

  // Close the drawer once a destination is picked, so it doesn't stay open
  // over the page the user just navigated to.
  document.querySelectorAll(".sidebar .nav-link").forEach(link => {
    link.addEventListener("click", function () {
      document.body.classList.remove("sidebar-open");
    });
  });

});