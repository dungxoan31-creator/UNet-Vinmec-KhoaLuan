// =============================================================================
// Slide Navigation & Presentation Engine
// Hệ thống Hỗ trợ Chẩn đoán Siêu âm Buồng trứng Human-in-the-Loop
// =============================================================================

(() => {
  'use strict';

  let currentSlide = 0;
  const slides = document.querySelectorAll('.slide');
  const totalSlides = slides.length;
  const progressBar = document.getElementById('progress-bar');
  const slideCounter = document.getElementById('slideCounter');
  const prevBtn = document.getElementById('prevBtn');
  const nextBtn = document.getElementById('nextBtn');
  const fsBtn = document.getElementById('fsBtn');
  const notesDrawer = document.getElementById('notes-drawer');
  const notesContent = document.getElementById('notesContent');
  const notesBtn = document.getElementById('notesBtn');
  const closeNotes = document.getElementById('closeNotes');
  const qaModal = document.getElementById('qa-modal');
  const qaBtn = document.getElementById('qaBtn');
  const closeQa = document.getElementById('closeQa');

  if (!totalSlides) return;

  function updateSlide(newIndex, updateHash = true) {
    if (newIndex < 0 || newIndex >= totalSlides) return;

    if (slides[currentSlide]) {
      slides[currentSlide].classList.remove('active');
    }

    currentSlide = newIndex;

    if (slides[currentSlide]) {
      slides[currentSlide].classList.add('active');
    }

    // Update progress bar
    if (progressBar) {
      const pct = ((currentSlide + 1) / totalSlides) * 100;
      progressBar.style.width = pct + '%';
    }

    // Update counter
    if (slideCounter) {
      slideCounter.textContent = `${String(currentSlide + 1).padStart(2, '0')} / ${String(totalSlides).padStart(2, '0')}`;
    }

    // Update button states
    if (prevBtn) {
      prevBtn.disabled = currentSlide === 0;
      prevBtn.style.opacity = currentSlide === 0 ? '0.45' : '1';
      prevBtn.style.cursor = currentSlide === 0 ? 'not-allowed' : 'pointer';
    }
    if (nextBtn) {
      const isLast = currentSlide === totalSlides - 1;
      nextBtn.textContent = isLast ? 'Hoàn thành ✓' : 'Tiếp theo ›';
    }

    // Update speaker notes
    if (notesContent && slides[currentSlide]) {
      const notes = slides[currentSlide].getAttribute('data-notes') || 'Không có ghi chú cho slide này.';
      notesContent.textContent = notes;
    }

    // Sync URL hash without jumping
    if (updateHash && window.history && window.history.replaceState) {
      window.history.replaceState(null, '', '#' + (currentSlide + 1));
    }
  }

  // Navigation handlers
  if (prevBtn) {
    prevBtn.addEventListener('click', (e) => {
      e.preventDefault();
      updateSlide(currentSlide - 1);
    });
  }

  if (nextBtn) {
    nextBtn.addEventListener('click', (e) => {
      e.preventDefault();
      updateSlide(currentSlide + 1);
    });
  }

  // Keyboard navigation
  window.addEventListener('keydown', (e) => {
    // If typing in input or textarea, skip presentation hotkeys
    if (['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) return;

    // If Q&A modal is open, only handle Escape
    if (qaModal && qaModal.classList.contains('open')) {
      if (e.key === 'Escape') {
        e.preventDefault();
        qaModal.classList.remove('open');
      }
      return;
    }

    if (e.key === 'ArrowRight' || e.key === ' ' || e.key === 'PageDown' || e.key === 'ArrowDown' || e.key === 'Enter') {
      e.preventDefault();
      updateSlide(currentSlide + 1);
    } else if (e.key === 'ArrowLeft' || e.key === 'PageUp' || e.key === 'ArrowUp' || e.key === 'Backspace') {
      e.preventDefault();
      updateSlide(currentSlide - 1);
    } else if (e.key === 'Home') {
      e.preventDefault();
      updateSlide(0);
    } else if (e.key === 'End') {
      e.preventDefault();
      updateSlide(totalSlides - 1);
    } else if (e.key.toLowerCase() === 'n') {
      e.preventDefault();
      if (notesDrawer) notesDrawer.classList.toggle('open');
    } else if (e.key.toLowerCase() === 'f') {
      e.preventDefault();
      toggleFullscreen();
    } else if (e.key.toLowerCase() === 'q') {
      e.preventDefault();
      if (qaModal) qaModal.classList.toggle('open');
    } else if (e.key === 'Escape') {
      if (notesDrawer) notesDrawer.classList.remove('open');
      if (qaModal) qaModal.classList.remove('open');
    }
  });

  // Listen to hashchange (e.g. browser Back / Forward)
  window.addEventListener('hashchange', () => {
    const raw = parseInt(window.location.hash.replace('#', ''), 10);
    if (!isNaN(raw) && raw >= 1 && raw <= totalSlides) {
      updateSlide(raw - 1, false);
    }
  });

  // Speaker notes toggle
  if (notesBtn) {
    notesBtn.addEventListener('click', () => {
      if (notesDrawer) notesDrawer.classList.toggle('open');
    });
  }

  if (closeNotes) {
    closeNotes.addEventListener('click', () => {
      if (notesDrawer) notesDrawer.classList.remove('open');
    });
  }

  // Q&A Modal toggle
  if (qaBtn) {
    qaBtn.addEventListener('click', () => {
      if (qaModal) qaModal.classList.add('open');
    });
  }

  if (closeQa) {
    closeQa.addEventListener('click', () => {
      if (qaModal) qaModal.classList.remove('open');
    });
  }

  if (qaModal) {
    qaModal.addEventListener('click', (e) => {
      if (e.target === qaModal) {
        qaModal.classList.remove('open');
      }
    });
  }

  // Fullscreen toggle
  function toggleFullscreen() {
    if (!document.fullscreenElement) {
      document.documentElement.requestFullscreen().catch(() => {});
    } else {
      document.exitFullscreen().catch(() => {});
    }
  }

  if (fsBtn) {
    fsBtn.addEventListener('click', toggleFullscreen);
  }

  // 12-Minute Countdown Presentation Timer
  let durationSeconds = 12 * 60;
  let timerInterval = null;
  let isTimerRunning = false;
  const timerDisplay = document.getElementById('timerDisplay');
  const timerToggle = document.getElementById('timerToggle');
  const timerBadge = document.getElementById('timerBadge');

  function renderTimer() {
    if (!timerDisplay) return;
    const mins = Math.floor(durationSeconds / 60);
    const secs = durationSeconds % 60;
    timerDisplay.textContent = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    if (timerBadge) {
      if (durationSeconds <= 120 && durationSeconds > 0) {
        timerBadge.classList.add('warning');
      } else {
        timerBadge.classList.remove('warning');
      }
    }
  }

  if (timerToggle) {
    timerToggle.addEventListener('click', () => {
      if (isTimerRunning) {
        clearInterval(timerInterval);
        isTimerRunning = false;
        timerToggle.textContent = 'Tiếp tục';
      } else {
        isTimerRunning = true;
        timerToggle.textContent = 'Tạm dừng';
        timerInterval = setInterval(() => {
          if (durationSeconds > 0) {
            durationSeconds--;
            renderTimer();
          } else {
            clearInterval(timerInterval);
            isTimerRunning = false;
            timerToggle.textContent = 'Hết giờ';
          }
        }, 1000);
      }
    });
  }

  // Initialize with URL hash or slide 0
  const initialHash = parseInt(window.location.hash.replace('#', ''), 10);
  const initialSlide = (!isNaN(initialHash) && initialHash >= 1 && initialHash <= totalSlides) ? (initialHash - 1) : 0;
  updateSlide(initialSlide, false);
  renderTimer();
})();
