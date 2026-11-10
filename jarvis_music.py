"""J.A.R.V.I.S Music Reactor - Mark X (Robot Face)
Cute robot-face HUD whose expressions follow your commands, the song about to play and the song playing.
Set JARVIS_HUD=classic to get the old arc-reactor HUD back."""
import asyncio, collections, hashlib, html, json, math, os, queue, random, re
import subprocess, sys, tempfile, threading, time, urllib.request, urllib.error
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QTimer, Signal, QObject, QSettings, QUrl, QPointF, QRectF
from PySide6.QtGui import (QColor, QFont, QPainter, QPen, QBrush, QLinearGradient,
                           QRadialGradient, QPainterPath, QPixmap, QPolygonF)
from PySide6.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
                               QLineEdit, QFileDialog, QTextEdit, QFrame, QSlider, QListWidget,
                               QListWidgetItem, QComboBox, QProgressBar)
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent   # folder next to the .exe
sys.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from robotface import FaceReactor, FACE_NAMES, INTENT_FACE, analyze_track, mood_from_text
except Exception as _face_err:          # robotface folder missing/broken -> classic HUD still works
    FaceReactor, FACE_NAMES, INTENT_FACE, _FACE_ERR = None, [], {}, _face_err
    analyze_track = lambda pcm, rate: None
    mood_from_text = lambda text: ('Happy', 3.0)
else:
    _FACE_ERR = None

EXTENSIONS = {'.mp3', '.wav', '.flac', '.ogg', '.m4a', '.aac', '.wma', '.opus'}
PITCH = -2   # Hz; a light touch. The old -12Hz made the voice sound synthetic.

THEMES = {
    'ARC':     dict(a='#24e4ff', b='#ffb35c', bg='#030a14', panel='#082033', text='#d2f6ff', dim='#6fb0c4'),
    'GOLD':    dict(a='#ffc24a', b='#ff5b3a', bg='#0f0803', panel='#231606', text='#fff0d2', dim='#c49a5c'),
    'CRIMSON': dict(a='#ff3d5e', b='#ffb35c', bg='#12040a', panel='#2a0a14', text='#ffdbe2', dim='#c4707f'),
    'VIOLET':  dict(a='#b57cff', b='#3de6ff', bg='#0a0514', panel='#1a0e30', text='#eadcff', dim='#9a82c4'),
    'EMERALD': dict(a='#3dffa8', b='#e6ff5c', bg='#031009', panel='#072419', text='#d6ffec', dim='#6fc49a'),
}
THEME_ALIASES = {'arc': 'ARC', 'blue': 'ARC', 'cyan': 'ARC', 'gold': 'GOLD', 'stark': 'GOLD', 'yellow': 'GOLD',
                 'crimson': 'CRIMSON', 'red': 'CRIMSON', 'violet': 'VIOLET', 'purple': 'VIOLET',
                 'emerald': 'EMERALD', 'green': 'EMERALD'}
T = dict(THEMES['ARC'])

# 'voice|fx' - fx is applied after synthesis (ffmpeg): 'cute' = squeaky pitch-up, 'robot' = pitch-up + robotic buzz
VOICES = [('Bubbles - very cute & soft (default)', 'en-US-AnaNeural|kawaii'),
          ('Softie - gentle cute girl', 'en-US-AnaNeural|soft'),
          ('Pixel - cute with tiny robot chirp', 'en-US-AnaNeural|chirp'),
          ('Sparkle - soft cute (Ava)', 'en-US-AvaMultilingualNeural|kawaii'),
          ('Tiny - soft cute (Indian English)', 'en-IN-NeerjaNeural|kawaii'),
          ('Bubbles - robot buzz', 'en-US-AnaNeural|robot'),
          ('Ryan - British male (classic JARVIS)', 'en-GB-RyanNeural'),
          ('Thomas - British male', 'en-GB-ThomasNeural'),
          ('Andrew - US male, warm', 'en-US-AndrewMultilingualNeural'),
          ('Brian - US male, calm', 'en-US-BrianMultilingualNeural'),
          ('William - Australian male', 'en-AU-WilliamMultilingualNeural'),
          ('Prabhat - Indian English male', 'en-IN-PrabhatNeural'),
          ('Sonia - British female', 'en-GB-SoniaNeural'),
          ('Ava - US female', 'en-US-AvaMultilingualNeural'),
          ('Neerja - Indian English female', 'en-IN-NeerjaNeural')]

LINES = {
    'play': ["Certainly, {s}. Playing", "Right away, {s}. Here's", "Of course, {s}. Now playing", "Good choice, {s}. This is"],
    'next': ["Up next", "Next up", "Moving on to"],
    'wake': ["Yes, {s}?", "At your service.", "I'm listening.", "Go ahead, {s}."],
    'pause': ["Paused.", "Holding the music for you.", "Music paused, {s}."],
    'resume': ["Back to the music.", "Resuming.", "Picking up where we left off."],
    'stop': ["Stopping the music.", "Music stopped, {s}.", "Silence it is."],
    'thanks': ["My pleasure, {s}.", "Anytime.", "Happy to help, {s}."],
    'hello': ["Hello, {s}. Ready when you are.", "Good to hear you, {s}.", "Hello there. What shall we listen to?"],
    'howru': ["All systems are running smoothly, {s}. Thank you for asking.", "Running at full capacity, and ready for some music."],
    'help': ["I can play any track in your library. Just say play, followed by the name. I can also pause, skip, change the volume, shuffle, or switch my display theme."],
    'nomatch': ["I couldn't find that one in your library, {s}.", "Hmm, I don't see anything close to that. Could you say it again?", "I'm afraid there's no close match for that title."],
    'unknown': ["I didn't quite catch that, {s}. You can ask me to play a song, or control the music.", "Sorry, {s}. Could you rephrase that?"],
    'empty': ["Your library looks empty, {s}. Please choose a music folder."],
    'shuf_on': ["Shuffle is on.", "Shuffling your library, {s}."], 'shuf_off': ["Shuffle is off.", "Back to playing in order."],
    'rep_on': ["I'll keep this track on repeat."], 'rep_off': ["Repeat is off."],
    'mute': ["Muted."], 'unmute': ["Sound restored."],
    'vol': ["Volume at {n} percent.", "Setting the volume to {n} percent, {s}."],
    'test': ["Good to see you again, {s}. How does this sound?"],
}

# ----------------------------------------------------------------------------- helpers
def col(key, alpha=255):
    c = QColor(T[key]); c.setAlpha(alpha); return c

def mix(c1, c2, t):
    t = max(0.0, min(1.0, t))
    return QColor(*(int(a + (b - a) * t) for a, b in ((c1.red(), c2.red()), (c1.green(), c2.green()), (c1.blue(), c2.blue()))))

def font(px, bold=False, mono=False, spacing=0.0):
    f = QFont(); f.setFamilies(['Consolas', 'Courier New'] if mono else ['Bahnschrift', 'Segoe UI', 'Arial'])
    f.setPixelSize(int(max(8, px))); f.setBold(bold)
    if spacing: f.setLetterSpacing(QFont.AbsoluteSpacing, spacing)
    return f

def normalize(s):
    return re.sub(r'[^\w]+', ' ', s.casefold()).strip()

def clean_title(raw):
    t = re.sub(r'_+', ' ', str(raw))
    t = re.sub(r'\[[^]]*\]', ' ', t)
    t = re.sub(r'\([^)]*(?:kbps|official|lyric|audio|download|video|remaster|hd|hq)[^)]*\)', ' ', t, flags=re.I)
    t = re.sub(r'(?i)\b(?:320 ?kbps|128 ?kbps|official audio|official video|lyrical video|full song|lyrics video|mp3|hq audio|hd audio)\b', ' ', t)
    t = re.sub(r'(?i)\s*[-|]\s*(?:official|lyrics|lyrical|audio|video|320|128|hq|hd).*$', '', t)
    return re.sub(r'\s+', ' ', t).strip(' -_.') or 'this track'

def fmt_time(ms):
    s = max(0, int(ms // 1000)); return f'{s // 60}:{s % 60:02d}'

FX_CHAINS = {
    # very cute + soft: strong pitch-up, harsh highs rolled off, tiny wobble, gentle level
    'kawaii': 'aresample=24000,asetrate=34800,aresample=24000,atempo=0.6897,highpass=f=220,lowpass=f=7000,treble=g=-3,vibrato=f=5.5:d=0.08,volume=1.1',
    'soft': 'aresample=24000,asetrate=31800,aresample=24000,atempo=0.7547,highpass=f=200,lowpass=f=6500,treble=g=-4,vibrato=f=4.5:d=0.05,volume=1.05',
    'chirp': ("aresample=24000,asetrate=33600,aresample=24000,atempo=0.7143,"
              "afftfilt=real='hypot(re,im)*cos(0)':imag='hypot(re,im)*sin(0)':win_size=256:overlap=0.75,"
              "highpass=f=250,lowpass=f=6500,treble=g=-2,volume=1.3"),
    'cute': 'aresample=24000,asetrate=30000,aresample=24000,atempo=0.8,highpass=f=150,volume=1.2',
    'robot': ("aresample=24000,asetrate=29000,aresample=24000,atempo=0.8276,"
              "afftfilt=real='hypot(re,im)*cos(0)':imag='hypot(re,im)*sin(0)':win_size=512:overlap=0.75,"
              "highpass=f=180,treble=g=3,volume=1.5"),
}

def apply_fx(src, dst, fx):
    import imageio_ffmpeg
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-y', '-v', 'error', '-nostdin', '-i', str(src), '-af', FX_CHAINS[fx], '-ar', '24000', '-b:a', '64k', str(dst)]
    r = subprocess.run(cmd, capture_output=True, timeout=120, creationflags=0x08000000 if os.name == 'nt' else 0)
    if r.returncode: raise RuntimeError(r.stderr.decode(errors='replace')[-300:])

def ffmpeg_pcm(path, rate, seconds=None):
    import imageio_ffmpeg
    cmd = [imageio_ffmpeg.get_ffmpeg_exe(), '-v', 'error', '-nostdin']
    if seconds: cmd += ['-t', str(seconds)]
    cmd += ['-i', str(path), '-map', '0:a:0', '-ac', '1', '-ar', str(rate), '-f', 's16le', '-']
    r = subprocess.run(cmd, capture_output=True, timeout=180, creationflags=0x08000000 if os.name == 'nt' else 0)
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors='replace')[-300:])
    return np.frombuffer(r.stdout, dtype='<i2').copy()

