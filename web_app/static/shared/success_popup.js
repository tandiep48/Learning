/**
 * success_popup.js — shared celebration popup for vocab_trainer & lesson_trainer
 *
 * Usage:
 *   SuccessPopup.show({
 *     total:    <number>,   // total tasks attempted
 *     correct:  <number>,   // number correct
 *     onContinue: fn,       // called when primary CTA is clicked
 *     onRetry:  fn | null,  // if provided, shows a "Retry Missed" button
 *     onHome:   fn,         // called when "Back to Menu" is clicked
 *     continueLabel: 'View Summary',  // optional CTA label
 *   });
 */
const SuccessPopup = (() => {
    let _overlay = null;
    let _canvas  = null;
    let _animFrame = null;
    let _confettiParticles = [];

    // ── Build DOM once ──────────────────────────────────────────
    function _ensureDom() {
        if (_overlay) return;

        _overlay = document.createElement('div');
        _overlay.className = 'success-popup-overlay';
        _overlay.innerHTML = `
            <div class="success-popup" id="sp-card">
                <canvas id="sp-confetti-canvas"></canvas>
                <div class="sp-icon-wrap" id="sp-icon">🎉</div>
                <h2 class="sp-title" id="sp-title">Training Complete!</h2>
                <p class="sp-subtitle" id="sp-subtitle">Great job finishing the session.</p>
                <div class="sp-stats">
                    <div class="sp-stat">
                        <div class="sp-stat-value" id="sp-total">0</div>
                        <div class="sp-stat-label">Tasks</div>
                    </div>
                    <div class="sp-stat">
                        <div class="sp-stat-value correct" id="sp-correct">0</div>
                        <div class="sp-stat-label">Correct</div>
                    </div>
                    <div class="sp-stat">
                        <div class="sp-stat-value accuracy" id="sp-accuracy">0%</div>
                        <div class="sp-stat-label">Accuracy</div>
                    </div>
                </div>
                <div class="sp-accuracy-bar-wrap">
                    <div class="sp-accuracy-bar" id="sp-bar"></div>
                </div>
                <div class="sp-actions" id="sp-actions"></div>
            </div>`;

        document.body.appendChild(_overlay);
        _canvas = _overlay.querySelector('#sp-confetti-canvas');
    }

    // ── Confetti ─────────────────────────────────────────────────
    const COLORS = ['#4ade80','#818cf8','#f472b6','#facc15','#38bdf8','#fb923c'];
    function _initConfetti(perfect) {
        if (!perfect) return; // only full confetti on perfect score
        const card = _overlay.querySelector('.success-popup');
        const W = card.clientWidth;
        const H = card.clientHeight;
        _canvas.width  = W;
        _canvas.height = H;
        _confettiParticles = Array.from({length: 80}, () => ({
            x: Math.random() * W,
            y: Math.random() * H * -0.5,
            r: Math.random() * 5 + 3,
            color: COLORS[Math.floor(Math.random() * COLORS.length)],
            speed: Math.random() * 2.5 + 1.2,
            drift: (Math.random() - 0.5) * 1.5,
            rot: Math.random() * Math.PI * 2,
            spin: (Math.random() - 0.5) * 0.15,
            shape: Math.random() > 0.5 ? 'rect' : 'circle'
        }));
        _animFrame = requestAnimationFrame(_tickConfetti);
    }

    function _tickConfetti() {
        const ctx = _canvas.getContext('2d');
        ctx.clearRect(0, 0, _canvas.width, _canvas.height);
        let alive = false;
        _confettiParticles.forEach(p => {
            p.y += p.speed;
            p.x += p.drift;
            p.rot += p.spin;
            if (p.y < _canvas.height + 10) alive = true;
            ctx.save();
            ctx.translate(p.x, p.y);
            ctx.rotate(p.rot);
            ctx.fillStyle = p.color;
            ctx.globalAlpha = Math.max(0, 1 - p.y / _canvas.height);
            if (p.shape === 'rect') {
                ctx.fillRect(-p.r, -p.r / 2, p.r * 2, p.r);
            } else {
                ctx.beginPath();
                ctx.arc(0, 0, p.r / 2, 0, Math.PI * 2);
                ctx.fill();
            }
            ctx.restore();
        });
        if (alive) {
            _animFrame = requestAnimationFrame(_tickConfetti);
        }
    }

    function _stopConfetti() {
        if (_animFrame) { cancelAnimationFrame(_animFrame); _animFrame = null; }
        if (_canvas) {
            const ctx = _canvas.getContext('2d');
            ctx.clearRect(0, 0, _canvas.width, _canvas.height);
        }
        _confettiParticles = [];
    }

    // ── Public API ───────────────────────────────────────────────
    function show({ total = 0, correct = 0, onContinue, onRetry = null, onHome, continueLabel = 'View Results' } = {}) {
        _ensureDom();
        _stopConfetti();

        const missed   = total - correct;
        const isPerfect = missed === 0 && total > 0;
        const accuracy  = total > 0 ? Math.round((correct / total) * 100) : 0;

        // Icon & title
        const iconEl = _overlay.querySelector('#sp-icon');
        iconEl.textContent = isPerfect ? '🏆' : '✅';
        iconEl.className   = `sp-icon-wrap ${isPerfect ? 'perfect' : 'has-missed'}`;

        _overlay.querySelector('#sp-title').textContent =
            isPerfect ? 'Perfect Score! 🎉' : 'Session Complete!';
        _overlay.querySelector('#sp-subtitle').textContent =
            isPerfect
                ? 'You got every question right. Incredible!'
                : `Almost there — ${missed} question${missed > 1 ? 's' : ''} to review.`;

        // Stats
        _overlay.querySelector('#sp-total').textContent    = total;
        _overlay.querySelector('#sp-correct').textContent  = correct;
        _overlay.querySelector('#sp-accuracy').textContent = `${accuracy}%`;

        // Accuracy bar colour
        const barEl = _overlay.querySelector('#sp-bar');
        barEl.style.width = '0%';
        const barColor = accuracy >= 90 ? '#16a34a' : accuracy >= 60 ? '#007a61' : '#f87171';
        barEl.style.background = `linear-gradient(90deg, ${barColor}, ${barColor}aa)`;
        // Animate bar after a frame
        requestAnimationFrame(() => requestAnimationFrame(() => {
            barEl.style.width = `${accuracy}%`;
        }));

        // Action buttons
        const actionsEl = _overlay.querySelector('#sp-actions');
        actionsEl.innerHTML = '';

        // "Back to Menu" secondary
        const homeBtn = document.createElement('button');
        homeBtn.className = 'sp-btn secondary';
        homeBtn.innerHTML = '<i class="fa-solid fa-house"></i> Menu';
        homeBtn.onclick = () => { hide(); if (onHome) onHome(); };
        actionsEl.appendChild(homeBtn);

        // "Retry Missed" warning (optional)
        if (onRetry && missed > 0) {
            const retryBtn = document.createElement('button');
            retryBtn.className = 'sp-btn warning';
            retryBtn.innerHTML = '<i class="fa-solid fa-rotate-right"></i> Retry Missed';
            retryBtn.onclick = () => { hide(); onRetry(); };
            actionsEl.appendChild(retryBtn);
        }

        // Primary CTA
        const continueBtn = document.createElement('button');
        continueBtn.className = 'sp-btn primary';
        continueBtn.innerHTML = `<i class="fa-solid fa-arrow-right"></i> ${continueLabel}`;
        continueBtn.onclick = () => { hide(); if (onContinue) onContinue(); };
        actionsEl.appendChild(continueBtn);

        // Show overlay
        _overlay.classList.add('open');

        // Trigger confetti for perfect score
        setTimeout(() => _initConfetti(isPerfect), 100);
    }

    function hide() {
        _stopConfetti();
        if (_overlay) _overlay.classList.remove('open');
    }

    return { show, hide };
})();
