let currentPassage = null;
let pinyinVisible = false;
let meaningVisible = false;
let currentAudio = null;

// Fetch passages on load
window.onload = async () => {
    try {
        const res = await fetch('/api/lesson/passages');
        const data = await res.json();
        const container = document.getElementById('passage-container');
        container.innerHTML = '';

        const grouped = {};
        data.passages.forEach(p => {
            const level = p.hsk_level || "Other";
            if (!grouped[level]) grouped[level] = [];
            grouped[level].push(p);
        });

        const levels = Object.keys(grouped).sort();

        levels.forEach(level => {
            const section = document.createElement('div');
            section.className = 'passage-section';
            
            const header = document.createElement('h3');
            header.innerText = level;
            section.appendChild(header);

            const grid = document.createElement('div');
            grid.className = 'dashboard-container';
            grid.style.marginTop = '10px';

            grouped[level].forEach(p => {
                const btn = document.createElement('div');
                btn.className = 'dash-card';
                btn.style.padding = '15px';
                btn.innerHTML = `<div class="dash-title" style="font-size:18px;">${p.passage_id}</div><div class="dash-desc">${p.line_count} sentences</div>`;
                btn.onclick = () => loadPassage(p.passage_id);
                grid.appendChild(btn);
            });

            section.appendChild(grid);
            container.appendChild(section);
        });
    } catch (e) {
        document.getElementById('passage-container').innerHTML = '<p>Error loading passages.</p>';
    }
};

function switchScreen(screenId) {
    document.querySelectorAll('.screen').forEach(el => el.classList.remove('active'));
    document.getElementById(screenId).classList.add('active');
    
    // Stop any playing audio when switching screens
    if (currentAudio) {
        currentAudio.pause();
    }
}

function goHome() {
    switchScreen('screen-menu');
    currentPassage = null;
}

async function loadPassage(passage_id) {
    switchScreen('screen-loading');
    
    try {
        const response = await fetch(`/api/lesson/passage/${passage_id}`);
        const data = await response.json();
        
        if (!response.ok) {
            alert(data.error || "Failed to load passage.");
            goHome();
            return;
        }
        
        currentPassage = data.passage;
        renderPassage();
        switchScreen('screen-reading');
        
    } catch(e) {
        alert("Error connecting to server.");
        goHome();
    }
}

function renderPassage() {
    document.getElementById('reading-title').innerText = currentPassage.passage_id;
    
    const contentDiv = document.getElementById('reading-content');
    contentDiv.innerHTML = '';
    
    currentPassage.lines.forEach((line, index) => {
        const lineDiv = document.createElement('div');
        lineDiv.className = 'reading-line';
        
        // Setup Audio logic
        let audioHTML = '';
        if (line.audio_key) {
            let hskLevel = currentPassage.hsk_level || 'H1';
            const audioSrc = `/lesson_audio/${hskLevel}/${line.audio_key}.mp3`;
            audioHTML = `
                <button class="audio-btn" onclick="playAudio('${audioSrc}')" title="Play Audio">
                    🔊
                </button>
            `;
        }
        
        const pinyinClass = pinyinVisible ? 'pinyin-text show' : 'pinyin-text';
        const meaningClass = meaningVisible ? 'meaning-text show' : 'meaning-text';
        
        const textHTML = `
            <div class="reading-text">
                <div class="hanzi-text">${line.content}</div>
                <div class="${pinyinClass}">${line.pinyin || ''}</div>
                <div class="${meaningClass}">${line.translations.vi || line.translations.en || ''}</div>
            </div>
        `;
        
        lineDiv.innerHTML = textHTML + audioHTML;
        contentDiv.appendChild(lineDiv);
    });
    
    updatePinyinBtnText();
    updateMeaningBtnText();
}

function playAudio(src) {
    if (currentAudio) {
        currentAudio.pause();
    }
    currentAudio = new Audio(src);
    currentAudio.play().catch(e => console.warn("Audio playback failed", e));
}

function togglePinyin() {
    pinyinVisible = !pinyinVisible;
    const pinyinElements = document.querySelectorAll('.pinyin-text');
    pinyinElements.forEach(el => {
        if (pinyinVisible) {
            el.classList.add('show');
        } else {
            el.classList.remove('show');
        }
    });
    updatePinyinBtnText();
}

function toggleMeaning() {
    meaningVisible = !meaningVisible;
    const meaningElements = document.querySelectorAll('.meaning-text');
    meaningElements.forEach(el => {
        if (meaningVisible) {
            el.classList.add('show');
        } else {
            el.classList.remove('show');
        }
    });
    updateMeaningBtnText();
}

function updateMeaningBtnText() {
    const btn = document.getElementById('toggle-meaning-btn');
    if (meaningVisible) {
        btn.innerText = "Hide Meaning";
        btn.classList.add('primary');
    } else {
        btn.innerText = "Show Meaning";
        btn.classList.remove('primary');
    }
}

function updatePinyinBtnText() {
    const btn = document.getElementById('toggle-pinyin-btn');
    if (pinyinVisible) {
        btn.innerText = "Hide Pinyin";
        btn.classList.add('primary');
    } else {
        btn.innerText = "Show Pinyin";
        btn.classList.remove('primary');
    }
}

function filterPassages() {
    const query = document.getElementById('search-input').value.toLowerCase();
    const sections = document.querySelectorAll('.passage-section');
    
    sections.forEach(section => {
        const cards = section.querySelectorAll('.dash-card');
        let hasVisible = false;
        cards.forEach(card => {
            const title = card.querySelector('.dash-title').innerText.toLowerCase();
            if (title.includes(query)) {
                card.style.display = 'flex';
                hasVisible = true;
            } else {
                card.style.display = 'none';
            }
        });
        
        if (hasVisible) {
            section.style.display = 'block';
        } else {
            section.style.display = 'none';
        }
    });
}