# ----------------------------------------------------------------------------- language
WAKE_WORDS = {'jarvis', 'jervis', 'jarvas', 'jarvus', 'jarviz', 'harvis', 'charvis', 'garvis', 'jarves', 'jarvice', 'jarviss'}

def _wake_end(text):
    for k, m in enumerate(list(re.finditer(r"[A-Za-z']+", text))[:5]):
        w = re.sub(r"'s$", '', m.group().lower())
        if w in WAKE_WORDS or SequenceMatcher(None, w, 'jarvis').ratio() >= .8:
            return m.end()
    return None

def has_wake(text):
    return _wake_end(text) is not None

def strip_wake(text):
    for k, m in enumerate(list(re.finditer(r"[A-Za-z']+", text))[:5]):
        w = re.sub(r"'s$", '', m.group().lower())
        if w in WAKE_WORDS or SequenceMatcher(None, w, 'jarvis').ratio() >= .8:
            before = re.sub(r'^\W*(?:hey|hi|ok|okay|yo)\W*$', '', text[:m.start()], flags=re.I)
            return (before + ' ' + text[m.end():]).strip(' ,.!?:;-')
    return text.strip()

def parse_intent(text):
    """Turn a natural sentence into (intent, argument)."""
    c = strip_wake(text).lower()
    c = re.sub(r"\b(please|sir|boss|for me|kindly|jarvis)\b", ' ', c)
    c = re.sub(r"\b(can|could|would|will) you\b", ' ', c)
    c = re.sub(r'\s+', ' ', c).strip(' .,!?')
    if not c: return 'wake', None
    m = re.match(r"(?:play|put on|start|queue up|queue|listen to|i want to hear|i wanna hear)\b\s*(.*)", c)
    if m:
        q = m.group(1).strip()
        if re.fullmatch(r'(?:the )?(?:next|following)(?: song| track| one)?', q): return 'next', None
        if re.fullmatch(r'(?:the )?(?:previous|last|prior)(?: song| track| one)?', q): return 'prev', None
        if q == '': return 'resume', None
        if q in ('music', 'something', 'a song', 'some music', 'anything', 'random', 'a random song', 'something else'): return 'play_any', None
        q = re.sub(r'^(?:the\s+)?(?:song\s+|track\s+)?(?:named\s+|called\s+)?(?:the\s+)?', '', q).strip()
        return 'play', q
    R = lambda p: re.search(p, c)
    if R(r'\b(thank|thanks|cheers)\b'): return 'thanks', None
    if R(r"^(hello|hi|hey|good (morning|afternoon|evening|night))\b") and len(c.split()) < 4: return 'hello', None
    if R(r"how are you|how's it going"): return 'howru', None
    if R(r'who are you|what can you do|what are you|^help\b'): return 'help', None
    if R(r"what time|the time|current time"): return 'time', None
    if R(r"what('s| is) (this|playing|the song|that song)|which (song|track)|what song|now playing"): return 'now', None
    if R(r'\b(theme|colou?r|skin|scheme)\b|^(?:go|switch|change)\b.*\b(' + '|'.join(THEME_ALIASES) + r')\b'):
        for k, v in THEME_ALIASES.items():
            if re.search(r'\b' + k + r'\b', c): return 'theme', v
        return 'theme', None
    if R(r'\bunmute\b'): return 'unmute', None
    if R(r'\bmute\b'): return 'mute', None
    if R(r'volume|louder|quieter|softer|turn (?:it )?(?:up|down)'):
        n = R(r'\d+')
        if n: return 'volset', max(0, min(100, int(n.group())))
        if R(r'louder|\bup\b|raise|increase|higher'): return 'volup', None
        if R(r'quieter|softer|\bdown\b|lower|decrease|reduce'): return 'voldown', None
        return 'volset', None
    if R(r'\b(restart|replay|start over|from the beginning)\b'): return 'restart', None
    if R(r'\b(pause|hold on|hold)\b'): return 'pause', None
    if R(r'\b(resume|continue|unpause|keep going)\b'): return 'resume', None
    if R(r'\b(stop|end|silence)\b'): return 'stop', None
    if R(r'\b(next|skip)\b'): return 'next', None
    if R(r'\b(previous|go back|last song|back)\b'): return 'prev', None
    if R(r'shuffle'): return 'shuffle', None
    if R(r'\b(repeat|loop)\b'): return 'repeat', None
    if R(r'\b(list|show)\b.*\b(songs|tracks|library)\b'): return 'list', None
    return 'unknown', c

CONTROL = {'pause', 'resume', 'stop', 'next', 'prev', 'restart', 'shuffle', 'repeat', 'mute', 'unmute', 'volset', 'volup', 'voldown', 'theme', 'list'}

def small_talk(t, s):
    """Offline fallback conversation (used only when no API key is configured)."""
    c = t.lower()
    if re.search(r'your name|who made you|who created|who are you', c): return f"I'm JARVIS, {s}. Just A Rather Very Intelligent System, at your service."
    if re.search(r'joke', c): return random.choice(["Why don't scientists trust atoms? Because they make up everything.", "I would tell you a UDP joke, but you might not get it.", "I asked the music library for a joke. It said it only knows tracks."])
    if re.search(r'good night|going to sleep|going to bed', c): return f"Good night, {s}. I'll keep the lights low."
    if re.search(r"\b(sad|tired|stressed|bored|lonely)\b", c): return f"I'm sorry to hear that, {s}. Perhaps some music would help. Shall I put something on?"
    if re.search(r'weather|news|stock|score|search', c): return "I can't reach live information in this mode, sir. Once you add an API key, I can talk about almost anything."
    return random.choice([f"I'm afraid I can only chat properly once my AI key is set up, {s}, but I'm happy to play you something.",
                          f"That's a little beyond my offline mode, {s}. Shall I put on a song instead?"])

# ----------------------------------------------------------------------------- audio analysis
class Analyzer:
    """Real FFT of the decoded PCM around the playback position, with beat detection."""
    def __init__(self, N=4096):
        self.N = N; self.win = np.hanning(N).astype(np.float32)
        self.rate = 0; self.gain = .6; self.prev = 0.0; self.flux = []; self.last_beat = 0.0

    def _prep(self, rate):
        f = np.fft.rfftfreq(self.N, 1 / rate)
        e = np.geomspace(40, min(11000, rate * .49), 65)
        self.lo = np.searchsorted(f, e[:-1]); self.hi = np.maximum(self.lo + 1, np.searchsorted(f, e[1:])); self.rate = rate

    def process(self, pcm, rate, pos_ms):
        if pcm is None or len(pcm) < self.N: return None
        if rate != self.rate: self._prep(rate)
        at = int(pos_ms * rate / 1000)
        if at < 0 or at >= len(pcm): return None
        s = max(0, at - self.N // 2)
        c = pcm[s:s + self.N].astype(np.float32) / 32768.0
        if len(c) < self.N: c = np.pad(c, (0, self.N - len(c)))
        level = min(1.0, float(np.sqrt(np.mean(c * c))) * 4.2)
        sp = np.abs(np.fft.rfft(c * self.win)); p = (sp * sp).astype(np.float64)
        cs = np.concatenate(([0.0], np.cumsum(p)))
        amp = np.sqrt((cs[self.hi] - cs[self.lo]) / (self.hi - self.lo))
        b = np.clip(np.log1p(amp * .13) / 3.8, 0, 1)
        self.gain = max(self.gain * .997, float(b.max()))
        b = np.clip(b * .95 / max(.45, self.gain), 0, 1).astype(np.float32)
        bass, mid, tre = float(b[:10].mean()), float(b[10:36].mean()), float(b[36:].mean())
        avg = float(np.mean(self.flux)) if self.flux else 0.0     # ~1 s of bass history
        self.flux = (self.flux + [bass])[-30:]
        now = time.perf_counter()
        beat = bass > self.prev + .04 and bass > avg * 1.3 + .05 and now - self.last_beat > .25
        self.prev = bass
        if beat: self.last_beat = now
        return b, level, bass, mid, tre, beat

# ----------------------------------------------------------------------------- widgets
class Bridge(QObject):
    speech_ready = Signal(int, object)
    transcript = Signal(str)
    error = Signal(str)
    decoded = Signal(int, object)
    meta_done = Signal(object)
    mic_level = Signal(float)
    ears = Signal(str)
    chat_reply = Signal(str)

class Panel(QFrame):
    """Glass panel with glowing edge and corner brackets, themed live."""
    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        r = QRectF(self.rect()).adjusted(1, 1, -1, -1)
        g = QLinearGradient(r.topLeft(), r.bottomRight()); g.setColorAt(0, col('panel', 205)); g.setColorAt(1, col('bg', 225))
        p.setBrush(QBrush(g)); p.setPen(QPen(col('a', 55), 1)); p.drawRoundedRect(r, 10, 10)
        L = 18; p.setPen(QPen(col('a', 230), 2)); x0, y0, x1, y1 = r.left(), r.top(), r.right(), r.bottom()
        for (x, y, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x0, y1, 1, -1), (x1, y1, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * L, y)); p.drawLine(QPointF(x, y), QPointF(x, y + dy * L))

