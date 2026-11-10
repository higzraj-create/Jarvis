# J.A.R.V.I.S Music Reactor - Mark IX

## Windows installation
1. Extract the ZIP and open CMD in this folder.
2. `py -3.13 -m venv .venv`
3. `.venv\Scripts\python.exe -m pip install -r requirements.txt`
4. For microphone commands: `.venv\Scripts\python.exe -m pip install -r requirements-voice.txt`
5. `.venv\Scripts\python.exe jarvis_music.py`

## What's new in Mark IX

### Voice that sounds natural
- Removed the heavy -12 Hz pitch drop that made the old voice sound synthetic; pace and pitch are now close to the neural voice's own delivery.
- Voice Lab (right panel): nine neural voices (British, US, Australian, Indian English), a pace slider, and a TEST button. Choices are remembered.
- JARVIS no longer repeats one canned line. Each reply has several variations, never the same one twice in a row, plus a time-aware greeting on startup.
- Tamil and Hindi titles are spoken by a native Tamil/Hindi neural voice in the middle of the English sentence. Add your own in `pronunciations.json`: `"Title": {"say": "spoken text", "voice": "ta-IN-ValluvarNeural"}`.
- Music ducks under his voice and fades in when the track starts.
- Voice lines are cached, so repeated phrases play instantly. Speech for a track is generated while the song decodes.

### Hearing you better
- Real voice-activity detection: whole sentences are captured, then transcribed (default model `base.en`, more accurate than the old `tiny`). The prompt is seeded with your song titles.
- After JARVIS answers, he keeps listening for about 9 seconds, so you can follow up without repeating "Jarvis".
- Natural phrasing works: "Jarvis, could you play Hukum", "turn it down", "what's playing", "switch to gold", "what time is it". Saying just a song title also works.
- Fuzzy wake word (Jarvis / Jervis / Jarvas ...). The mic ignores his own voice.
- Faster or slower model: set `JARVIS_WHISPER=small.en` (or `tiny.en`) before launching.

### Visuals
- Five themes (Arc, Gold, Crimson, Violet, Emerald): button on the right panel, or say "switch to gold".
- Reactor: 64 real-FFT bars with peak caps, smooth spectrum contour, bass shockwaves and particles on detected beats, arc-reactor coils, rotating degree scale, bass/mid/high meters.
- The core changes with state: standby, live spectrum, listening (mic level ring), processing, speaking (ring follows the real loudness of his voice).
- Full-track waveform you can click or drag to seek, searchable track list, colour-coded console, glass panels with corner brackets. Press F11 for fullscreen.

## Mark IX update 2

### Talk to JARVIS about anything
- Turn on ALWAYS LISTENING and say "Jarvis, ..." then just talk. He answers out loud in short, natural sentences, and keeps listening for ~12 seconds so you can reply without saying his name again. Typing in the command box works the same way.
- Short commands (play, pause, louder, next, theme ...) stay instant and never go through the AI.
- Conversation uses the Anthropic API (model `claude-haiku-5-5`, change with `JARVIS_MODEL`). Put your key in `api_key.txt` (or set `ANTHROPIC_API_KEY`). API usage is billed separately from a Claude.ai subscription and costs very little for short chats. Without a key he only has a few offline replies.

### 3D holographic emblem
- The centre is now a real 3D hologram on a continuous loop: a wire globe whose surface is pushed out by the live spectrum, three gyro rings turning on different axes with orbiting beads, and J.A.R.V.I.S lettering orbiting on a ring. A scanline sweeps over it and it flickers like a projection. It spins faster with louder music and when he speaks.

### Visualizer follows his voice too
- While JARVIS talks, the 64 bars, shockwaves and globe react to the real spectrum of his speech (the music keeps ducking underneath). When he stops, they return to the song.

## Notes
- Edge TTS needs internet; the Windows voice is the offline fallback.
- Visualizer analyses the playing file (first 25 minutes), not other apps or the microphone.
- Use headphones with always-listening so song lyrics do not trigger commands.
