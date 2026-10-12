import os
import sys
import re
import math
import asyncio
import tempfile
import subprocess
import urllib.request
import urllib.parse
import json
import io
import shutil
from PIL import Image, ImageDraw, ImageFont, ImageEnhance, ImageFilter
import cv2
import numpy as np
import edge_tts
import edge_tts.constants as edge_constants
import edge_tts.communicate as edge_communicate
import imageio_ffmpeg
from gtts import gTTS
import streamlit as st

# Configuración de página móvil y escritorio
st.set_page_config(
    page_title="ViralSuite AI - Estudio de Voces y Reels",
    page_icon="🎙️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Buscar ejecutable de FFmpeg (Linux Streamlit Cloud o Windows Local)
FFMPEG_EXE = shutil.which("ffmpeg") or imageio_ffmpeg.get_ffmpeg_exe()

# Parche de alta disponibilidad para Microsoft Edge-TTS (Elimina Error 403 en la nube)
edge_constants.BASE_URL = "api.msedgeservices.com/tts/cognitiveservices"
edge_constants.WSS_URL = f"wss://{edge_constants.BASE_URL}/websocket/v1?Ocp-Apim-Subscription-Key={edge_constants.TRUSTED_CLIENT_TOKEN}"
edge_constants.VOICE_LIST = f"https://{edge_constants.BASE_URL}/voices/list?Ocp-Apim-Subscription-Key={edge_constants.TRUSTED_CLIENT_TOKEN}"
edge_communicate.WSS_URL = edge_constants.WSS_URL

def run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                return pool.submit(asyncio.run, coro).result()
        return loop.run_until_complete(coro)
    except RuntimeError:
        return asyncio.run(coro)

# Estilos CSS de cine oscuro y diseño móvil
st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at top, #131b2e 0%, #090d16 100%);
        color: #f0f4f8;
    }
    .main-header {
        background: linear-gradient(90deg, #1e293b 0%, #0f172a 100%);
        padding: 1.4rem;
        border-radius: 16px;
        border: 1px solid rgba(56, 189, 248, 0.25);
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 30px rgba(0,0,0,0.4);
    }
    .main-header h1 {
        margin: 0;
        font-size: 1.8rem;
        background: linear-gradient(90deg, #38bdf8, #818cf8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .main-header p {
        margin: 0.4rem 0 0 0;
        color: #94a3b8;
        font-size: 0.95rem;
    }
    .stButton > button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        padding: 0.65rem 1rem;
        transition: all 0.2s ease;
    }
    .stDownloadButton > button {
        width: 100%;
        border-radius: 12px;
        font-weight: 700;
        background: linear-gradient(90deg, #10b981, #059669) !important;
        color: white !important;
        border: none !important;
        padding: 0.75rem 1rem;
    }
</style>
""", unsafe_allow_html=True)

VOICES_MAP = {
    "MX - México: Jorge (MASCULINO - Grave / Misterio / Documental)": "es-MX-JorgeNeural",
    "MX - México: Dalia (FEMENINO - Historia / Documental Expresivo)": "es-MX-DaliaNeural",
    "CO - Colombia: Gonzalo (MASCULINO - Discovery / Reportaje)": "es-CO-GonzaloNeural",
    "CO - Colombia: Salomé (FEMENINO - Documental Claro)": "es-CO-SalomeNeural",
    "US - EE.UU. Latino: Alonso (MASCULINO - Cine / Tráiler / Impacto)": "es-US-AlonsoNeural",
    "US - EE.UU. Latino: Paloma (FEMENINO - Dinámico Latino)": "es-US-PalomaNeural",
    "AR - Argentina: Tomás (MASCULINO - Enérgico / Reportaje)": "es-AR-TomasNeural",
    "AR - Argentina: Elena (FEMENINO - Expresiva Latinoamérica)": "es-AR-ElenaNeural",
    "CL - Chile: Lorenzo (MASCULINO - Sobrio Documental)": "es-CL-LorenzoNeural",
    "CL - Chile: Catalina (FEMENINO - Voz Narrativa Docu-Series)": "es-CL-CatalinaNeural",
    "PE - Perú: Alex (MASCULINO - Documental Claro)": "es-PE-AlexNeural",
    "PE - Perú: Camila (FEMENINO - Suave Documental)": "es-PE-CamilaNeural",
    "VE - Venezuela: Sebastián (MASCULINO - Narración Reportaje)": "es-VE-SebastianNeural",
    "VE - Venezuela: Paola (FEMENINO - Documental Cultura)": "es-VE-PaolaNeural",
    "EC - Ecuador: Luis (MASCULINO - Voz Narrativa Sobria)": "es-EC-LuisNeural",
    "EC - Ecuador: Andrea (FEMENINO - Documental Claro)": "es-EC-AndreaNeural",
    "UY - Uruguay: Mateo (MASCULINO - Narración Latino Sur)": "es-UY-MateoNeural",
    "GT - Guatemala: Andrés (MASCULINO - Narración Centro)": "es-GT-AndresNeural",
    "DO - Rep. Dominicana: Emilio (MASCULINO - Narración Caribe)": "es-DO-EmilioNeural",
    "ES - España: Álvaro (MASCULINO - Cinematográfico Clásico)": "es-ES-AlvaroNeural",
    "ES - España: Elvira (FEMENINO - Documental Naturaleza)": "es-ES-ElviraNeural",
    "US - EE.UU. Inglés: Christopher (MASCULINO - Tráiler Cine Profundo)": "en-US-ChristopherNeural"
}

DOCUMENTARY_EFFECTS_DSP = {
    "🎬 Documental History / Discovery (Grave Profundo + Ecualizador de Estudio)": (
        "equalizer=f=100:width_type=h:width=100:g=6,equalizer=f=3000:width_type=h:width=1000:g=2,asetrate=24000*0.94,atempo=1.0638"
    ),
    "🌌 Misterio Abisal / Espacio (Tono Súper Grave Abisal)": (
        "equalizer=f=80:width_type=h:width=80:g=9,asetrate=24000*0.87,atempo=1.149"
    ),
    "🐾 Documental Naturaleza / National Geo (Tono Cálido & Pausado)": (
        "equalizer=f=200:width_type=h:width=150:g=4,asetrate=24000*0.97,atempo=0.98"
    ),
    "⚡ Reportaje / Noticias de Impacto (Agudos Brillos & Ritmo Rápido)": (
        "equalizer=f=2500:width_type=h:width=500:g=4,atempo=1.10"
    ),
    "🎙️ Voz Natural (Sin Procesar / Tono Original)": (
        "anull"
    )
}

BUILTIN_SCRIPTS = {
    "La araña violinista": (
        "Oculta en la penumbra de roperos, grietas y rincones olvidados de nuestros propios hogares, "
        "acecha uno de los arácnidos más letales y silenciosos del continente: la araña violinista. "
        "De aspecto frágil y tímido, posee una marca en el lomo en forma de violín que delata su temible identidad. "
        "Su veneno es quince veces más tóxico que el de una serpiente de cascabel y tiene un efecto devastador: "
        "disuelve los tejidos de la piel mediante enzimas necrosantes que provocan gangrena celular en cuestión de horas. "
        "En los casos más severos, sus toxinas invaden el torrente sanguíneo, comprometiendo los riñones y amenazando la vida humana. "
        "La mayoría de las personas son mordidas mientras duermen o al ponerse ropa que estuvo guardada por meses, sin sentir dolor en el instante. "
        "¿Has revisado detrás de tus muebles hoy para asegurarte de no dormir con una de ellas?"
    ),
    "El Triángulo de las Bermudas": (
        "En medio del Océano Atlántico se encuentra uno de los misterios más desconcertantes de la historia moderna: "
        "el Triángulo de las Bermudas. Durante más de un siglo, decenas de barcos colosales y aviones militares han desaparecido "
        "sin dejar una sola mancha de aceite o llamada de auxilio. "
        "En 1945, cinco bombarderos navales despegaron en una misión rutinaria... y jamás regresaron. "
        "Cuando un hidroavión de rescate salió en su búsqueda con trece hombres a bordo, también se desvaneció en el aire en cuestión de minutos. "
        "Científicos e investigadores han propuesto teorías como anomalías magnéticas que desorientan las brújulas o bolsas de gas metano que hunden navíos al instante. "
        "Sin embargo, el fondo marino de esta zona abisal sigue guardando secretos que nadie ha podido desentrañar. "
        "¿Crees que se trata de simple mala suerte climática... o de algo que la ciencia todavía no comprende?"
    ),
    "El Pozo de Kola": (
        "En la gélida tundra de Rusia, científicos pasaron más de veinte años perforando la corteza terrestre "
        "con una sola misión: llegar lo más profundo posible hacia el centro del planeta. "
        "El resultado fue el Pozo Superprofundo de Kola, un agujero de más de doce kilómetros de profundidad donde la roca arde a casi doscientos grados. "
        "A esa profundidad, la presión es tan aplastante que la roca se comporta como plástico derretido. "
        "Pero lo más impactante ocurrió cuando los ingenieros bajaron micrófonos térmicos resistentes al calor para registrar el movimiento de las placas... "
        "Las grabaciones captaron sonidos de baja frecuencia tan perturbadores y parecidos a voces humanas que muchos de los trabajadores se negaron a continuar. "
        "El pozo fue sellado con una placa de acero soldada que sigue ahí hasta el día de hoy. "
        "¿Te atreverías a desenterrar lo que dejaron encerrado en las profundidades?"
    ),
    "La Fosa de las Marianas": (
        "A casi once mil metros bajo la superficie del océano se encuentra el lugar más inhóspito, oscuro y aterrador del planeta: "
        "la Fosa de las Marianas. Si pusieras el Monte Everest en su fondo, su cima aún quedaría sumergida bajo más de dos kilómetros de agua. "
        "A esta profundidad, la luz del sol jamás ha llegado y la presión equivale a cincuenta aviones comerciales aplastando cada centímetro. "
        "Sin embargo, en esta oscuridad abisal habitan criaturas translúcidas y bioluminiscentes que desafían toda explicación biológica. "
        "¿Qué otros secretos crees que siguen ocultos en el fondo del océano?"
    )
}

def clean_text_for_tts(raw_text):
    if not raw_text:
        return ""
    cleaned = re.sub(r'https?://\S+|www\.\S+|\b[a-zA-Z0-9.-]+\.[a-z]{2,}\b', '', raw_text)
    cleaned = re.sub(r'\+\d+', '', cleaned)
    cleaned = re.sub(r'\s*\.\s*', '. ', cleaned)
    cleaned = re.sub(r'\s+', ' ', cleaned).strip()
    return cleaned

def apply_dsp_filter(input_mp3, af_pipeline):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        output_mp3 = fp.name
    cmd = [FFMPEG_EXE, "-y", "-i", input_mp3, "-af", af_pipeline, "-b:a", "192k", output_mp3]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return output_mp3

async def _synthesize_edge_task(clean_text, voice_code, raw_path, rate="+0%", pitch="+0Hz"):
    communicate = edge_tts.Communicate(clean_text, voice=voice_code, rate=rate, pitch=pitch)
    await communicate.save(raw_path)

def generate_raw_tts(text, voice_code, rate="+0%", pitch="+0Hz"):
    clean_text = clean_text_for_tts(text)
    if not clean_text:
        raise ValueError("El texto está vacío.")
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        raw_path = fp.name

    try:
        run_async(_synthesize_edge_task(clean_text, voice_code, raw_path, rate=rate, pitch=pitch))
    except Exception as e:
        tts = gTTS(text=clean_text, lang="es", tld="com.mx")
        tts.save(raw_path)

    return raw_path

def load_subtitle_font(size=48):
    font_candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "arialbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
    ]
    for path in font_candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()

def make_cinematic_9_16(im, w=1080, h=1920):
    try:
        iw, ih = im.size
        scale_bg = max(w / iw, h / ih)
        bg_w, bg_h = int(iw * scale_bg), int(ih * scale_bg)
        bg = im.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
        left = max(0, (bg_w - w) // 2)
        top = max(0, (bg_h - h) // 2)
        bg = bg.crop((left, top, left + w, top + h))
        bg = bg.filter(ImageFilter.GaussianBlur(radius=28))
        bg = ImageEnhance.Brightness(bg).enhance(0.40)

        scale_fg = min(w / iw, (h * 0.72) / ih)
        fg_w, fg_h = int(iw * scale_fg), int(ih * scale_fg)
        fg = im.resize((fg_w, fg_h), Image.Resampling.LANCZOS)

        fg_x = (w - fg_w) // 2
        fg_y = (h - fg_h) // 2
        bg.paste(fg, (fg_x, fg_y))
        return bg
    except Exception:
        return im.resize((w, h), Image.Resampling.BILINEAR)

def fetch_topic_images_online(topic, max_imgs=4):
    urls = []
    loaded_imgs = []
    try:
        search_url = f"https://es.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(topic)}&gsrlimit=12&prop=pageimages&format=json&pithumbsize=1080"
        req = urllib.request.Request(search_url, headers={'User-Agent': 'ViralSuite/3.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        pages = data.get('query', {}).get('pages', {})
        for p in pages.values():
            if 'thumbnail' in p and len(urls) < max_imgs:
                u = p['thumbnail']['source']
                if not u.endswith('.svg') and not u.endswith('.svg.png'):
                    urls.append(u)
    except Exception:
        pass

    if len(urls) < 2:
        try:
            search_url_en = f"https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch={urllib.parse.quote(topic)}&gsrlimit=10&prop=pageimages&format=json&pithumbsize=1080"
            req = urllib.request.Request(search_url_en, headers={'User-Agent': 'ViralSuite/3.0'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode())
            pages = data.get('query', {}).get('pages', {})
            for p in pages.values():
                if 'thumbnail' in p and len(urls) < max_imgs:
                    u = p['thumbnail']['source']
                    if not u.endswith('.svg') and not u.endswith('.svg.png') and u not in urls:
                        urls.append(u)
        except Exception:
            pass

    for img_url in urls:
        try:
            img_req = urllib.request.Request(img_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(img_req, timeout=6) as img_resp:
                img_bytes = img_resp.read()
            im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
            loaded_imgs.append(im)
        except Exception:
            pass
    return loaded_imgs

def fetch_wiki_smart_script(topic):
    summary = ""
    try:
        search_url = f"https://es.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(topic)}&srlimit=1&format=json"
        req = urllib.request.Request(search_url, headers={'User-Agent': 'ViralSuite/3.0'})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = json.loads(resp.read().decode())
        results = data.get('query', {}).get('search', [])
        if results:
            page_title = results[0]['title']
            sum_url = f"https://es.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(page_title)}"
            req2 = urllib.request.Request(sum_url, headers={'User-Agent': 'ViralSuite/3.0'})
            with urllib.request.urlopen(req2, timeout=5) as resp2:
                sdata = json.loads(resp2.read().decode())
            summary = sdata.get('extract', '')
            summary = re.sub(r'\[.*?\]', '', summary)
    except Exception:
        pass

    if summary and len(summary) > 60:
        return (
            f"Existe un misterio fascinante y peligroso alrededor de {topic}. "
            f"{summary} "
            f"Durante años, investigadores y testigos han documentado casos y fenómenos que desafían todo lo que creíamos saber. "
            f"Muchos ignoran los verdaderos peligros y secretos que oculta, hasta que es demasiado tarde para reaccionar. "
            f"¿Conocías estos impactantes datos o alguna vez has tenido una experiencia con esto? Deja tu respuesta en los comentarios."
        )
    return None

def split_into_subtitles(script_text):
    sentences = re.split(r'(?<=[.?!])\s+', script_text)
    subs = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        words = s.split()
        chunk_size = 4
        for i in range(0, len(words), chunk_size):
            chunk = " ".join(words[i:i + chunk_size])
            if chunk:
                subs.append(chunk)
    return subs

def render_final_video_multiscene(script_text, voice_code, topic_name, uploaded_files):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as fp_out:
        output_video_path = fp_out.name
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp_Final:
        final_audio_path = fp_Final.name

    raw_audio_path = generate_raw_tts(script_text, voice_code, rate="-3%", pitch="-1Hz")

    cmd_eq = [
        FFMPEG_EXE, "-y", "-i", raw_audio_path,
        "-af", "equalizer=f=100:width_type=h:width=100:g=6,equalizer=f=3000:width_type=h:width=1000:g=2,volume=1.2",
        "-b:a", "192k", final_audio_path
    ]
    subprocess.run(cmd_eq, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    cmd_d = [FFMPEG_EXE, "-i", final_audio_path]
    res_d = subprocess.run(cmd_d, stderr=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    duration = 60.0
    for line in res_d.stderr.split("\n"):
        if "Duration" in line:
            time_str = line.split("Duration:")[1].split(",")[0].strip()
            h_t, m_t, s_t = time_str.split(":")
            duration = float(h_t)*3600 + float(m_t)*60 + float(s_t)
            break

    fps = 24
    total_frames = int(duration * fps)
    w, h = 1080, 1920

    loaded_imgs = []
    if uploaded_files:
        for uf in uploaded_files:
            try:
                im = Image.open(uf).convert("RGB")
                loaded_imgs.append(make_cinematic_9_16(im, w, h))
            except Exception:
                pass

    if not loaded_imgs:
        online_imgs = fetch_topic_images_online(topic_name, max_imgs=4)
        for im in online_imgs:
            loaded_imgs.append(make_cinematic_9_16(im, w, h))

    if not loaded_imgs:
        fallback = Image.new("RGB", (w, h), (15, 22, 38))
        loaded_imgs = [fallback]

    num_scenes = len(loaded_imgs)
    frames_per_scene = max(1, total_frames / num_scenes)

    font_main = load_subtitle_font(46)
    subtitles = split_into_subtitles(script_text)
    if not subtitles:
        subtitles = [topic_name]
    num_subs = len(subtitles)
    frames_per_sub = max(1, total_frames / num_subs)

    gradient = Image.new("RGBA", (w, 550), (0, 0, 0, 0))
    g_draw = ImageDraw.Draw(gradient)
    for y in range(550):
        alpha = int(220 * (y / 550))
        g_draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    subtitle_overlays = []
    for phrase in subtitles:
        ov = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        ov.paste(gradient, (0, h - 550), gradient)
        draw = ImageDraw.Draw(ov)

        tb = draw.textbbox((0, 0), phrase, font=font_main, stroke_width=3)
        text_w = tb[2] - tb[0]
        text_h = tb[3] - tb[1]
        text_x = (w - text_w) // 2
        box_y = h - 380

        pad_x = 32
        pad_y = 18
        draw.rounded_rectangle(
            [text_x - pad_x, box_y - pad_y, text_x + text_w + pad_x, box_y + text_h + pad_y],
            radius=24, fill=(10, 15, 25, 205), outline=(255, 255, 255, 50), width=2
        )
        draw.text(
            (text_x, box_y), phrase, font=font_main, fill=(255, 255, 255, 255),
            stroke_width=3, stroke_fill=(0, 0, 0, 240)
        )
        subtitle_overlays.append(ov)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as fp_temp:
        temp_video = fp_temp.name

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    writer = cv2.VideoWriter(temp_video, fourcc, fps, (w, h))

    for frame_idx in range(total_frames):
        scene_idx = min(num_scenes - 1, int(frame_idx // frames_per_scene))
        base_img = loaded_imgs[scene_idx]

        scene_progress = (frame_idx % frames_per_scene) / frames_per_scene
        zoom = 1.0 + 0.12 * math.sin(scene_progress * math.pi)

        zw = int(w * zoom)
        zh = int(h * zoom)
        img_zoomed = base_img.resize((zw, zh), Image.Resampling.BILINEAR)

        crop_x = (zw - w) // 2
        crop_y = (zh - h) // 2
        frame_img = img_zoomed.crop((crop_x, crop_y, crop_x + w, crop_y + h)).convert("RGBA")

        sub_idx = min(len(subtitle_overlays) - 1, int(frame_idx // frames_per_sub))
        frame_img.alpha_composite(subtitle_overlays[sub_idx])

        frame_np = np.array(frame_img.convert("RGB"))
        frame_bgr = cv2.cvtColor(frame_np, cv2.COLOR_RGB2BGR)
        writer.write(frame_bgr)

    writer.release()

    cmd_mux = [
        FFMPEG_EXE, "-y", "-i", temp_video, "-i", final_audio_path,
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k", "-shortest", output_video_path
    ]
    subprocess.run(cmd_mux, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    for p in [raw_audio_path, final_audio_path, temp_video]:
        try:
            os.remove(p)
        except Exception:
            pass

    return output_video_path, duration

# Encabezado Principal
st.markdown("""
<div class="main-header">
    <h1>🎙️ ViralSuite AI — Estudio en la Nube 24/7</h1>
    <p>Generador de Voces Neurales de Cine & Creador Automático de Videos Reels 9:16 (Sin depender de tu PC)</p>
</div>
""", unsafe_allow_html=True)

tab_voz, tab_video = st.tabs([
    "🎙️ 1. Estudio de Voces Neurales",
    "🎬 2. Creador de Videos Reels (> 1 Minuto)"
])

with tab_voz:
    col1, col2 = st.columns([1.2, 1])

    with col1:
        st.subheader("📝 Guion para Locución")
        if "voice_script" not in st.session_state:
            st.session_state.voice_script = BUILTIN_SCRIPTS["La Fosa de las Marianas"]

        st.caption("💡 Ideas rápidas (toca una para cargar):")
        q_cols = st.columns(4)
        for idx, (title, content) in enumerate(BUILTIN_SCRIPTS.items()):
            if q_cols[idx % 4].button(title, key=f"q_{idx}"):
                st.session_state.voice_script = content

        script_input = st.text_area(
            "Escribe o pega tu guion aquí:",
            value=st.session_state.voice_script,
            height=180
        )

        selected_voice_label = st.selectbox(
            "🗣️ Locutor / Voz Neuronal Latinoamericana:",
            options=list(VOICES_MAP.keys()),
            index=0
        )

        selected_effect = st.selectbox(
            "🎛️ Masterización / Efecto de Estudio (DSP):",
            options=list(DOCUMENTARY_EFFECTS_DSP.keys()),
            index=0
        )

        c_rate, c_pitch = st.columns(2)
        rate_val = c_rate.slider("⚡ Velocidad (%)", min_value=-25, max_value=25, value=-3, step=1)
        pitch_val = c_pitch.slider("🎵 Tono / Pitch (Hz)", min_value=-15, max_value=15, value=-1, step=1)

        btn_col1, btn_col2 = st.columns(2)
        preview_clicked = btn_col1.button("🎧 Probar Muestra Rápida")
        generate_clicked = btn_col2.button("✨ GENERAR AUDIO COMPLETO", type="primary")

    with col2:
        st.subheader("🔊 Reproductor y Descarga Directa")
        rate_str = f"{rate_val:+d}%"
        pitch_str = f"{pitch_val:+d}Hz"
        voice_code = VOICES_MAP[selected_voice_label]
        af_pipeline = DOCUMENTARY_EFFECTS_DSP[selected_effect]

        if preview_clicked:
            with st.spinner("Generando muestra de estudio..."):
                try:
                    sample_txt = f"Hola, esta es una prueba de estudio con la voz de {selected_voice_label.split(':')[1].split('(')[0].strip()}."
                    raw_mp3 = generate_raw_tts(sample_txt, voice_code, rate=rate_str, pitch=pitch_str)
                    final_mp3 = apply_dsp_filter(raw_mp3, af_pipeline)
                    with open(final_mp3, "rb") as f:
                        audio_bytes = f.read()
                    st.success(f"✅ Muestra lista: **{voice_code}**")
                    st.audio(audio_bytes, format="audio/mp3")
                    st.download_button(
                        label="⬇️ Descargar Muestra MP3",
                        data=audio_bytes,
                        file_name=f"muestra_{voice_code}.mp3",
                        mime="audio/mpeg"
                    )
                except Exception as e:
                    st.error(f"Error generando muestra: {e}")

        if generate_clicked:
            if not script_input.strip():
                st.warning("⚠️ Escribe un guion primero.")
            else:
                with st.spinner("🎙️ Sintetizando voz neuronal y aplicando ecualización de cine..."):
                    try:
                        raw_mp3 = generate_raw_tts(script_input, voice_code, rate=rate_str, pitch=pitch_str)
                        final_mp3 = apply_dsp_filter(raw_mp3, af_pipeline)
                        with open(final_mp3, "rb") as f:
                            audio_bytes = f.read()
                        st.success(f"✅ ¡Locución completada con éxito! ({voice_code})")
                        st.audio(audio_bytes, format="audio/mp3")
                        st.download_button(
                            label="⬇️ DESCARGAR AUDIO MP3 EN ALTA CALIDAD",
                            data=audio_bytes,
                            file_name=f"locucion_{voice_code}.mp3",
                            mime="audio/mpeg"
                        )
                    except Exception as e:
                        st.error(f"Error generando voz: {e}")

with tab_video:
    v_col1, v_col2 = st.columns([1.1, 1])

    with v_col1:
        st.subheader("🎬 Configuración del Video Reel 9:16")
        preset_topic = st.selectbox(
            "📌 Elige una plantilla o selecciona 'Escribir mi propio tema':",
            options=["Escribir mi propio tema..."] + list(BUILTIN_SCRIPTS.keys()),
            index=1
        )

        if preset_topic == "Escribir mi propio tema...":
            topic_input = st.text_input("Escribe el tema del video (la IA buscará fotos reales):", value="El Misterio de la Atlántida")
            default_reel_script = ""
        else:
            topic_input = preset_topic
            default_reel_script = BUILTIN_SCRIPTS[preset_topic]

        custom_reel_script = st.text_area(
            "📝 Guion del Video (Puedes editarlo o dejarlo vacío para autogenerar):",
            value=default_reel_script,
            height=150
        )

        uploaded_imgs = st.file_uploader(
            "🖼️ Sube tus propias fotos para las escenas (Opcional - Si lo dejas vacío descarga fotos automáticamente):",
            type=["jpg", "jpeg", "png", "webp"],
            accept_multiple_files=True
        )

        reel_voice_label = st.selectbox(
            "🗣️ Voz para narrar el Reel:",
            options=list(VOICES_MAP.keys())[:8],
            index=0,
            key="reel_voice"
        )

        gen_video_btn = st.button("🎬 GENERAR VIDEO REEL 9:16 COMPLETO", type="primary")

    with v_col2:
        st.subheader("📱 Resultado del Video Reel")
        if gen_video_btn:
            with st.spinner("⏳ Generando locución, descargando escenas, aplicando subtítulos blancos y renderizando MP4 (toma ~40 seg)..."):
                try:
                    final_script = custom_reel_script.strip()
                    if not final_script:
                        wiki_s = fetch_wiki_smart_script(topic_input)
                        final_script = wiki_s if wiki_s else BUILTIN_SCRIPTS["La araña violinista"]

                    r_voice_code = VOICES_MAP[reel_voice_label]
                    video_path, dur = render_final_video_multiscene(
                        final_script, r_voice_code, topic_input, uploaded_imgs
                    )
                    with open(video_path, "rb") as vf:
                        video_bytes = vf.read()

                    st.success(f"✅ ¡Video Reel 9:16 Renderizado! Duración: **{dur:.1f} segundos**")
                    st.video(video_bytes)
                    st.download_button(
                        label="⬇️ DESCARGAR VIDEO REEL (.MP4)",
                        data=video_bytes,
                        file_name=f"reel_{re.sub(r'[^a-zA-Z0-9]', '_', topic_input.lower())}.mp4",
                        mime="video/mp4"
                    )
                except Exception as e:
                    st.error(f"Error renderizando video: {e}")