class WaveSeek(QWidget):
    """Full-track waveform from the decoded audio; click or drag to seek."""
    seek = Signal(float)
    def __init__(self):
        super().__init__(); self.setFixedHeight(66); self.setCursor(Qt.PointingHandCursor)
        self.pk = None; self.frac = 0.0; self._cache = None; self.drag = False

    def set_peaks(self, pk):
        self.pk = pk; self._cache = None; self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); w, h = self.width(), self.height(); mid = h / 2
        if self.pk is None:
            p.setPen(QPen(col('a', 80), 1)); p.drawLine(QPointF(0, mid), QPointF(w, mid))
            p.setPen(col('dim')); p.setFont(font(10, mono=True, spacing=2)); p.drawText(QRectF(0, 0, w, h), Qt.AlignCenter, 'WAVEFORM STANDBY'); return
        n = max(10, int(w // 4))
        if self._cache is None or self._cache[0] != n:
            idx = np.linspace(0, len(self.pk), n + 1).astype(int)
            self._cache = (n, [float(self.pk[idx[i]:max(idx[i] + 1, idx[i + 1])].max()) for i in range(n)])
        vals = self._cache[1]
        for i, v in enumerate(vals):
            hh = max(2.0, (v ** .7) * (h - 8)); x = i * (w / n) + 1
            played = (i / n) < self.frac
            p.setPen(QPen(col('a', 235) if played else col('a', 60), 2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(x, mid - hh / 2), QPointF(x, mid + hh / 2))
        px = self.frac * w; p.setPen(QPen(col('b', 255), 2)); p.drawLine(QPointF(px, 2), QPointF(px, h - 2))

    def _emit(self, ev):
        self.frac = max(0.0, min(1.0, ev.position().x() / max(1, self.width()))); self.seek.emit(self.frac); self.update()
    def mousePressEvent(self, ev): self.drag = True; self._emit(ev)
    def mouseMoveEvent(self, ev):
        if self.drag: self._emit(ev)
    def mouseReleaseEvent(self, ev): self.drag = False

class Reactor(QWidget):
    """Audio-reactive arc reactor. Everything reacts to decoded PCM, mic level or the voice envelope."""
    def __init__(self):
        super().__init__(); self.setMinimumSize(430, 430)
        self.an = Analyzer(); self.van = Analyzer(2048); self.spin = 0.0; self.phase = 0.0; self.playing = False; self.mode = 'idle'; self.conv = False
        self.target = np.zeros(64, np.float32); self.bands = np.zeros(64, np.float32); self.peaks = np.zeros(64, np.float32)
        self.level = self.bass = self.mid = self.treble = 0.0
        self.beat = 0.0; self.ripples = []; self.parts = []; self.voice = 0.0; self.mic = 0.0; self.boot = 0.0
        self.dust = [[random.random(), random.random(), random.random() * .7 + .3, random.random() * .05 + .01] for _ in range(90)]
        self.bg = None
        th = np.linspace(0, math.tau, 49); self.sph = []                 # 3D wire globe geometry
        for ph in np.radians([-60, -30, 0, 30, 60]):
            P = np.array([np.cos(ph) * np.cos(th), np.full_like(th, np.sin(ph)), np.cos(ph) * np.sin(th)]); self.sph.append((P, self._bidx(P)))
        for k in range(8):
            t0 = k * math.tau / 8; ph = np.linspace(-math.pi / 2, math.pi / 2, 25)
            P = np.array([np.cos(ph) * math.cos(t0), np.sin(ph), np.cos(ph) * math.sin(t0)]); self.sph.append((P, self._bidx(P)))
        t2 = np.linspace(0, math.tau, 73); self.ring = np.array([np.cos(t2) * 1.9, np.sin(t2) * 1.9, np.zeros_like(t2)])
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(30)

    @staticmethod
    def _bidx(P): return ((np.arctan2(P[2], P[0]) / math.tau) % 1.0 * 64).astype(int) % 64

    @staticmethod
    def rot(ay, ax, az=0.0):
        cy, sy, cx, sx, cz, sz = math.cos(ay), math.sin(ay), math.cos(ax), math.sin(ax), math.cos(az), math.sin(az)
        return (np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]]) @ np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
                @ np.array([[cy, 0, sy], [0, 1, 0], [-sy, 0, cy]]))

    def poly3(self, p, P, U, cf, cb, wf=1.5, wb=1.0):
        """Perspective-project a 3D polyline; front-facing runs bright, back-facing runs dim."""
        sc_ = 7.0 / (7.0 - P[2]); x = P[0] * sc_ * U; y = P[1] * sc_ * U; front = P[2] >= 0; n = len(x)
        cut = (np.flatnonzero(front[1:] != front[:-1]) + 1).tolist()
        for a, b in zip([0] + cut, cut + [n]):
            b = min(n, b + 1)
            if b - a < 2: continue
            p.setPen(QPen(cf if front[a] else cb, wf if front[a] else wb))
            p.drawPolyline(QPolygonF([QPointF(float(x[k]), float(y[k])) for k in range(a, b)]))

    def draw_holo(self, p, R, sc):
        """Holographic emblem: audio-displaced wire globe, three gyro rings and a ring of rotating J.A.R.V.I.S letters, all true 3D."""
        U = R * .20; t = time.time(); M0 = self.rot(0, .38 + .14 * math.sin(t * .6)); spin = self.spin
        front = QColor(sc); front.setAlpha(235); back = QColor(sc); back.setAlpha(65)
        bright = mix(sc, QColor('#ffffff'), .65); warm = QColor(T['b'])
        e = max(self.level, .12 if self.mode != 'idle' else .05)
        g = QRadialGradient(QPointF(0, 0), U * 1.5); g.setColorAt(0, QColor(255, 255, 255, int(80 + 120 * e + 70 * self.beat)))
        gc = QColor(sc); gc.setAlpha(int(60 + 60 * e)); g.setColorAt(.5, gc); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.setPen(Qt.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(QPointF(0, 0), U * 1.5, U * 1.5); p.setBrush(Qt.NoBrush)
        M = M0 @ self.rot(spin, 0)
        for P, idx in self.sph:                                      # globe surface is pushed out by the live spectrum
            self.poly3(p, M @ (P * (1 + self.bands[idx] * .30 + self.beat * .10)), U, front, back)
        rings = [(self.rot(spin * 1.3, 1.15), QColor(sc)), (self.rot(-spin * .9, .35, 1.0), warm), (self.rot(spin * .7, 1.9, -.6), QColor(sc))]
        for k, (Rr, c) in enumerate(rings):
            Mr = M0 @ Rr; cf = QColor(c); cf.setAlpha(225); cb = QColor(c); cb.setAlpha(55)
            self.poly3(p, Mr @ self.ring, U, cf, cb, 1.8, 1.0)
            for j in range(3):                                       # orbiting beads
                a = spin * (1.2 + .4 * k) + j * math.tau / 3; b = Mr @ np.array([math.cos(a) * 1.9, math.sin(a) * 1.9, 0.0]); s_ = 7 / (7 - b[2])
                p.setPen(Qt.NoPen); p.setBrush(bright if b[2] >= 0 else back); p.drawEllipse(QPointF(b[0] * s_ * U, b[1] * s_ * U), U * .075 * s_, U * .075 * s_)
        p.setFont(font(U * .36, True)); Mr = M0 @ rings[0][0]; txt = 'J.A.R.V.I.S  ' * 2; n = len(txt)   # letters orbiting on ring 1
        for k, ch in enumerate(txt):
            if ch == ' ': continue
            a = k * math.tau / n + t * .45; b = Mr @ np.array([math.cos(a) * 1.9, math.sin(a) * 1.9, 0.0]); s_ = 7 / (7 - b[2])
            c = QColor(bright) if b[2] >= 0 else QColor(sc); c.setAlpha(240 if b[2] >= 0 else 70); p.setPen(c)
            p.drawText(QRectF(b[0] * s_ * U - U * .3, b[1] * s_ * U - U * .3, U * .6, U * .6), Qt.AlignCenter, ch)

    def draw_scan(self, p, R, sc, t):
        p.setPen(QPen(QColor(sc.red(), sc.green(), sc.blue(), 16), 1)); y = -R * .45
        while y < R * .45: p.drawLine(QPointF(-R * .45, y), QPointF(R * .45, y)); y += 4
        sy = -R * .45 + ((t * .35) % 1.0) * R * .9; sg = QLinearGradient(0, sy - R * .06, 0, sy + R * .06)
        c0 = QColor(sc); c0.setAlpha(0); c1 = QColor(sc); c1.setAlpha(80); sg.setColorAt(0, c0); sg.setColorAt(.5, c1); sg.setColorAt(1, c0)
        p.fillRect(QRectF(-R * .45, sy - R * .06, R * .9, R * .12), QBrush(sg))

    def set_audio(self, pcm, rate, pos_ms, voice=False):
        r = (self.van if voice else self.an).process(pcm, rate, pos_ms) if (voice or self.playing) else None
        if r is None:
            self.target *= .7; self.level *= .8; self.bass *= .8; self.mid *= .8; self.treble *= .8; return
        self.target, self.level, self.bass, self.mid, self.treble, beat = r
        if beat:
            self.beat = 1.0; self.ripples.append(0.0)
            for _ in range(int(8 + 22 * self.bass)):
                a = random.random() * math.tau; v = random.random() * .5 + .25
                self.parts.append([math.cos(a), math.sin(a), math.cos(a) * v, math.sin(a) * v, 1.0])
            self.parts = self.parts[-260:]

    def tick(self):
        dt = .03; self.boot = min(1.0, self.boot + dt / 2.4)
        self.phase += dt * (1 + 2.2 * self.level + 2 * self.voice)
        self.spin += dt * (.8 + 1.8 * self.level + 1.4 * self.voice)
        up = self.target > self.bands
        self.bands = np.where(up, self.bands * .35 + self.target * .65, self.bands * .86 + self.target * .14).astype(np.float32)
        self.peaks = np.maximum(self.peaks - .012, self.bands)
        self.beat *= .86
        self.ripples = [a + dt * 1.15 for a in self.ripples if a < 1]
        for q in self.parts:
            q[0] += q[2] * dt * 1.1; q[1] += q[3] * dt * 1.1; q[4] -= dt * .9
        self.parts = [q for q in self.parts if q[4] > 0]
        self.update()

    def make_bg(self):
        w, h = self.width(), self.height(); pm = QPixmap(w, h); pm.fill(QColor(T['bg']))
        p = QPainter(pm); p.setRenderHint(QPainter.Antialiasing)
        g = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * .62)
        g.setColorAt(0, col('a', 46)); g.setColorAt(.45, col('a', 12)); g.setColorAt(1, QColor(0, 0, 0, 0))
        p.fillRect(0, 0, w, h, QBrush(g))
        p.setPen(QPen(col('a', 26), 1.6))
        for x in range(14, w, 28):
            for y in range(14, h, 28): p.drawPoint(x, y)
        v = QRadialGradient(QPointF(w / 2, h / 2), max(w, h) * .75)
        v.setColorAt(.55, QColor(0, 0, 0, 0)); v.setColorAt(1, QColor(0, 0, 0, 170)); p.fillRect(0, 0, w, h, QBrush(v))
        p.end(); return pm

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing)
        w, h = self.width(), self.height()
        if self.bg is None or self.bg.size() != self.size(): self.bg = self.make_bg()
        p.drawPixmap(0, 0, self.bg)
        A, B = QColor(T['a']), QColor(T['b'])
        sc = {'idle': A, 'music': A, 'listening': QColor('#3dffa8'), 'thinking': B, 'speaking': mix(B, QColor('#ffffff'), .55)}[self.mode]
        t = time.time()
        for d in self.dust:                                        # drifting dust motes
            p.setPen(QPen(col('a', int(50 * d[2])), 1.8)); p.drawPoint(QPointF(d[0] * w, ((d[1] - t * d[3] * .1) % 1.0) * h))
        cx, cy = w / 2, h / 2; R = min(w, h) * .235; boot = 1 - (1 - self.boot) ** 3
        p.translate(cx, cy); p.setOpacity(boot); p.scale(.9 + .1 * boot, .9 + .1 * boot)
        p.setCompositionMode(QPainter.CompositionMode_Plus)
        off = self.phase * .02
        rt = R * 1.95                                              # rotating degree scale
        for i in range(120):
            a = math.radians(i * 3) + off; long = i % 10 == 0; r2 = rt + R * (.075 if long else .035)
            p.setPen(QPen(col('a', 170 if long else 55), 1.4 if long else 1))
            p.drawLine(QPointF(math.cos(a) * rt, math.sin(a) * rt), QPointF(math.cos(a) * r2, math.sin(a) * r2))
        for age in self.ripples:                                   # bass shockwaves
            r = R * (.65 + 1.3 * age); p.setPen(QPen(mix(sc, QColor('#ffffff'), .3), 2.2 * (1 - age) + .4)); c = QColor(sc); c.setAlpha(int(140 * (1 - age)))
            p.setPen(QPen(c, 2.2 * (1 - age) + .4)); p.setBrush(Qt.NoBrush); p.drawEllipse(QPointF(0, 0), r, r)
        inner = R * 1.26; bw = max(2.0, 2 * math.pi * inner / 64 * .5); span = R * .5
        pts = []
        for i in range(64):                                        # frequency bars + peak caps
            th = math.tau * i / 64 - math.pi / 2; amp = float(self.bands[i]); ln = R * .045 + amp * span
            c = mix(A, B, amp ** 2); c.setAlpha(80 + int(amp * 175))
            ct, st = math.cos(th), math.sin(th)
            p.setPen(QPen(c, bw, Qt.SolidLine, Qt.RoundCap)); p.drawLine(QPointF(ct * inner, st * inner), QPointF(ct * (inner + ln), st * (inner + ln)))
            pk = float(self.peaks[i])
            if pk > .06:
                pr = inner + R * .045 + pk * span + R * .035; p.setPen(QPen(QColor(255, 255, 255, 190), bw * .55, Qt.SolidLine, Qt.RoundCap))
                p.drawPoint(QPointF(ct * pr, st * pr))
            rr = R * 1.12 + amp * R * .13; pts.append(QPointF(ct * rr, st * rr))
        mids = [(pts[i] + pts[(i + 1) % 64]) * .5 for i in range(64)]   # smooth spectrum contour
        path = QPainterPath(); path.moveTo(mids[63])
        for i in range(64): path.quadTo(pts[i], mids[i])
        p.setPen(QPen(col('a', 175), 1.6)); p.setBrush(QBrush(col('a', 16))); p.drawPath(path); p.setBrush(Qt.NoBrush)
        for i in range(4):                                         # counter-rotating segmented rings
            r = R * (.70 + i * .09); hot = (i == 2)
            p.setPen(QPen(col('b', 220) if hot else col('a', 190), 2.6 if hot else 1.5))
            for s in range(8):
                ang = (self.phase * (22 if i % 2 else -17) + s * 45 + i * 17)
                p.drawArc(QRectF(-r, -r, 2 * r, 2 * r), int(ang * 16), int((20 + i * 3) * 16))
        cr = R * .60                                               # arc-reactor coils
        p.setPen(QPen(mix(sc, QColor('#ffffff'), self.beat * .5), R * .06, Qt.SolidLine, Qt.FlatCap))
        for s in range(10):
            p.drawArc(QRectF(-cr, -cr, 2 * cr, 2 * cr), int((s * 36 + self.phase * 4) * 16), int(24 * 16))
        if self.mode == 'speaking':                                # voice ring follows the real speech envelope
            n = 72; vp = QPainterPath()
            for i in range(n + 1):
                th = math.tau * i / n; r = R * .535 + R * (.045 * self.voice) * math.sin(th * 6 + t * 9) + R * .02 * self.voice * math.sin(th * 11 - t * 13)
                pt = QPointF(math.cos(th) * r, math.sin(th) * r); vp.moveTo(pt) if i == 0 else vp.lineTo(pt)
            p.setPen(QPen(QColor(255, 255, 255, 215), 2.4)); p.drawPath(vp)
        elif self.mode == 'listening':
            r = R * (.535 + .05 * min(1, self.mic)); p.setPen(QPen(QColor(61, 255, 168, 230), 2.6)); p.drawEllipse(QPointF(0, 0), r, r)
        energy = max(self.level, .1 if self.mode != 'idle' else .04)
        g = QRadialGradient(QPointF(0, 0), R * .5 * (1 + .1 * self.beat + .06 * energy))
        g.setColorAt(0, QColor(255, 255, 255, int(40 + 90 * energy + 60 * self.beat))); g.setColorAt(.55, mix(sc, QColor(0, 0, 0), .2)); g.setColorAt(1, QColor(0, 0, 0, 0))
        gc = QColor(sc); gc.setAlpha(80); g.setColorAt(.55, gc); p.setPen(Qt.NoPen); p.setBrush(QBrush(g)); p.drawEllipse(QPointF(0, 0), R * .5, R * .5)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setBrush(QColor(3, 14, 24, 150)); p.setPen(QPen(col('a', 230), 2)); p.drawEllipse(QPointF(0, 0), R * .46, R * .46)
        p.save(); clip = QPainterPath(); clip.addEllipse(QPointF(0, 0), R * .45, R * .45); p.setClipPath(clip)
        p.setCompositionMode(QPainter.CompositionMode_Plus); p.setOpacity(boot * (1 - .2 * (random.random() < .05)))
        p.save(); p.translate(0, -R * .05); self.draw_holo(p, R, sc); p.restore(); self.draw_scan(p, R, sc, t)
        p.restore()
        for q in self.parts:                                       # beat particles
            pr = R * (1.3 + (1 - q[4]) * 1.1); c = QColor(sc); c.setAlpha(int(220 * q[4]))
            p.setPen(QPen(c, 2.4 * q[4] + .6, Qt.SolidLine, Qt.RoundCap))
            ang = math.atan2(q[1], q[0]); p.drawPoint(QPointF(math.cos(ang) * pr, math.sin(ang) * pr))
        p.setPen(QColor('#f4feff')); p.setFont(font(R * .07, True, spacing=R * .014))
        p.drawText(QRectF(-R * .5, R * .27, R, R * .09), Qt.AlignCenter, 'J.A.R.V.I.S')
        label = {'idle': 'AWAITING INPUT' if self.conv else 'STANDBY', 'music': 'LIVE SPECTRUM', 'listening': 'LISTENING',
                 'thinking': 'PROCESSING', 'speaking': 'SPEAKING'}[self.mode]
        p.setPen(sc); p.setFont(font(R * .045, mono=True, spacing=R * .01))
        p.drawText(QRectF(-R * .5, R * .355, R, R * .08), Qt.AlignCenter, label)
        p.resetTransform(); p.setOpacity(1)
        p.setPen(QPen(col('a', 190), 1.6)); m = 14; L = 24                  # HUD corners
        for (x, y, dx, dy) in ((m, m, 1, 1), (w - m, m, -1, 1), (m, h - m, 1, -1), (w - m, h - m, -1, -1)):
            p.drawLine(QPointF(x, y), QPointF(x + dx * L, y)); p.drawLine(QPointF(x, y), QPointF(x, y + dy * L))
        p.setFont(font(10, mono=True, spacing=1.5)); p.setPen(col('dim'))
        p.drawText(QPointF(m + 10, m + 24), 'FREQUENCY ARRAY // 64 CH')
        p.drawText(QRectF(w - 200 - m - 8, m + 10, 200, 20), Qt.AlignRight, time.strftime('%H:%M:%S'))
        p.drawText(QPointF(m + 10, h - m - 12), 'AUDIO INPUT: ' + ('LIVE PCM' if self.playing else 'STANDBY'))
        for k, (name, v) in enumerate((('BASS', self.bass), ('MID', self.mid), ('HIGH', self.treble))):
            x = w - m - 92 + k * 30; hh = 6 + min(1, v * 1.4) * 44
            p.setPen(Qt.NoPen); p.setBrush(col('a', 60)); p.drawRect(QRectF(x, h - m - 24 - 50, 12, 50))
            p.setBrush(mix(A, B, v)); p.drawRect(QRectF(x, h - m - 24 - hh, 12, hh))
            p.setPen(col('dim')); p.setFont(font(8, mono=True)); p.drawText(QPointF(x - 3, h - m - 8), name)

