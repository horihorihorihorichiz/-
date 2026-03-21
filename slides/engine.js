/**
 * Slides-to-Web Engine
 * 16:9のWebスライドナビゲーションエンジン
 * キーボード・タッチ・クリック操作対応
 */
class SlideEngine {
  constructor(options = {}) {
    this.currentSlide = 0;
    this.slides = [];
    this.isTransitioning = false;
    this.transitionDuration = options.transitionDuration || 600;
    this.onSlideChange = options.onSlideChange || null;

    this.init();
  }

  init() {
    this.slides = Array.from(document.querySelectorAll('.slide'));
    this.totalSlides = this.slides.length;

    if (this.totalSlides === 0) return;

    // Create UI elements
    this.createProgressBar();
    this.createSlideNumber();
    this.createNavHint();

    // Bind events
    this.bindKeyboard();
    this.bindTouch();
    this.bindClick();
    this.bindWheel();
    this.bindHashChange();

    // Check URL hash for starting slide
    const hash = window.location.hash;
    if (hash && hash.startsWith('#slide-')) {
      const num = parseInt(hash.replace('#slide-', ''), 10);
      if (num >= 1 && num <= this.totalSlides) {
        this.currentSlide = num - 1;
      }
    }

    // Show first slide
    this.showSlide(this.currentSlide, false);

    // Hide nav hint after first interaction
    this.firstInteraction = false;
  }

  createProgressBar() {
    this.progressBar = document.createElement('div');
    this.progressBar.className = 'slide-progress';
    document.body.appendChild(this.progressBar);
  }

  createSlideNumber() {
    this.slideNumberEl = document.createElement('div');
    this.slideNumberEl.className = 'slide-number';
    document.body.appendChild(this.slideNumberEl);
  }

  createNavHint() {
    this.navHint = document.createElement('div');
    this.navHint.className = 'nav-hint';
    this.navHint.textContent = '← → キーまたはクリックで操作';
    document.body.appendChild(this.navHint);
  }

  bindKeyboard() {
    document.addEventListener('keydown', (e) => {
      switch (e.key) {
        case 'ArrowRight':
        case 'ArrowDown':
        case ' ':
        case 'PageDown':
          e.preventDefault();
          this.next();
          break;
        case 'ArrowLeft':
        case 'ArrowUp':
        case 'PageUp':
          e.preventDefault();
          this.prev();
          break;
        case 'Home':
          e.preventDefault();
          this.goTo(0);
          break;
        case 'End':
          e.preventDefault();
          this.goTo(this.totalSlides - 1);
          break;
        case 'f':
        case 'F':
          this.toggleFullscreen();
          break;
      }
    });
  }

  bindTouch() {
    let startX = 0;
    let startY = 0;

    document.addEventListener('touchstart', (e) => {
      startX = e.touches[0].clientX;
      startY = e.touches[0].clientY;
    }, { passive: true });

    document.addEventListener('touchend', (e) => {
      const dx = e.changedTouches[0].clientX - startX;
      const dy = e.changedTouches[0].clientY - startY;

      if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 50) {
        if (dx < 0) this.next();
        else this.prev();
      }
    }, { passive: true });
  }

  bindClick() {
    document.addEventListener('click', (e) => {
      // Ignore clicks on interactive elements
      if (e.target.closest('a, button, input, select, textarea')) return;

      const x = e.clientX / window.innerWidth;
      if (x > 0.5) this.next();
      else this.prev();
    });
  }

  bindWheel() {
    let wheelTimeout = null;
    document.addEventListener('wheel', (e) => {
      e.preventDefault();
      if (wheelTimeout) return;
      wheelTimeout = setTimeout(() => { wheelTimeout = null; }, 800);

      if (e.deltaY > 0) this.next();
      else this.prev();
    }, { passive: false });
  }

  bindHashChange() {
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash;
      if (hash && hash.startsWith('#slide-')) {
        const num = parseInt(hash.replace('#slide-', ''), 10);
        if (num >= 1 && num <= this.totalSlides) {
          this.goTo(num - 1);
        }
      }
    });
  }

  next() {
    if (this.currentSlide < this.totalSlides - 1) {
      this.goTo(this.currentSlide + 1);
    }
  }

  prev() {
    if (this.currentSlide > 0) {
      this.goTo(this.currentSlide - 1);
    }
  }

  goTo(index) {
    if (index === this.currentSlide || this.isTransitioning) return;
    if (index < 0 || index >= this.totalSlides) return;

    this.hideNavHint();
    this.isTransitioning = true;
    this.currentSlide = index;
    this.showSlide(index, true);

    setTimeout(() => {
      this.isTransitioning = false;
    }, this.transitionDuration);
  }

  showSlide(index, animate = true) {
    // Update active class
    this.slides.forEach((slide, i) => {
      slide.classList.toggle('active', i === index);
    });

    // Update progress bar
    const progress = ((index + 1) / this.totalSlides) * 100;
    this.progressBar.style.width = `${progress}%`;

    // Update slide number
    this.slideNumberEl.textContent = `${index + 1} / ${this.totalSlides}`;

    // Update URL hash
    history.replaceState(null, null, `#slide-${index + 1}`);

    // Callback
    if (this.onSlideChange) {
      this.onSlideChange(index, this.totalSlides);
    }
  }

  hideNavHint() {
    if (!this.firstInteraction) {
      this.firstInteraction = true;
      this.navHint.style.transition = 'opacity 1s ease';
      this.navHint.style.opacity = '0';
      setTimeout(() => this.navHint.remove(), 1000);
    }
  }

  toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }
}

// Auto-initialize
document.addEventListener('DOMContentLoaded', () => {
  window.slideEngine = new SlideEngine();
});
