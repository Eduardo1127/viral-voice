// ViralVoice AI Studio - Client Application
document.addEventListener('DOMContentLoaded', () => {
  // Elements
  const scriptText = document.getElementById('scriptText');
  const charCount = document.getElementById('charCount');
  const btnPaste = document.getElementById('btnPaste');
  const btnClear = document.getElementById('btnClear');
  const voiceSelect = document.getElementById('voiceSelect');
  const dspPreset = document.getElementById('dspPreset');
  const speedSlider = document.getElementById('speedSlider');
  const speedVal = document.getElementById('speedVal');
  const pitchSlider = document.getElementById('pitchSlider');
  const pitchVal = document.getElementById('pitchVal');
  const btnPreview = document.getElementById('btnPreview');
  const btnGenerate = document.getElementById('btnGenerate');
  const statusBar = document.getElementById('statusBar');
  const playerCard = document.getElementById('playerCard');
  const audioPlayer = document.getElementById('audioPlayer');
  const currentVoiceBadge = document.getElementById('currentVoiceBadge');
  const btnDownloadDsp = document.getElementById('btnDownloadDsp');
  const btnDownloadRaw = document.getElementById('btnDownloadRaw');
  const btnInstall = document.getElementById('btnInstall');

  // Templates
  const templateButtons = document.querySelectorAll('.pill-btn');
  const templates = {
    misterio: 'A más de once mil metros de profundidad, en la fosa de las Marianas, la luz del sol jamás ha tocado el fondo. Sin embargo, algo vivo acaba de moverse en la más completa oscuridad.',
    historia: 'En el año 1518, en la ciudad de Estrasburgo, una mujer comenzó a bailar sin música en medio de la calle. En cuestión de días, cientos de personas se unieron sin poder parar hasta el colapso.',
    curiosidad: '¿Sabías que los pulpos tienen tres corazones y su sangre es de color azul? Dos de sus corazones dejan de latir en el momento exacto en que comienzan a nadar.',
    terror: 'Si alguna vez te despiertas a las tres de la mañana y sientes que alguien te está observando fijamente desde la esquina de tu habitación... por favor, nunca abras los ojos.'
  };

  // State
  let currentRawBlob = null;
  let currentDspBlob = null;
  let audioContext = null;

  // --- PWA Installation Setup ---
  let deferredPrompt = null;
  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;
    btnInstall.style.display = 'inline-flex';
  });

  btnInstall.addEventListener('click', async () => {
    if (deferredPrompt) {
      deferredPrompt.prompt();
      const { outcome } = await deferredPrompt.userChoice;
      if (outcome === 'accepted') {
        btnInstall.style.display = 'none';
      }
      deferredPrompt = null;
    }
  });

  // Service Worker Registration
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/sw.js').catch((err) => {
      console.log('SW registration error:', err);
    });
  }

  // --- Text Helpers ---
  scriptText.addEventListener('input', () => {
    charCount.textContent = `${scriptText.value.length} caracteres`;
  });

  btnPaste.addEventListener('click', async () => {
    try {
      const text = await navigator.clipboard.readText();
      if (text) {
        scriptText.value = text;
        charCount.textContent = `${text.length} caracteres`;
      }
    } catch {
      setStatus('No se pudo acceder al portapapeles directamente. Pégalo manualmente.', 'error');
    }
  });

  btnClear.addEventListener('click', () => {
    scriptText.value = '';
    charCount.textContent = '0 caracteres';
  });

  templateButtons.forEach((btn) => {
    btn.addEventListener('click', () => {
      const key = btn.dataset.template;
      if (templates[key]) {
        scriptText.value = templates[key];
        charCount.textContent = `${scriptText.value.length} caracteres`;
      }
    });
  });

  // --- Sliders ---
  speedSlider.addEventListener('input', () => {
    const val = parseInt(speedSlider.value, 10);
    speedVal.textContent = (val > 0 ? `+${val}` : `${val}`) + '%';
  });

  pitchSlider.addEventListener('input', () => {
    const val = parseInt(pitchSlider.value, 10);
    pitchVal.textContent = (val > 0 ? `+${val}` : `${val}`) + 'Hz';
  });

  // --- Status Display ---
  function setStatus(message, type = 'normal') {
    statusBar.className = `status-bar ${type}`;
    if (type === 'loading') {
      statusBar.innerHTML = `<span class="spinner"></span> <span>${message}</span>`;
    } else {
      statusBar.textContent = message;
    }
  }

  // --- Base64 to ArrayBuffer Helper ---
  function base64ToArrayBuffer(base64) {
    const binaryString = window.atob(base64);
    const len = binaryString.length;
    const bytes = new Uint8Array(len);
    for (let i = 0; i < len; i++) {
      bytes[i] = binaryString.charCodeAt(i);
    }
    return bytes.buffer;
  }

  // --- AudioBuffer to WAV Converter ---
  function audioBufferToWav(buffer) {
    const numChannels = buffer.numberOfChannels;
    const sampleRate = buffer.sampleRate;
    const format = 1; // 16-bit PCM
    const bitDepth = 16;
    const bytesPerSample = bitDepth / 8;
    const blockAlign = numChannels * bytesPerSample;
    const length = buffer.length * blockAlign;
    const bufferLength = 44 + length;
    const arrayBuffer = new ArrayBuffer(bufferLength);
    const view = new DataView(arrayBuffer);

    function writeString(offset, string) {
      for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
      }
    }

    // RIFF chunk
    writeString(0, 'RIFF');
    view.setUint32(4, 36 + length, true);
    writeString(8, 'WAVE');

    // fmt sub-chunk
    writeString(12, 'fmt ');
    view.setUint32(16, 16, true);
    view.setUint16(20, format, true);
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, sampleRate * blockAlign, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitDepth, true);

    // data sub-chunk
    writeString(36, 'data');
    view.setUint32(40, length, true);

    // Interleave channels
    let offset = 44;
    const channels = [];
    for (let c = 0; c < numChannels; c++) {
      channels.push(buffer.getChannelData(c));
    }

    for (let i = 0; i < buffer.length; i++) {
      for (let c = 0; c < numChannels; c++) {
        let sample = channels[c][i];
        sample = Math.max(-1, Math.min(1, sample));
        const intSample = sample < 0 ? sample * 0x8000 : sample * 0x7FFF;
        view.setInt16(offset, intSample, true);
        offset += 2;
      }
    }

    return new Blob([view], { type: 'audio/wav' });
  }

  // --- DSP Equalizer via OfflineAudioContext ---
  async function processDsp(rawArrayBuffer, preset) {
    const AudioCtx = window.AudioContext || window.webkitAudioContext;
    if (!audioContext) {
      audioContext = new AudioCtx();
    }
    const decodedBuffer = await audioContext.decodeAudioData(rawArrayBuffer.slice(0));

    if (preset === 'natural') {
      return {
        wavBlob: audioBufferToWav(decodedBuffer),
        buffer: decodedBuffer
      };
    }

    const OfflineCtx = window.OfflineAudioContext || window.webkitOfflineAudioContext;
    const offline = new OfflineCtx(
      decodedBuffer.numberOfChannels,
      decodedBuffer.length,
      decodedBuffer.sampleRate
    );

    const source = offline.createBufferSource();
    source.buffer = decodedBuffer;

    let chain = source;

    if (preset === 'discovery') {
      // Graves de cine profundos
      const lowShelf = offline.createBiquadFilter();
      lowShelf.type = 'lowshelf';
      lowShelf.frequency.value = 120;
      lowShelf.gain.value = 6;

      // Definición vocal
      const peak = offline.createBiquadFilter();
      peak.type = 'peaking';
      peak.frequency.value = 2800;
      peak.gain.value = 2;

      // Brillo y presencia
      const highShelf = offline.createBiquadFilter();
      highShelf.type = 'highshelf';
      highShelf.frequency.value = 8500;
      highShelf.gain.value = 3;

      chain.connect(lowShelf);
      lowShelf.connect(peak);
      peak.connect(highShelf);
      chain = highShelf;
    } else if (preset === 'misterio') {
      // Subgraves masivos
      const lowShelf = offline.createBiquadFilter();
      lowShelf.type = 'lowshelf';
      lowShelf.frequency.value = 90;
      lowShelf.gain.value = 8;

      // Atenuación de agudos para atmósfera oscura
      const highShelf = offline.createBiquadFilter();
      highShelf.type = 'highshelf';
      highShelf.frequency.value = 7000;
      highShelf.gain.value = -3.5;

      chain.connect(lowShelf);
      lowShelf.connect(highShelf);
      chain = highShelf;
    } else if (preset === 'tiktok') {
      // Corte de retumbes graves de teléfono
      const highPass = offline.createBiquadFilter();
      highPass.type = 'highpass';
      highPass.frequency.value = 90;

      // Mordida vocal media
      const peak = offline.createBiquadFilter();
      peak.type = 'peaking';
      peak.frequency.value = 2500;
      peak.gain.value = 4;

      // Ultra claridad
      const highShelf = offline.createBiquadFilter();
      highShelf.type = 'highshelf';
      highShelf.frequency.value = 9000;
      highShelf.gain.value = 4;

      chain.connect(highPass);
      highPass.connect(peak);
      peak.connect(highShelf);
      chain = highShelf;
    } else if (preset === 'radio') {
      const lowShelf = offline.createBiquadFilter();
      lowShelf.type = 'lowshelf';
      lowShelf.frequency.value = 150;
      lowShelf.gain.value = 4;

      const peak = offline.createBiquadFilter();
      peak.type = 'peaking';
      peak.frequency.value = 1200;
      peak.gain.value = 2.5;

      chain.connect(lowShelf);
      lowShelf.connect(peak);
      chain = peak;
    }

    chain.connect(offline.destination);
    source.start(0);

    const rendered = await offline.startRendering();
    const wavBlob = audioBufferToWav(rendered);
    return { wavBlob, buffer: rendered };
  }

  // --- Synthesis Request ---
  async function generateVoice(customText = null) {
    const text = (customText || scriptText.value).trim();
    if (!text) {
      setStatus('Por favor escribe o pega un texto antes de generar.', 'error');
      scriptText.focus();
      return;
    }

    const voice = voiceSelect.value;
    const rate = speedVal.textContent.trim();
    const pitch = pitchVal.textContent.trim();
    const preset = dspPreset.value;

    btnGenerate.disabled = true;
    btnPreview.disabled = true;
    setStatus('Conectando con la nube y sintetizando voz neuronal...', 'loading');

    try {
      let response = await fetch('/api/tts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, voice, rate, pitch })
      });

      if (response.status === 404) {
        response = await fetch('/.netlify/functions/tts', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, voice, rate, pitch })
        });
      }

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.error || `Error del servidor (${response.status})`);
      }

      const data = await response.json();
      if (!data.audio) {
        throw new Error('La respuesta del servidor no contenía audio.');
      }

      setStatus('Procesando masterización de estudio DSP...', 'loading');

      const rawBuffer = base64ToArrayBuffer(data.audio);
      currentRawBlob = new Blob([rawBuffer], { type: 'audio/mp3' });

      // Apply selected DSP equalizer
      const { wavBlob } = await processDsp(rawBuffer, preset);
      currentDspBlob = wavBlob;

      // Update audio player with the DSP mastered version
      const audioUrl = URL.createObjectURL(currentDspBlob);
      audioPlayer.src = audioUrl;
      audioPlayer.play().catch(() => {
        // Autoplay policy fallback
      });

      // Update download links
      const rawUrl = URL.createObjectURL(currentRawBlob);
      btnDownloadRaw.href = rawUrl;
      btnDownloadRaw.download = `narracion_${voice}_raw.mp3`;

      currentVoiceBadge.textContent = `${voice.split('-')[2] || voice} • ${dspPreset.options[dspPreset.selectedIndex].text.split('(')[0].trim()}`;

      playerCard.style.display = 'flex';
      setStatus('¡Voz neuronal masterizada lista para reproducir y descargar!', 'success');
    } catch (err) {
      console.error('Error generating audio:', err);
      setStatus(`Error: ${err.message}`, 'error');
    } finally {
      btnGenerate.disabled = false;
      btnPreview.disabled = false;
    }
  }

  // --- Download DSP Button ---
  btnDownloadDsp.addEventListener('click', () => {
    if (!currentDspBlob) return;
    const url = URL.createObjectURL(currentDspBlob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `narracion_masterizada_dsp_${voiceSelect.value}.wav`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });

  // --- Main Button Listeners ---
  btnGenerate.addEventListener('click', () => {
    generateVoice();
  });

  btnPreview.addEventListener('click', () => {
    const selectedVoiceName = voiceSelect.options[voiceSelect.selectedIndex].text.split('(')[0].trim();
    const sampleText = `Hola, esta es una prueba de la voz neuronal de ${selectedVoiceName} con ecualización de estudio.`;
    generateVoice(sampleText);
  });
});