# ----------------------------------------------------------------------------- main window
def build_style():
    a, text, dim = T['a'], T['text'], T['dim']
    return f'''
    QWidget {{background:transparent; color:{text}; font-family:'Bahnschrift','Segoe UI'; font-size:13px;}}
    QPushButton {{background:rgba(255,255,255,12); border:1px solid {a}66; border-radius:8px; padding:10px 12px; color:{text}; font-weight:600;}}
    QPushButton:hover {{background:{a}30; border-color:{a};}}
    QPushButton:checked {{background:{a}40; border-color:{a}; color:white;}}
    QPushButton#play {{background:{a}33; border:2px solid {a}; border-radius:28px; min-width:56px; max-width:56px; min-height:56px; max-height:56px; padding:0; font-size:18px;}}
    QLineEdit {{background:rgba(0,0,0,110); border:1px solid {a}66; border-radius:8px; padding:11px; color:white; selection-background-color:{a}88;}}
    QLineEdit:focus {{border-color:{a};}}
    QTextEdit {{background:rgba(0,0,0,110); border:1px solid {a}33; border-radius:8px; padding:8px; color:{text};}}
    QListWidget {{background:rgba(0,0,0,100); border:1px solid {a}33; border-radius:8px; padding:4px; outline:none;}}
    QListWidget::item {{padding:7px 8px; border-radius:5px; color:{text};}}
    QListWidget::item:hover {{background:{a}22;}}
    QListWidget::item:selected {{background:{a}44; color:white;}}
    QComboBox {{background:rgba(0,0,0,110); border:1px solid {a}66; border-radius:8px; padding:8px 10px;}}
    QComboBox QAbstractItemView {{background:{T['panel']}; color:{text}; selection-background-color:{a}55; border:1px solid {a}66;}}
    QComboBox::drop-down {{border:none; width:22px;}}
    QSlider::groove:horizontal {{height:4px; background:{a}33; border-radius:2px;}}
    QSlider::sub-page:horizontal {{background:{a}; border-radius:2px;}}
    QSlider::handle:horizontal {{background:{a}; width:14px; height:14px; margin:-6px 0; border-radius:7px;}}
    QProgressBar {{background:{a}22; border:none; border-radius:3px; max-height:6px;}}
    QProgressBar::chunk {{background:{a}; border-radius:3px;}}
    QScrollBar:vertical {{background:transparent; width:8px;}}
    QScrollBar::handle:vertical {{background:{a}55; border-radius:4px; min-height:24px;}}
    QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{height:0;}}
    QLabel#dim {{color:{dim};}}
    '''

