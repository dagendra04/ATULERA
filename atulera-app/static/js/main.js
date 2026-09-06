/* ============================================================
   ATULÉRA — Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  // ============================================================
  // HERO IMAGE SLIDESHOW
  // ============================================================
  const slides = document.querySelectorAll('.hero-slide');
  const dots = document.querySelectorAll('.slide-dot');
  let currentSlide = 0;
  let slideTimer = null;

  function goToSlide(idx) {
    slides[currentSlide].classList.remove('active');
    dots[currentSlide]?.classList.remove('active');
    currentSlide = (idx + slides.length) % slides.length;
    slides[currentSlide].classList.add('active');
    dots[currentSlide]?.classList.add('active');
  }

  function nextSlide() { goToSlide(currentSlide + 1); }
  function prevSlide() { goToSlide(currentSlide - 1); }

  function startAutoplay() {
    stopAutoplay();
    if (slides.length > 1) {
      slideTimer = setInterval(nextSlide, 5000); // ← 5 seconds as requested
    }
  }

  function stopAutoplay() {
    if (slideTimer) { clearInterval(slideTimer); slideTimer = null; }
  }

  document.getElementById('heroNext')?.addEventListener('click', () => { nextSlide(); startAutoplay(); });
  document.getElementById('heroPrev')?.addEventListener('click', () => { prevSlide(); startAutoplay(); });

  dots.forEach(dot => {
    dot.addEventListener('click', () => {
      goToSlide(parseInt(dot.dataset.slide));
      startAutoplay();
    });
  });

  const heroSection = document.getElementById('home');
  if (heroSection) {
    heroSection.addEventListener('mouseenter', stopAutoplay);
    heroSection.addEventListener('mouseleave', startAutoplay);
  }

  // Keyboard navigation
  document.addEventListener('keydown', e => {
    if (e.key === 'ArrowLeft') { prevSlide(); startAutoplay(); }
    if (e.key === 'ArrowRight') { nextSlide(); startAutoplay(); }
  });

  if (slides.length > 1) startAutoplay();


  // ============================================================
  // NAVIGATION — SCROLL EFFECT + ACTIVE LINK
  // ============================================================
  const header = document.getElementById('siteHeader');
  const navLinks = document.querySelectorAll('.nav-link');
  const sections = document.querySelectorAll('section[id]');

  window.addEventListener('scroll', () => {
    // Scrolled header
    if (window.scrollY > 80) {
      header?.classList.add('scrolled');
    } else {
      header?.classList.remove('scrolled');
    }

    // Active nav link
    let current = '';
    sections.forEach(sec => {
      if (window.scrollY >= sec.offsetTop - 180) {
        current = sec.id;
      }
    });
    navLinks.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href') === `#${current}`) {
        link.classList.add('active');
      }
    });
  }, { passive: true });


  // ============================================================
  // MOBILE NAV TOGGLE
  // ============================================================
  const navToggle = document.getElementById('navToggle');
  const primaryNav = document.getElementById('primaryNav');

  navToggle?.addEventListener('click', () => {
    primaryNav?.classList.toggle('open');
  });

  // Close nav when link clicked
  primaryNav?.querySelectorAll('a').forEach(link => {
    link.addEventListener('click', () => primaryNav.classList.remove('open'));
  });


  // ============================================================
  // SERVICE TABS
  // ============================================================
  const tabBtns = document.querySelectorAll('.tab-btn');
  const tabPanels = document.querySelectorAll('.tab-panel');

  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      tabPanels.forEach(p => p.classList.remove('active'));
      btn.classList.add('active');
      const panel = document.getElementById(`tab-${btn.dataset.tab}`);
      if (panel) {
        panel.classList.add('active');
        // Re-trigger reveal for newly visible cards
        panel.querySelectorAll('.reveal').forEach(el => {
          el.classList.remove('visible');
          setTimeout(() => el.classList.add('visible'), 50);
        });
      }
    });
  });


  // ============================================================
  // SCROLL REVEAL ANIMATIONS
  // ============================================================
  const revealEls = document.querySelectorAll('.reveal, .reveal-left, .reveal-right');

  const revealObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.classList.add('visible');
      }
    });
  }, { threshold: 0.12, rootMargin: '0px 0px -60px 0px' });

  revealEls.forEach(el => revealObserver.observe(el));


  // ============================================================
  // ANIMATED COUNTER
  // ============================================================
  const counters = document.querySelectorAll('.counter');

  function animateCounter(el) {
    const target = parseInt(el.dataset.target);
    const duration = 1800;
    const step = target / (duration / 16);
    let current = 0;
    el.style.animation = 'countUp 0.6s ease both';

    const timer = setInterval(() => {
      current = Math.min(current + step, target);
      el.textContent = Math.floor(current) + (el.textContent.includes('+') || el.dataset.suffix === '+' ? '+' : '');
      if (current >= target) {
        el.textContent = target + (el.parentElement.querySelector('.label')?.textContent.includes('%') ? '%' : '+');
        clearInterval(timer);
      }
    }, 16);
  }

  const counterObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        animateCounter(entry.target);
        counterObserver.unobserve(entry.target);
      }
    });
  }, { threshold: 0.5 });

  counters.forEach(el => counterObserver.observe(el));


  // ============================================================
  // FAQ ACCORDION
  // ============================================================
  document.querySelectorAll('.faq-q').forEach(btn => {
    btn.addEventListener('click', () => {
      const item = btn.closest('.faq-item');
      const isOpen = item.classList.contains('open');
      // Close all
      document.querySelectorAll('.faq-item.open').forEach(i => i.classList.remove('open'));
      // Toggle clicked
      if (!isOpen) item.classList.add('open');
    });
  });


  // ============================================================
  // FLASH MESSAGE AUTO-DISMISS
  // ============================================================
  const flashes = document.querySelectorAll('.flash');
  flashes.forEach(flash => {
    setTimeout(() => {
      flash.style.opacity = '0';
      flash.style.transform = 'translateX(20px)';
      flash.style.transition = 'all 0.4s ease';
      setTimeout(() => flash.remove(), 400);
    }, 5000);
  });


  // ============================================================
  // YEAR IN FOOTER
  // ============================================================
  const yearEl = document.getElementById('year');
  if (yearEl) yearEl.textContent = new Date().getFullYear();


  // ============================================================
  // ASSISTANT WIDGET
  // ============================================================
  const assistantToggle = document.getElementById('assistantToggle');
  const assistantPanel = document.getElementById('assistantPanel');
  const assistantClose = document.getElementById('assistantClose');
  const assistantInput = document.getElementById('assistantInput');
  const assistantSend = document.getElementById('assistantSend');
  const assistantBody = document.getElementById('assistantBody');

  assistantToggle?.addEventListener('click', () => {
    assistantPanel?.classList.toggle('open');
    if (assistantPanel?.classList.contains('open')) {
      assistantInput?.focus();
    }
  });

  assistantClose?.addEventListener('click', () => {
    assistantPanel?.classList.remove('open');
  });

  async function sendAssistantQuery() {
    const q = assistantInput?.value.trim();
    if (!q) return;

    // Add user message
    addMsg(q, 'user');
    assistantInput.value = '';

    // Add loading indicator
    const loadingEl = addMsg('Searching...', 'bot loading');

    try {
      const res = await fetch(`/api/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();

      loadingEl.remove();
      addMsg(data.reply, 'bot');

      data.services?.forEach(s => {
        const a = document.createElement('a');
        a.className = 'assistant-result';
        a.href = `/services/${s.slug}`;
        a.target = '_blank';
        a.rel = 'noopener noreferrer';
        a.innerHTML = `<strong>${s.title}</strong> · <span style="opacity:0.7">${s.group_name}</span>`;
        assistantBody?.appendChild(a);
      });

      data.faqs?.forEach(f => {
        addMsg(`<strong>${f.question}</strong><br><small style="opacity:0.75">${f.answer}</small>`, 'bot');
      });
    } catch {
      loadingEl.remove();
      addMsg('Sorry, something went wrong. Please try again or contact us directly.', 'bot');
    }

    assistantBody?.scrollTo({ top: assistantBody.scrollHeight, behavior: 'smooth' });
  }

  function addMsg(text, cls = 'bot') {
    const d = document.createElement('div');
    d.className = `assistant-msg ${cls}`;
    d.innerHTML = text;
    assistantBody?.appendChild(d);
    assistantBody?.scrollTo({ top: assistantBody.scrollHeight, behavior: 'smooth' });
    return d;
  }

  assistantSend?.addEventListener('click', sendAssistantQuery);
  assistantInput?.addEventListener('keydown', e => {
    if (e.key === 'Enter') sendAssistantQuery();
  });


  // ============================================================
  // ADMIN TABS (for admin dashboard)
  // ============================================================
  const adminTabs = document.querySelectorAll('.admin-tab');
  const adminPanels = document.querySelectorAll('.admin-panel');

  adminTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      adminTabs.forEach(t => t.classList.remove('active'));
      adminPanels.forEach(p => p.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById(`panel-${tab.dataset.panel}`);
      target?.classList.add('active');
    });
  });

});
