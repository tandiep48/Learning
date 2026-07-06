async function fetchLessons() {
    // Expects 'window.practiceNumber' to be defined globally by the HTML template
    const num = window.practiceNumber;
    const category = window.practiceCategory || 'practice';
    try {
        const res = await fetch(`/api/practice/${num}?category=${encodeURIComponent(category)}`);
        const data = await res.json();
        
        if (!res.ok) {
            document.getElementById('lesson-grid').innerHTML = `<p style="color:red">${t('practice_select.error_prefix', { error: data.error })}</p>`;
            return;
        }

        const grid = document.getElementById('lesson-grid');
        grid.innerHTML = '';

        if (!data.lessons || data.lessons.length === 0) {
            grid.innerHTML = `<p>${t('practice_select.no_lessons_found')}</p>`;
            return;
        }

        data.lessons.forEach(lesson => {
            const card = document.createElement('a');
            card.href = `/practice/${num}/${lesson}?category=${encodeURIComponent(category)}`;
            card.className = 'lesson-card';
            card.innerHTML = `
                <div class="lesson-label">${t('picker.lesson_prefix')} ${lesson}</div>
            `;
            // Set referrer so practice.js can build the correct Back button
            card.addEventListener('click', () => {
                sessionStorage.setItem('practice_referrer', `${category}-${num}`);
            });
            grid.appendChild(card);
        });
    } catch (e) {
        document.getElementById('lesson-grid').innerHTML = `<p style="color:red">${t('practice_select.failed_connect')}</p>`;
    }
}

// Update Back button based on where the user came from
function applyReferrer() {
    const referrer = sessionStorage.getItem('practice_referrer');
    const backLink = document.querySelector('.page-back');
    if (!backLink) return;
    if (referrer === 'recommend') {
        backLink.href = '/recommend';
        backLink.textContent = `← ${t('practice_select.back_to_recommendations')}`;
    }
    // Don't clear here — keep it so the lesson card click can override
}

applyReferrer();
fetchLessons();
