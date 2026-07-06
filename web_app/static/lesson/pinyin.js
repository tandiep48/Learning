document.addEventListener('DOMContentLoaded', () => {

    const pronunciationMap = {
        "b": "Like 'p' in 'spit'",
        "p": "Like 'p' in 'pit'",
        "m": "Like 'm' in 'man'",
        "f": "Like 'f' in 'fan'",
        "d": "Like 't' in 'stop'",
        "t": "Like 't' in 'top'",
        "n": "Like 'n' in 'not'",
        "l": "Like 'l' in 'lot'",
        "g": "Like 'k' in 'skill'",
        "k": "Like 'k' in 'kill'",
        "h": "Like 'h' in 'hat'",
        "j": "Like 'j' in 'jeep'",
        "q": "Like 'ch' in 'cheat'",
        "x": "Like 'sh' in 'sheet'",
        "zh": "Like 'j' in 'jump'",
        "ch": "Like 'ch' in 'church'",
        "sh": "Like 'sh' in 'shoe'",
        "r": "Like 'r' in 'run' but with tongue curled back",
        "z": "Like 'ds' in 'pads'",
        "c": "Like 'ts' in 'cats'",
        "s": "Like 's' in 'sun'"
    };

    window.playPinyin = function(pinyinText) {
        if (window.currentAudio) {
            window.currentAudio.pause();
        }
        const audioUrl = `https://storage.googleapis.com/chinese-learning-audio-assets/audio_pinyin/${encodeURIComponent(pinyinText)}.mp3`;
        const audio = new Audio(audioUrl);
        window.currentAudio = audio;
        
        audio.play().catch(e => {
            console.warn("Audio playback failed from bucket, falling back to TTS:", e);
            if ('speechSynthesis' in window) {
                let textToSpeak = pinyinText.replace(/[āáǎà]/g, 'a')
                                            .replace(/[ōóǒò]/g, 'o')
                                            .replace(/[ēéěè]/g, 'e')
                                            .replace(/[īíǐì]/g, 'i')
                                            .replace(/[ūúǔù]/g, 'u')
                                            .replace(/[ǖǘǚǜü]/g, 'v');
                
                let utterance = new SpeechSynthesisUtterance(textToSpeak);
                utterance.lang = 'zh-CN';
                window.speechSynthesis.speak(utterance);
            }
        });
    };

    const tooltip = document.getElementById('pinyin-tooltip');
    if (tooltip) {
        document.body.appendChild(tooltip);
    }

    
    window.showPronunciation = function(element, event) {
        if (!tooltip) return;
        const pinyin = element.innerText.trim();
        if (!pinyin) return;
        
        const detail = pronunciationMap[pinyin] || t('pinyin.pronunciation_for', { syllable: pinyin });
        tooltip.innerText = detail;
        tooltip.classList.add('visible');
        
        tooltip.style.left = (event.pageX + 10) + 'px';
        tooltip.style.top = (event.pageY + 10) + 'px';
    };
    
    window.hidePronunciation = function() {
        if (!tooltip) return;
        tooltip.classList.remove('visible');
    };

    // Advanced Pinyin Popover
    const popover = document.getElementById('pinyin-popover');
    if (popover) {
        document.body.appendChild(popover);
    }

    let activePopoverId = null;

    const toneMarks = {
        'a': ['ā', 'á', 'ǎ', 'à'],
        'o': ['ō', 'ó', 'ǒ', 'ò'],
        'e': ['ē', 'é', 'ě', 'è'],
        'i': ['ī', 'í', 'ǐ', 'ì'],
        'u': ['ū', 'ú', 'ǔ', 'ù'],
        'ü': ['ǖ', 'ǘ', 'ǚ', 'ǜ']
    };

    function addTone(syllable, toneIndex) {
        let targetVowel = '';
        if (syllable.includes('a')) targetVowel = 'a';
        else if (syllable.includes('o')) targetVowel = 'o';
        else if (syllable.includes('e')) targetVowel = 'e';
        else if (syllable.includes('iu')) targetVowel = 'u';
        else if (syllable.includes('ui')) targetVowel = 'i';
        else if (syllable.includes('i')) targetVowel = 'i';
        else if (syllable.includes('u')) targetVowel = 'u';
        else if (syllable.includes('ü')) targetVowel = 'ü';

        if (targetVowel) {
            return syllable.replace(targetVowel, toneMarks[targetVowel][toneIndex]);
        }
        return syllable;
    }

    function getTones(syllable) {
        return [0, 1, 2, 3].map(i => addTone(syllable, i));
    }

    window.playTone = function(pinyinWithTone) {
        if (window.currentAudio) {
            window.currentAudio.pause();
        }
        const audioUrl = `https://storage.googleapis.com/chinese-learning-audio-assets/audio_pinyin/${encodeURIComponent(pinyinWithTone)}.mp3`;
        const audio = new Audio(audioUrl);
        window.currentAudio = audio;
        
        audio.play().catch(e => {
            console.warn("Audio playback failed from bucket, falling back to TTS:", e);
            if ('speechSynthesis' in window) {
                let utterance = new SpeechSynthesisUtterance(pinyinWithTone);
                utterance.lang = 'zh-CN';
                window.speechSynthesis.speak(utterance);
            }
        });
        
        window.closePinyinPopover();
    };

    window.displayPinyinPopover = function(pinyinId, event) {
        if (!popover) return;
        
        // Toggle if clicking the same active popover
        if (activePopoverId === pinyinId && popover.style.display !== 'none') {
            window.closePinyinPopover();
            return;
        }
        
        activePopoverId = pinyinId;
        const rect = event.target.getBoundingClientRect();
        
        const tones = getTones(pinyinId);
        let html = '';
        tones.forEach(tone => {
            html += `<div onclick="playTone('${tone}')" class="tone-button">${tone} <i class="fa-solid fa-volume-high"></i></div>`;
        });
        popover.innerHTML = html;
        
        popover.style.display = 'flex';
        popover.style.top = (rect.bottom + window.scrollY) + 'px';
        popover.style.left = (rect.left + window.scrollX) + 'px';
    };

    window.closePinyinPopover = function() {
        if (!popover) return;
        popover.style.display = 'none';
        activePopoverId = null;
    };

    document.addEventListener('click', (e) => {
        if (activePopoverId && popover) {
            if (!e.target.closest('.pinyin-popover') && !e.target.closest('.btn-pinyin')) {
                window.closePinyinPopover();
            }
        }
    });
});
