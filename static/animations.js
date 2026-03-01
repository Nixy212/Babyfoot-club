// ============================================
// BABY-FOOT CLUB - Animations
// ============================================

document.addEventListener('DOMContentLoaded', function() {

  // ======== NAVBAR SCROLL EFFECT ========
  const nav = document.querySelector('.nav');
  if (nav) {
    window.addEventListener('scroll', () => {
      if (window.pageYOffset > 50) {
        nav.classList.add('scrolled');
      } else {
        nav.classList.remove('scrolled');
      }
    });
  }

  // ======== SMOOTH SCROLL ========
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', function(e) {
      const href = this.getAttribute('href');
      if (href !== '#' && href.length > 1) {
        const target = document.querySelector(href);
        if (target) {
          e.preventDefault();
          target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        }
      }
    });
  });

  // ======== PARALLAX SUR LES ORBES ========
  const orbs = document.querySelectorAll('.glow-orb');
  if (orbs.length > 0) {
    let ticking = false;
    window.addEventListener('mousemove', (e) => {
      if (!ticking) {
        window.requestAnimationFrame(() => {
          const mouseX = e.clientX / window.innerWidth;
          const mouseY = e.clientY / window.innerHeight;
          orbs.forEach((orb, index) => {
            const speed = (index + 1) * 20;
            const x = (mouseX - 0.5) * speed;
            const y = (mouseY - 0.5) * speed;
            orb.style.transform = `translate(${x}px, ${y}px)`;
          });
          ticking = false;
        });
        ticking = true;
      }
    });
  }

  // ======== RIPPLE EFFECT SUR BOUTONS ========
  document.querySelectorAll('.btn').forEach(button => {
    button.addEventListener('click', function(e) {
      const ripple = document.createElement('span');
      const rect = this.getBoundingClientRect();
      const size = Math.max(rect.width, rect.height);
      const x = e.clientX - rect.left - size / 2;
      const y = e.clientY - rect.top - size / 2;

      ripple.style.cssText = `
        position: absolute;
        width: ${size}px;
        height: ${size}px;
        left: ${x}px;
        top: ${y}px;
        border-radius: 50%;
        background: rgba(255, 255, 255, 0.4);
        transform: scale(0);
        animation: ripple-effect 0.6s ease-out;
        pointer-events: none;
      `;

      this.appendChild(ripple);
      setTimeout(() => ripple.remove(), 600);
    });
  });

  if (!document.querySelector('#ripple-keyframes')) {
    const style = document.createElement('style');
    style.id = 'ripple-keyframes';
    style.textContent = `
      @keyframes ripple-effect {
        to { transform: scale(4); opacity: 0; }
      }
    `;
    document.head.appendChild(style);
  }

  // ======== INTERSECTION OBSERVER FADE-IN ========
  const fadeObserver = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity = '1';
        entry.target.style.transform = 'translateY(0)';
      }
    });
  }, { threshold: 0.1, rootMargin: '0px 0px -100px 0px' });

  document.querySelectorAll('.feat-cell').forEach((cell, index) => {
    cell.style.opacity = '0';
    cell.style.transform = 'translateY(40px)';
    cell.style.transition = `opacity 0.8s ease ${index * 0.1}s, transform 0.8s ease ${index * 0.1}s`;
    fadeObserver.observe(cell);
  });

  // ======== HOVER 3D SUR FEATURE CARDS ========
  document.querySelectorAll('.feat-cell').forEach(cell => {
    cell.addEventListener('mousemove', function(e) {
      const rect = this.getBoundingClientRect();
      const x = e.clientX - rect.left;
      const y = e.clientY - rect.top;
      const centerX = rect.width / 2;
      const centerY = rect.height / 2;
      const rotateX = (y - centerY) / 30;
      const rotateY = (centerX - x) / 30;
      this.style.transform = `perspective(1000px) rotateX(${rotateX}deg) rotateY(${rotateY}deg) translateY(-12px) scale(1.02)`;
    });
    cell.addEventListener('mouseleave', function() {
      this.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg) translateY(0) scale(1)';
    });
  });

  // ======== CURSOR CUSTOM (Desktop uniquement) ========
  // Check résistant au resize via matchMedia
  const isDesktop = window.matchMedia('(pointer: fine) and (min-width: 769px)');
  if (isDesktop.matches) {
    const cursor = document.createElement('div');
    cursor.className = 'custom-cursor';
    document.body.appendChild(cursor);

    let cursorX = 0, cursorY = 0, targetX = 0, targetY = 0;
    let cursorRAF = null;

    document.addEventListener('mousemove', (e) => {
      targetX = e.clientX;
      targetY = e.clientY;
    });

    function animateCursor() {
      cursorX += (targetX - cursorX) * 0.15;
      cursorY += (targetY - cursorY) * 0.15;
      cursor.style.transform = `translate(${cursorX - 20}px, ${cursorY - 20}px)`;
      cursorRAF = requestAnimationFrame(animateCursor);
    }
    animateCursor();

    const cursorStyle = document.createElement('style');
    cursorStyle.textContent = `
      .custom-cursor {
        position: fixed;
        width: 40px;
        height: 40px;
        border: 2px solid rgba(205, 127, 50, 0.5);
        border-radius: 50%;
        pointer-events: none;
        z-index: 9999;
        top: 0; left: 0;
        will-change: transform;
        transition: width 0.3s, height 0.3s, border-color 0.3s;
      }
      .custom-cursor.active {
        width: 60px;
        height: 60px;
        border-color: rgba(255, 215, 0, 0.8);
      }
    `;
    document.head.appendChild(cursorStyle);

    document.querySelectorAll('a, button, .btn').forEach(el => {
      el.addEventListener('mouseenter', () => cursor.classList.add('active'));
      el.addEventListener('mouseleave', () => cursor.classList.remove('active'));
    });
  }

  // ======== PARTICULES FLOTTANTES (Desktop haute perf uniquement) ========
  const isDesktopForParticles = window.matchMedia('(pointer: fine) and (min-width: 769px)');
  if (isDesktopForParticles.matches) {
    const particleStyle = document.createElement('style');
    particleStyle.textContent = `
      @keyframes float-up {
        0% { transform: translateY(0) translateX(0); opacity: 0; }
        10% { opacity: 0.6; }
        90% { opacity: 0.3; }
        100% { transform: translateY(-100vh) translateX(40px); opacity: 0; }
      }
    `;
    document.head.appendChild(particleStyle);

    function createParticle() {
      const particle = document.createElement('div');
      const size = Math.random() * 4 + 2;
      const startX = Math.random() * window.innerWidth;
      const duration = Math.random() * 20 + 20;
      const delay = Math.random() * 5;

      particle.style.cssText = `
        position: fixed;
        width: ${size}px;
        height: ${size}px;
        background: radial-gradient(circle, rgba(205, 127, 50, 0.6), transparent);
        border-radius: 50%;
        pointer-events: none;
        z-index: 1;
        left: ${startX}px;
        bottom: -20px;
        animation: float-up ${duration}s linear ${delay}s;
        opacity: 0;
        will-change: transform, opacity;
      `;

      document.body.appendChild(particle);
      setTimeout(() => particle.remove(), (duration + delay) * 1000);
    }

    setInterval(createParticle, 6000); // Réduit de 3s à 6s
  }

  // ======== LOADING FADE-IN ========
  // Fade-in léger uniquement si la page est déjà visible (pas de blanc au chargement)
  if (!document.body.classList.contains('no-fade')) {
    document.body.style.opacity = '0';
    document.body.style.transition = 'opacity 0.3s';
    requestAnimationFrame(() => {
      requestAnimationFrame(() => { document.body.style.opacity = '1'; });
    });
  }

});
