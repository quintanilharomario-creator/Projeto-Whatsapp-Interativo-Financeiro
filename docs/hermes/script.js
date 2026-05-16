'use strict';

// ── Navbar scroll ──────────────────────────────────────────────
const navbar = document.getElementById('navbar');
window.addEventListener('scroll', () => {
  navbar.classList.toggle('scrolled', window.scrollY > 20);
}, { passive: true });

// ── Mobile nav toggle ──────────────────────────────────────────
const navToggle = document.querySelector('.nav-toggle');
navToggle.addEventListener('click', () => {
  navbar.classList.toggle('nav-open');
  navToggle.setAttribute('aria-expanded',
    navbar.classList.contains('nav-open') ? 'true' : 'false');
});

document.querySelectorAll('.nav-links a').forEach(a => {
  a.addEventListener('click', () => navbar.classList.remove('nav-open'));
});

// Close mobile nav on outside click
document.addEventListener('click', e => {
  if (!navbar.contains(e.target)) navbar.classList.remove('nav-open');
});

// ── Scroll animations ──────────────────────────────────────────
const observer = new IntersectionObserver(entries => {
  entries.forEach(entry => {
    if (entry.isIntersecting) {
      entry.target.classList.add('animated');
      observer.unobserve(entry.target);
    }
  });
}, { threshold: 0.12 });

document.querySelectorAll('[data-animate]').forEach(el => {
  // Stagger by position among animated siblings in same parent
  const siblings = [...el.parentElement.querySelectorAll('[data-animate]')];
  el.style.transitionDelay = `${siblings.indexOf(el) * 100}ms`;
  observer.observe(el);
});

// ── FAQ accordion ──────────────────────────────────────────────
document.querySelectorAll('.faq-question').forEach(btn => {
  btn.addEventListener('click', () => {
    const item = btn.closest('.faq-item');
    const isOpen = item.classList.contains('open');
    document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
    if (!isOpen) item.classList.add('open');
  });
});

// ── Smooth CTA scroll for anchor links ────────────────────────
document.querySelectorAll('a[href^="#"]').forEach(a => {
  a.addEventListener('click', e => {
    const target = document.querySelector(a.getAttribute('href'));
    if (!target) return;
    e.preventDefault();
    const top = target.getBoundingClientRect().top + window.scrollY - 72;
    window.scrollTo({ top, behavior: 'smooth' });
  });
});