class Jarvis(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle('J.A.R.V.I.S  |  MUSIC REACTOR MARK X  -  ROBOT FACE'); self.resize(1440, 900); self.setMinimumSize(1120, 740)
        S = self.settings = QSettings('Jarvis', 'MusicReactor')
        self.theme = str(S.value('theme', 'ARC')); self.theme = self.theme if self.theme in THEMES else 'ARC'
        T.clear(); T.update(THEMES[self.theme])
        self.folder = Path(S.value('music_folder', str(Path.home() / 'Music')))
        self.addr = str(S.value('address', 'sir'))
        self.api_key = self.load_api_key(); self.history = []; self.chatting = False; self.hinted = False
        self.sim_voice = False; self.cur_pcm = None; self.pending_mood = None
        self.voice_name = str(S.value('voice_mk10b', 'en-US-AnaNeural|kawaii'))
        self.voice_rate = int(S.value('voice_rate_mk10', -4))
        self.whisper_model = os.environ.get('JARVIS_WHISPER', str(S.value('whisper_model', 'base.en')))
        self.cache = Path(tempfile.gettempdir()) / 'jarvis_voice_cache'; self.cache.mkdir(exist_ok=True); self.prune_cache()
        self.pronunciations = self.load_pronunciations()
        self.songs, self.meta, self.index, self.pending_index = [], {}, -1, None
        self.pcm, self.pcm_rate, self.decode_serial, self.decoded_ms = None, 22050, 0, 0
        self.shuffle = self.repeat = self.muted = False
        self.vol = int(S.value('volume', 70)) / 100; self.cur_vol = 0.0
        self.speaking = False; self.speech_queue = []; self.speech_after = None; self.speech_serial = 0
        self.seg_items, self.seg_i, self.cur_env, self.seg_token = [], 0, None, None
        self.listen_stop = threading.Event(); self.listen_thread = None
        self.follow_until = 0.0; self.mute_until = 0.0; self.ears = 'OFF'; self.prompt = 'Jarvis, play'
        self.last_line = {}; self._pos = 0; self._pos_t = time.perf_counter()
        self.bridge = Bridge()
        for sig, fn in ((self.bridge.speech_ready, self.on_speech_ready), (self.bridge.transcript, self.on_transcript),
                        (self.bridge.error, lambda m: self.log_line('ERR', m)), (self.bridge.decoded, self.on_decoded),
                        (self.bridge.meta_done, self.on_meta), (self.bridge.mic_level, self.on_mic_level),
                        (self.bridge.ears, lambda s: setattr(self, 'ears', s)), (self.bridge.chat_reply, self.on_chat_reply)):
            sig.connect(fn)
        self.audio = QAudioOutput(); self.player = QMediaPlayer(); self.player.setAudioOutput(self.audio)
        self.speech_audio = QAudioOutput(); self.speech_audio.setVolume(1.0)
        self.speech_player = QMediaPlayer(); self.speech_player.setAudioOutput(self.speech_audio)
        self.speech_player.mediaStatusChanged.connect(self.on_speech_status)
        self.player.playbackStateChanged.connect(self.on_playback); self.player.mediaStatusChanged.connect(self.on_media_status)
        self.player.positionChanged.connect(self.on_position); self.player.durationChanged.connect(lambda n: setattr(self, 'duration', n))
        self.player.errorOccurred.connect(lambda err, msg: self.log_line('ERR', 'Player: ' + msg) if msg else None)
        self.duration = 0
        self.build_ui(); self.apply_theme(self.theme, speak=False)
        self.timer = QTimer(self); self.timer.timeout.connect(self.tick); self.timer.start(33)
        self.scan()
        QTimer.singleShot(1100, self.greet)
        if S.value('always_listening', False, type=bool): QTimer.singleShot(1500, lambda: self.mic.setChecked(True))

    # ---- UI
    def label(self, text, px=12, bold=False, spacing=0.0, color=None, mono=False):
        l = QLabel(text); l.setFont(font(px, bold, mono, spacing))
        if color: l.setStyleSheet(f'color:{color};')
        return l

    def build_ui(self):
        root = QVBoxLayout(self); root.setContentsMargins(22, 16, 22, 18); root.setSpacing(12)
        top = QHBoxLayout(); brand = QVBoxLayout(); brand.setSpacing(0)
        brand.addWidget(self.label('J.A.R.V.I.S', 28, True, 8, '#f4feff'))
        self.sub = self.label('MARK X  MUSIC REACTOR  /  ROBOT FACE  /  NEURAL VOICE', 11, False, 3); self.sub.setObjectName('dim'); brand.addWidget(self.sub)
        top.addLayout(brand); top.addStretch()
        self.status = self.label('●  SYSTEM ONLINE', 13, True, 2); top.addWidget(self.status); root.addLayout(top)
        main = QHBoxLayout(); main.setSpacing(14)
        left = Panel(); left.setFixedWidth(285); lv = QVBoxLayout(left); lv.setContentsMargins(16, 18, 16, 16); lv.setSpacing(8)
        lv.addWidget(self.label('MUSIC LIBRARY', 11, True, 2, T['a']))
        self.library = self.label('', 11); self.library.setObjectName('dim'); self.library.setWordWrap(True); lv.addWidget(self.library)
        self.search = QLineEdit(); self.search.setPlaceholderText('Search tracks...'); self.search.textChanged.connect(self.filter_list); lv.addWidget(self.search)
        self.listw = QListWidget(); self.listw.itemActivated.connect(lambda it: self.request_play(it.data(Qt.UserRole))); lv.addWidget(self.listw, 1)
        row = QHBoxLayout()
        b = QPushButton('FOLDER'); b.clicked.connect(self.choose_folder); row.addWidget(b)
        b = QPushButton('RESCAN'); b.clicked.connect(self.scan); row.addWidget(b); lv.addLayout(row)
        lv.addWidget(self.label('Double-click a track to play', 10, color=T['dim']))
        main.addWidget(left)
        center = Panel(); cv = QVBoxLayout(center); cv.setContentsMargins(14, 10, 14, 14); cv.setSpacing(6)
        self.use_face = FaceReactor is not None and os.environ.get('JARVIS_HUD', '').lower() != 'classic'
        self.reactor = FaceReactor(Analyzer, T) if self.use_face else Reactor(); cv.addWidget(self.reactor, 1)
        self.song = self.label('NO TRACK SELECTED', 22, True, 1.5, '#ffffff'); self.song.setAlignment(Qt.AlignCenter); self.song.setWordWrap(True); cv.addWidget(self.song)
        self.detail = self.label('Choose a folder, then say "Jarvis, play ..."', 12); self.detail.setObjectName('dim'); self.detail.setAlignment(Qt.AlignCenter); cv.addWidget(self.detail)
        self.wave = WaveSeek(); self.wave.seek.connect(lambda f: self.player.setPosition(int(f * self.decoded_ms)) if self.decoded_ms else None); cv.addWidget(self.wave)
        tr = QHBoxLayout(); self.t_cur = self.label('0:00', 11, mono=True); self.t_tot = self.label('0:00', 11, mono=True)
        tr.addWidget(self.t_cur); tr.addStretch(); tr.addWidget(self.t_tot); cv.addLayout(tr)
        bt = QHBoxLayout(); bt.addStretch()
        self.btn_shuffle = QPushButton('⇄'); self.btn_shuffle.setCheckable(True); self.btn_shuffle.toggled.connect(lambda v: setattr(self, 'shuffle', v))
        self.btn_repeat = QPushButton('↻'); self.btn_repeat.setCheckable(True); self.btn_repeat.toggled.connect(lambda v: setattr(self, 'repeat', v))
        self.btn_play = QPushButton('▶'); self.btn_play.setObjectName('play'); self.btn_play.clicked.connect(self.toggle)
        for w_, fn in ((self.btn_shuffle, None), (QPushButton('◀◀'), self.previous), (self.btn_play, None), (QPushButton('■'), self.stop), (QPushButton('▶▶'), self.next), (self.btn_repeat, None)):
            if fn: w_.clicked.connect(lambda _=False, f=fn: f())
            bt.addWidget(w_)
        bt.addStretch(); cv.addLayout(bt); main.addWidget(center, 1)
        right = Panel(); right.setFixedWidth(310); rv = QVBoxLayout(right); rv.setContentsMargins(16, 18, 16, 16); rv.setSpacing(8)
        rv.addWidget(self.label('JARVIS CONSOLE', 11, True, 2, T['a']))
        self.logview = QTextEdit(); self.logview.setReadOnly(True); rv.addWidget(self.logview, 1)
        rv.addWidget(self.label('TEXT COMMAND', 11, True, 2, T['a']))
        self.command = QLineEdit(); self.command.setPlaceholderText('Type to JARVIS: play ..., pause, louder ...')
        self.command.returnPressed.connect(self.send); rv.addWidget(self.command)
        go = QPushButton('SEND  ➤'); go.clicked.connect(self.send); rv.addWidget(go)
        rv.addWidget(self.label('VOICE LAB', 11, True, 2, T['a']))
        self.voice_box = QComboBox()
        for name, vid in VOICES: self.voice_box.addItem(name, vid)
        i = self.voice_box.findData(self.voice_name); self.voice_box.setCurrentIndex(max(0, i))
        self.voice_box.currentIndexChanged.connect(self.on_voice_change); rv.addWidget(self.voice_box)
        sr = QHBoxLayout(); sr.addWidget(self.label('Pace', 11, color=T['dim']))
        self.rate_slider = QSlider(Qt.Horizontal); self.rate_slider.setRange(-20, 15); self.rate_slider.setValue(self.voice_rate)
        self.rate_slider.valueChanged.connect(self.on_rate_change); sr.addWidget(self.rate_slider)
        tb = QPushButton('TEST'); tb.clicked.connect(lambda: self.say(self.pick('test'))); sr.addWidget(tb); rv.addLayout(sr)
        self.chat_label = self.label('AI CHAT: ONLINE' if self.api_key else 'AI CHAT: add api_key.txt (see README)', 10, color=T['dim']); rv.addWidget(self.chat_label)
        rv.addWidget(self.label('OUTPUT VOLUME', 11, True, 2, T['a']))
        self.volume = QSlider(Qt.Horizontal); self.volume.setRange(0, 100); self.volume.setValue(int(self.vol * 100))
        self.volume.valueChanged.connect(self.on_volume); rv.addWidget(self.volume)
        self.theme_btn = QPushButton(); self.theme_btn.clicked.connect(lambda: self.cycle_theme(True)); rv.addWidget(self.theme_btn)
        if self.use_face:
            self.face_box = QComboBox(); self.face_box.addItem('FACE MOOD:  AUTO', None)
            for n_ in FACE_NAMES: self.face_box.addItem('FACE MOOD:  ' + n_.upper(), n_)
            self.face_box.currentIndexChanged.connect(lambda i: self.reactor.set_pin(self.face_box.itemData(i))); rv.addWidget(self.face_box)
        self.mic = QPushButton('🎙  ALWAYS LISTENING'); self.mic.setCheckable(True); self.mic.toggled.connect(self.toggle_listening); rv.addWidget(self.mic)
        self.meter = QProgressBar(); self.meter.setRange(0, 100); self.meter.setTextVisible(False); rv.addWidget(self.meter)
        main.addWidget(right); root.addLayout(main, 1)
        self.command.setFocus()

    def paintEvent(self, e):
        p = QPainter(self); g = QLinearGradient(0, 0, self.width(), self.height())
        g.setColorAt(0, QColor(T['bg']).lighter(125)); g.setColorAt(.5, QColor(T['bg'])); g.setColorAt(1, QColor(T['bg']).darker(140))
        p.fillRect(self.rect(), QBrush(g))

    def keyPressEvent(self, e):
        if e.key() == Qt.Key_F11: self.showNormal() if self.isFullScreen() else self.showFullScreen()
        else: super().keyPressEvent(e)

    def apply_theme(self, name, speak=True):
        self.theme = name; T.clear(); T.update(THEMES[name]); self.settings.setValue('theme', name)
        self.setStyleSheet(build_style()); self.reactor.bg = None; self.theme_btn.setText(f'THEME:  {name}'); self.update()
        for w_ in self.findChildren(QWidget): w_.update()

    def cycle_theme(self, speak=False, name=None):
        names = list(THEMES); name = name or names[(names.index(self.theme) + 1) % len(names)]
        self.apply_theme(name)
        if speak: self.say(f'Switching to the {name.lower()} display.')

    # ---- robot face hooks (silently do nothing when the classic HUD is selected)
    def face(self, name, *a):
        fn = getattr(self.reactor, name, None) if self.use_face else None
        return fn(*a) if fn else None

    def face_intent(self, intent, arg=None):
        if intent == 'volset' and arg is not None: m = ('Excited', 2.5) if arg >= 70 else ('Sleepy', 2.5) if arg <= 20 else ('Happy', 2.5)
        else: m = INTENT_FACE.get(intent)
        if m: self.face('react', m[0], m[1] + 1.5)      # a little longer than the reaction so it covers the voice reply

    def log_line(self, who, text):
        if who == 'ERR' and not text.startswith(('Neural voice', 'Voice output', 'Microphone')): self.face('react', 'Confused', 2.5)
        colors = {'JARVIS': T['a'], 'YOU': T['b'], 'HEARD': T['dim'], 'ERR': '#ff6b6b', 'SYS': T['dim']}
        self.logview.append(f'<span style="color:{T["dim"]}">{time.strftime("%H:%M:%S")}</span> '
                            f'<b style="color:{colors.get(who, T["dim"])}">{who}</b> {html.escape(text)}')

    def log(self, text): self.log_line('SYS', text)

    # ---- voice output
    def pick(self, key, **kw):
        opts = [c for c in LINES[key] if c != self.last_line.get(key)] or LINES[key]
        c = random.choice(opts); self.last_line[key] = c
        return c.format(s=self.addr, n=kw.get('n', ''))

    def greet(self):
        h = datetime.now().hour; g = 'Good morning' if h < 12 else 'Good afternoon' if h < 17 else 'Good evening'
        n = len(self.songs); self.face('react', 'Happy', 6.0)
        self.say(f'{g}, {self.addr}. All systems are online, and I have {n} tracks ready. What would you like to hear?' if n
                 else f'{g}, {self.addr}. All systems are online. Please choose your music folder to begin.')

    def say(self, parts, after=None):
        parts = [parts] if isinstance(parts, str) else parts
        parts = [(x, None) if isinstance(x, str) else x for x in parts]
        parts = [(t, v) for t, v in parts if re.search(r'\w', t)]
        if not parts:
            if after: after()
            return
        self.log_line('JARVIS', ' '.join(t for t, _ in parts))
        self.speech_queue.append((parts, after)); self.pump_speech()

    def pump_speech(self):
        if self.speaking or not self.speech_queue: return
        parts, after = self.speech_queue.pop(0)
        self.speaking = True; self.speech_after = after; self.speech_serial += 1; self.cur_env = None; self.cur_pcm = None; self.sim_voice = False
        serial = self.speech_serial
        threading.Thread(target=self.speech_worker, args=(serial, parts), daemon=True).start()
        QTimer.singleShot(30000, lambda: self.speaking and serial == self.speech_serial and self.finish_speech())

    def speech_worker(self, serial, parts):
        try:
            import edge_tts
            default, _, fx = self.voice_name.partition('|')
            if fx not in FX_CHAINS: fx = ''
            async def one(text, voice):
                for v in ([voice, default] if voice and voice != default else [default]):
                    kw = dict(rate=f'{self.voice_rate:+d}%', pitch=f'{PITCH:+d}Hz') if v == default else {}
                    path = self.cache / (hashlib.sha1(f'{v}|{kw}|{fx}|{text}'.encode()).hexdigest()[:24] + '.mp3')
                    try:
                        if not (path.exists() and path.stat().st_size > 800):
                            tmp = path.with_suffix('.part'); await edge_tts.Communicate(text, voice=v, **kw).save(str(tmp))
                            if fx:
                                try: fxo = path.with_suffix('.fx.mp3'); apply_fx(tmp, fxo, fx); os.replace(fxo, path); tmp.unlink(missing_ok=True)
                                except Exception as e_: self.bridge.error.emit('Voice effect failed: ' + str(e_)[:100]); os.replace(tmp, path)
                            else: os.replace(tmp, path)
                        return str(path)
                    except Exception:
                        if v == default: raise
            async def go(): return await asyncio.gather(*[one(t, v) for t, v in parts])
            paths = asyncio.run(go())
            self.bridge.speech_ready.emit(serial, [(pth, *self.envelope(pth)) for pth in paths])
        except Exception as exc:
            self.bridge.error.emit('Neural voice offline, using Windows voice: ' + str(exc)[:120])
            try:
                import pyttsx3
                eng = pyttsx3.init(); eng.setProperty('rate', 170)
                for v in eng.getProperty('voices'):
                    if any(k in v.name for k in ('Zira', 'Hazel', 'Susan', 'George', 'David')): eng.setProperty('voice', v.id); break
                eng.say(' '.join(t for t, _ in parts)); eng.runAndWait()
            except Exception as err:
                self.bridge.error.emit('Voice output unavailable: ' + str(err)[:120])
            self.sim_voice = True
            self.bridge.speech_ready.emit(serial, [])

    @staticmethod
    def envelope(path):
        """Real loudness envelope of the speech clip (20 ms steps) so the HUD ring follows JARVIS's voice."""
        try:
            raw = ffmpeg_pcm(path, 16000); pcm = raw.astype(np.float32) / 32768; n = len(pcm) // 320
            env = np.sqrt((pcm[:n * 320].reshape(n, 320) ** 2).mean(1))
            return np.clip(env / (np.percentile(env, 95) + 1e-6), 0, 1), raw
        except Exception:
            return None, None

    def on_speech_ready(self, serial, items):
        if serial != self.speech_serial or not self.speaking: return
        if not items: self.finish_speech(); return
        self.seg_items, self.seg_i = items, 0; self.play_seg()

    def play_seg(self):
        if not self.speaking or self.seg_i >= len(self.seg_items): return
        path, env, pcm = self.seg_items[self.seg_i]; self.cur_env = env; self.cur_pcm = pcm
        if self.seg_i == 0 and self.pending_mood: self.face('react', *self.pending_mood); self.pending_mood = None
        tok = self.seg_token = (self.speech_serial, self.seg_i)
        self.speech_player.setSource(QUrl.fromLocalFile(path)); self.speech_player.play()
        # Safety net: if the player never reports "end of media", move on after the clip's known length.
        QTimer.singleShot((len(env) * 20 if env is not None else 15000) + 2500, lambda: self.advance_seg(tok))

    def advance_seg(self, tok):
        if not self.speaking or tok is None or tok != self.seg_token: return
        self.seg_token = None; self.seg_i += 1
        if self.seg_i < len(self.seg_items): QTimer.singleShot(0, self.play_seg)
        else: self.finish_speech()

    def on_speech_status(self, status):
        if status in (QMediaPlayer.EndOfMedia, QMediaPlayer.InvalidMedia): self.advance_seg(self.seg_token)

    def finish_speech(self):
        if not self.speaking: return
        self.speaking = False; self.cur_env = None
        after, self.speech_after = self.speech_after, None
        self.mute_until = time.time() + .6
        if self.mic.isChecked(): self.follow_until = time.time() + 12
        if after:
            try: after()
            except Exception as exc: self.log_line('ERR', 'Could not start track: ' + str(exc))
        self.pump_speech()

    def interrupt_speech(self):
        self.pending_mood = None; self.speech_queue.clear(); self.speech_serial += 1; self.speech_after = None
        if self.speaking: self.speaking = False; self.cur_env = None; self.speech_player.stop()

    def voice_level(self):
        if not self.speaking: return 0.0
        if self.cur_env is not None:
            i = int(self.speech_player.position() / 20)
            return float(self.cur_env[i]) if 0 <= i < len(self.cur_env) else 0.0
        return .35 + .35 * abs(math.sin(time.time() * 9)) if self.sim_voice else 0.0   # offline voice has no envelope

    def prune_cache(self):
        try:
            files = sorted(self.cache.glob('*.mp3'), key=lambda f: f.stat().st_mtime)
            for f in files[:-150]: f.unlink()
        except OSError: pass

    def load_pronunciations(self):
        try:
            data = json.loads((APP_DIR / 'pronunciations.json').read_text(encoding='utf-8'))
            return {normalize(k): v for k, v in data.items()}
        except (OSError, ValueError): return {}

    def spoken_title(self, title):
        e = self.pronunciations.get(normalize(title))
        if isinstance(e, dict): return (e.get('say', title), e.get('voice'))
        if isinstance(e, str): return (e, None)
        if re.search(r'[\u0B80-\u0BFF]', title): return (title, 'ta-IN-ValluvarNeural')
        if re.search(r'[\u0900-\u097F]', title): return (title, 'hi-IN-MadhurNeural')
        return (title, None)

    def on_voice_change(self, i):
        self.voice_name = self.voice_box.itemData(i); self.settings.setValue('voice_mk10b', self.voice_name); self.say(self.pick('test'))

    def on_rate_change(self, v): self.voice_rate = v; self.settings.setValue('voice_rate_mk10', v)

    # ---- library
    def choose_folder(self):
        path = QFileDialog.getExistingDirectory(self, 'Select your music folder', str(self.folder))
        if path: self.folder = Path(path); self.settings.setValue('music_folder', path); self.scan()

    def scan(self):
        self.songs = []
        try:
            if self.folder.is_dir():
                self.songs = sorted((p for p in self.folder.rglob('*') if p.is_file() and p.suffix.lower() in EXTENSIONS), key=lambda p: p.name.casefold())
        except OSError as exc: self.log_line('ERR', 'Library scan: ' + str(exc))
        self.library.setText(f'{len(self.songs)} tracks indexed\n{self.folder}'); self.rebuild_list()
        self.log(f'Library scan: {len(self.songs)} tracks found.')
        paths = list(self.songs)
        def work():
            out = {}
            try:
                from mutagen import File
                for p in paths:
                    try:
                        f = File(str(p), easy=True)
                        if f:
                            t, a = f.get('title'), f.get('artist'); out[p] = (clean_title(t[0]) if t else None, str(a[0]) if a else '')
                    except Exception: pass
            except Exception: pass
            self.bridge.meta_done.emit(out)
        threading.Thread(target=work, daemon=True).start()

    def on_meta(self, out):
        self.meta.update(out); self.rebuild_list()
        titles = [self.meta_of(p)[0] for p in self.songs[:14]]
        self.prompt = ('Jarvis, play ' + ', '.join(titles))[:380]

    def meta_of(self, p):
        t, a = self.meta.get(p, (None, ''))
        return (t or clean_title(p.stem), a)

    def rebuild_list(self):
        self.listw.clear()
        for i, p in enumerate(self.songs):
            t, a = self.meta_of(p); it = QListWidgetItem(f'{t}  -  {a}' if a else t)
            it.setData(Qt.UserRole, i); self.listw.addItem(it)
        self.filter_list(self.search.text())
        if 0 <= self.index < self.listw.count(): self.listw.setCurrentRow(self.index)

    def filter_list(self, text):
        q = text.casefold().strip()
        for i in range(self.listw.count()):
            it = self.listw.item(i); it.setHidden(bool(q) and q not in it.text().casefold())

    def best_match(self, query):
        q = normalize(query); qt = q.split(); best = (0.0, -1)
        for i, p in enumerate(self.songs):
            title, artist = self.meta_of(p); name = normalize(title); full = normalize(f'{title} {artist} {p.stem}')
            if q == name: s = 1.0
            elif q and q in full: s = .94
            else:
                words = full.split()
                cov = sum(1 for t in qt if any(SequenceMatcher(None, t, w).ratio() >= .8 for w in words)) / max(1, len(qt))
                s = max(SequenceMatcher(None, q, name).ratio(), .9 * cov if cov > .99 else .7 * cov)
            if s > best[0]: best = (s, i)
        return best

    # ---- conversation
    def load_api_key(self):
        k = os.environ.get('ANTHROPIC_API_KEY') or str(self.settings.value('api_key', '') or '')
        f = (APP_DIR / 'api_key.txt')
        if not k and f.exists():
            for line in f.read_text(encoding='utf-8', errors='ignore').splitlines():
                if line.strip() and not line.strip().startswith('#'): k = line.strip(); break
        return k.strip()

    def converse(self, text):
        said = strip_wake(text) or text
        if not self.api_key:
            self.say(small_talk(said, self.addr))
            if not self.hinted:
                self.hinted = True; self.log_line('SYS', 'For full conversation, put your Anthropic API key in api_key.txt (see README).')
            return
        self.chatting = True; self.history.append({'role': 'user', 'content': said}); self.history = self.history[-12:]
        while self.history and self.history[0]['role'] != 'user': self.history.pop(0)
        threading.Thread(target=self.chat_worker, daemon=True).start()

    def chat_worker(self):
        try:
            now = 'nothing is playing'
            if 0 <= self.index < len(self.songs) and self.reactor.playing:
                t, a = self.meta_of(self.songs[self.index]); now = f'now playing: {t}' + (f' by {a}' if a else '')
            system = (f"You are J.A.R.V.I.S, the calm, witty, quietly humorous British AI assistant from Iron Man, built into a music player. "
                      f"The user's address is '{self.addr}'. You are speaking aloud, so answer like a real conversation: one to three short sentences, "
                      f"natural contractions, no lists, no markdown, no emojis. You can chat about anything, give opinions and recommendations, and ask a brief "
                      f"follow-up question when it feels natural. Music control (play, pause, volume, themes) is handled by the app itself, so never claim to have "
                      f"done it yourself. Current time: {datetime.now().strftime('%A %I:%M %p')}; {now}.")
            body = json.dumps({'model': os.environ.get('JARVIS_MODEL', 'claude-haiku-5-5'), 'max_tokens': 220,
                               'system': system, 'messages': list(self.history)}).encode()
            req = urllib.request.Request('https://api.anthropic.com/v1/messages', data=body, headers={
                'x-api-key': self.api_key, 'anthropic-version': '2023-06-01', 'content-type': 'application/json'})
            with urllib.request.urlopen(req, timeout=30) as r: data = json.load(r)
            self.bridge.chat_reply.emit(''.join(b.get('text', '') for b in data.get('content', []) if b.get('type') == 'text').strip())
        except urllib.error.HTTPError as exc:
            self.bridge.error.emit(f'AI chat HTTP {exc.code}: ' + exc.read()[:160].decode(errors='replace')); self.bridge.chat_reply.emit('')
        except Exception as exc:
            self.bridge.error.emit('AI chat: ' + str(exc)[:160]); self.bridge.chat_reply.emit('')

    def on_chat_reply(self, text):
        self.chatting = False
        if not text:
            if self.history and self.history[-1]['role'] == 'user': self.history.pop()
            self.say(f"I'm having trouble reaching my network, {self.addr}."); return
        text = re.sub(r'[*_#`>]+', '', text); self.history.append({'role': 'assistant', 'content': text})
        sentences = [x for x in re.split(r'(?<=[.!?])\s+', text) if x.strip()][:5]
        self.pending_mood = mood_from_text(' '.join(sentences)); self.say(sentences)

    # ---- commands
    def send(self):
        c = self.command.text().strip(); self.command.clear()
        if c: self.execute(c)

    def execute(self, text, voice=False):
        self.log_line('YOU', text)
        if voice: self.follow_until = time.time() + 9
        intent, arg = parse_intent(text); s = self.addr; self.face_intent(intent, arg)
        if self.api_key and (intent in ('hello', 'howru', 'thanks') or (intent in CONTROL and len(strip_wake(text).split()) > 6)):
            self.converse(text); return        # open-ended talk goes to the AI; short commands stay instant
        if intent == 'wake': self.say(self.pick('wake'))
        elif intent in ('thanks', 'hello', 'howru', 'help'): self.say(self.pick(intent))
        elif intent == 'time': self.say(f"It's {datetime.now().strftime('%I:%M %p').lstrip('0')}, {s}.")
        elif intent == 'now':
            if self.index >= 0:
                t, a = self.meta_of(self.songs[self.index]); self.say(["You're listening to", self.spoken_title(t)] + ([f'by {a}'] if a else []))
            else: self.say(f'Nothing is playing at the moment, {s}.')
        elif intent == 'theme': self.cycle_theme(True, arg)
        elif intent == 'mute': self.muted = True; self.say(self.pick('mute'))
        elif intent == 'unmute': self.muted = False; self.say(self.pick('unmute'))
        elif intent in ('volset', 'volup', 'voldown'):
            if intent == 'volset' and arg is None: self.say('Tell me a volume between zero and one hundred.'); return
            n = arg if intent == 'volset' else max(0, min(100, self.volume.value() + (15 if intent == 'volup' else -15)))
            self.volume.setValue(n); self.say(self.pick('vol', n=n))
        elif intent == 'pause': self.player.pause(); self.say(self.pick('pause'))
        elif intent == 'resume':
            if self.index < 0 and self.songs: self.request_play(0)
            else: self.player.play(); self.say(self.pick('resume'))
        elif intent == 'stop': self.stop(); self.say(self.pick('stop'))
        elif intent == 'restart': self.player.setPosition(0); self.player.play()
        elif intent == 'next': self.next()
        elif intent == 'prev': self.previous()
        elif intent == 'shuffle': self.btn_shuffle.setChecked(not self.shuffle); self.say(self.pick('shuf_on' if self.shuffle else 'shuf_off'))
        elif intent == 'repeat': self.btn_repeat.setChecked(not self.repeat); self.say(self.pick('rep_on' if self.repeat else 'rep_off'))
        elif intent == 'list': self.log_line('SYS', 'TRACKS: ' + (', '.join(self.meta_of(p)[0] for p in self.songs[:35]) or 'none found'))
        elif intent == 'play_any':
            self.request_play(random.randrange(len(self.songs))) if self.songs else self.say(self.pick('empty'))
        elif intent == 'play':
            if not self.songs: self.say(self.pick('empty')); return
            score, i = self.best_match(arg)
            if score < .5: self.log_line('SYS', f'No close match for "{arg}" (best {score:.2f})'); self.face('react', 'Confused', 4.5); self.say(self.pick('nomatch'))
            else: self.request_play(i)
        else:   # a bare song title said without the word "play"
            score, i = self.best_match(arg) if self.songs and arg else (0, -1)
            self.request_play(i) if score >= .78 else self.converse(text)

    # ---- playback
    def request_play(self, i, auto=False):
        if not 0 <= i < len(self.songs): self.say(self.pick('empty')); return
        self.interrupt_speech(); self.pending_index = i; self.decode_serial += 1; self.face('face_pending')
        self.pcm = None; self.decoded_ms = 0; self.wave.set_peaks(None); self.player.stop()
        path = self.songs[i]; title, artist = self.meta_of(path)
        self.song.setText(title); self.detail.setText(artist or 'LOCAL AUDIO'); self.listw.setCurrentRow(i)
        self.decode_track(path)
        self.say([self.pick('next' if auto else 'play'), self.spoken_title(title)], after=self.start_pending)

    def start_pending(self):
        i = self.pending_index
        if i is None or not 0 <= i < len(self.songs):
            self.log_line('ERR', 'No track queued to start.'); return
        self.pending_index = None; self.index = i; self.cur_vol = 0.0     # gentle fade-in
        self.face('face_track_start')
        self.player.setSource(QUrl.fromLocalFile(str(self.songs[i]))); self.player.play()
        self.log('Now playing: ' + str(self.songs[i]))

    def decode_track(self, path):
        serial = self.decode_serial
        def work():
            try:
                pcm = ffmpeg_pcm(path, self.pcm_rate, 1500)
                bins = 1000; n = len(pcm) // bins * bins
                pk = (np.abs(pcm[:n].astype(np.int32)).reshape(bins, -1).max(1) / 32768.0) if n else np.zeros(bins)
                feats = analyze_track(pcm, self.pcm_rate) if self.use_face else None
                self.bridge.decoded.emit(serial, (pcm, pk.astype(np.float32), feats))
            except Exception as exc: self.bridge.error.emit('Audio decoder: ' + str(exc)[:160])
        threading.Thread(target=work, daemon=True).start()

    def on_decoded(self, serial, data):
        if serial != self.decode_serial: return
        self.pcm, pk, feats = data; self.decoded_ms = len(self.pcm) / self.pcm_rate * 1000; self.wave.set_peaks(pk)
        self.log('Live spectrum and waveform ready.')
        if feats:
            self.face('set_track', feats)
            self.log(f"Song mood: {feats['vibe'].upper()}  (about {feats['tempo']:.0f} BPM, energy {feats['energy']:.2f})")

    def now_ms(self):
        if self.reactor.playing: return self._pos + (time.perf_counter() - self._pos_t) * 1000
        return self._pos

    def on_position(self, n):
        self._pos = n; self._pos_t = time.perf_counter(); self.t_cur.setText(fmt_time(n)); self.t_tot.setText(fmt_time(self.duration))

    def on_playback(self, state):
        self.reactor.playing = (state == QMediaPlayer.PlayingState); self.btn_play.setText('❚❚' if self.reactor.playing else '▶')
        if state == QMediaPlayer.PausedState: self.face('react', 'Sleepy', 4.0)

    def on_media_status(self, status):
        if status == QMediaPlayer.EndOfMedia:
            if self.repeat: self.player.setPosition(0); self.player.play()
            else: self.next(auto=True)

    def toggle(self):
        if self.player.playbackState() == QMediaPlayer.PlayingState: self.player.pause()
        elif self.index >= 0: self.player.play()
        elif self.songs: self.request_play(0)

    def stop(self):
        self.face('face_idle'); self.pending_index = None; self.player.stop(); self.decode_serial += 1; self.pcm = None; self.decoded_ms = 0; self.wave.set_peaks(None)

    def next(self, auto=False):
        if not self.songs: self.say(self.pick('empty')); return
        self.request_play(random.randrange(len(self.songs)) if self.shuffle else (self.index + 1) % len(self.songs), auto)

    def previous(self):
        if not self.songs: self.say(self.pick('empty')); return
        self.request_play((self.index - 1) % len(self.songs))

    def on_volume(self, v): self.vol = v / 100; self.settings.setValue('volume', v)

    # ---- per-frame
    def tick(self):
        target = 0.0 if self.muted else self.vol * (.22 if self.speaking else 1.0)      # music ducks under JARVIS's voice
        self.cur_vol += (target - self.cur_vol) * (.25 if self.speaking else .07)
        self.audio.setVolume(max(0.0, min(1.0, self.cur_vol)))
        R = self.reactor
        if self.speaking and self.cur_pcm is not None:            # JARVIS's own voice drives the spectrum
            R.set_audio(self.cur_pcm, 16000, self.speech_player.position() + 20, voice=True)
        elif self.speaking and self.sim_voice:
            v = self.voice_level(); idx = np.arange(64); R.target = np.clip(v * (.3 + .6 * np.abs(np.sin(time.time() * 6 + idx * .7))) * np.exp(-idx / 90), 0, 1).astype(np.float32); R.level = v * .6
        else:
            R.set_audio(self.pcm, self.pcm_rate, self.now_ms() + 25)
        R.voice = R.voice * .5 + self.voice_level() * .5; R.mic *= .85; R.conv = time.time() < self.follow_until
        R.mode = (('speaking' if (self.cur_pcm is not None or self.sim_voice) else 'thinking') if self.speaking else 'thinking' if self.chatting else 'listening' if self.ears == 'HEARING' else 'thinking' if self.ears == 'PROCESSING'
                  else 'music' if R.playing else 'idle')
        if self.decoded_ms: self.wave.frac = min(1.0, self.now_ms() / self.decoded_ms); self.wave.update()
        txt, c = {'speaking': ('SPEAKING', T['b']), 'listening': ('LISTENING', '#3dffa8'), 'thinking': ('PROCESSING', T['b']),
                  'music': ('MUSIC PLAYING', T['a']), 'idle': ('SYSTEM ONLINE', '#2de0ae')}[R.mode]
        if self.ears == 'LOADING': txt, c = 'LOADING SPEECH MODEL', T['dim']
        if (txt, c) != getattr(self, '_st', None):
            self._st = (txt, c); self.status.setText('●  ' + txt); self.status.setStyleSheet(f'color:{c};')

    def on_mic_level(self, v):
        self.reactor.mic = max(self.reactor.mic, v); self.meter.setValue(int(v * 100))

    # ---- voice input
    def on_transcript(self, txt):
        self.log_line('HEARD', txt)
        if has_wake(txt): self.face('react', 'Surprised', 0.9)
        if has_wake(txt) or time.time() < self.follow_until: self.execute(txt, voice=True)

    def toggle_listening(self, on):
        self.settings.setValue('always_listening', on)
        if on:
            self.listen_stop.clear(); self.mic.setText('●  LISTENING - CLICK TO STOP')
            self.log('Microphone live. Say "Jarvis, play ..." - I will keep listening for a few seconds after I answer. Headphones help.')
            if not (self.listen_thread and self.listen_thread.is_alive()):
                self.listen_thread = threading.Thread(target=self.listen_loop, daemon=True); self.listen_thread.start()
        else:
            self.listen_stop.set(); self.mic.setText('🎙  ALWAYS LISTENING'); self.ears = 'OFF'; self.meter.setValue(0)

    def listen_loop(self):
        """Continuous capture with voice-activity endpointing; whole utterances go to Whisper."""
        try:
            import sounddevice as sd
            from faster_whisper import WhisperModel
            self.bridge.ears.emit('LOADING')
            model = WhisperModel(self.whisper_model, device='cpu', compute_type='int8')
            rate, frame = 16000, 480; q = queue.Queue(maxsize=400)
            def cb(indata, frames, t, status):
                try: q.put_nowait(indata[:, 0].copy())
                except queue.Full: pass
            floor = .006; pre = collections.deque(maxlen=10); buf = []; talking = False; quiet = 0
            with sd.InputStream(samplerate=rate, channels=1, dtype='float32', blocksize=frame, callback=cb):
                self.bridge.ears.emit('READY')
                while not self.listen_stop.is_set():
                    try: fr = q.get(timeout=.2)
                    except queue.Empty: continue
                    rms = float(np.sqrt(np.mean(fr * fr))); self.bridge.mic_level.emit(min(1.0, rms * 12))
                    if self.speaking or time.time() < self.mute_until:      # never listen to our own voice
                        buf, talking = [], False; pre.clear(); continue
                    if not talking:
                        floor = floor * .98 + rms * .02; pre.append(fr)
                        if rms > max(.012, floor * 3.2): talking, buf, quiet = True, list(pre), 0; self.bridge.ears.emit('HEARING')
                        continue
                    buf.append(fr); quiet = 0 if rms > max(.009, floor * 2.2) else quiet + 1
                    if quiet > 24 or len(buf) > 400:                         # ~0.7 s of silence ends the sentence
                        audio = np.concatenate(buf); talking, buf = False, []; pre.clear()
                        if len(audio) < rate * .4: self.bridge.ears.emit('READY'); continue
                        self.bridge.ears.emit('PROCESSING')
                        segs, _ = model.transcribe(audio, language='en', vad_filter=True, beam_size=3,
                                                   initial_prompt=self.prompt, condition_on_previous_text=False)
                        phrase = ' '.join(s.text.strip() for s in segs).strip()
                        if phrase: self.bridge.transcript.emit(phrase)
                        self.bridge.ears.emit('READY')
        except Exception as exc:
            self.bridge.error.emit('Microphone stopped: ' + str(exc)[:160]); self.bridge.ears.emit('OFF')

    def closeEvent(self, e):
        self.listen_stop.set(); self.player.stop(); self.speech_player.stop(); super().closeEvent(e)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    win = Jarvis(); win.show()
    sys.exit(app.exec())
