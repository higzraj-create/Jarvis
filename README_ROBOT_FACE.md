# J.A.R.V.I.S Music Reactor - Mark X (Robot Face)

The arc-reactor HUD has been replaced by the cute LED robot face from your CuteRobot project.
The face is alive: it blinks, looks around, follows your mouse, and its expression changes with
what you say, what JARVIS says, the song that is about to play, and the song that is playing.

## Start (Windows)
Double-click **START_JARVIS.bat**.
* First run: it finds Python 3.10 - 3.13, creates a `.venv`, installs everything (PySide6 is ~200 MB),
  then starts JARVIS. The next runs start straight away.
* No Python? Install 3.13 from python.org and tick "Add python.exe to PATH", then run the .bat again.
* **START_JARVIS_CLASSIC_HUD.bat** starts the old arc-reactor HUD instead.
* Clean reinstall: delete the `.venv` folder and run START_JARVIS.bat again.

## When does the face change?
| Moment | Face |
|---|---|
| Idle / standby | Normal, with random cute expressions; after 75 s Sleepy, after 150 s Sleeping |
| Waking up from sleep | little Surprised pop |
| JARVIS starts up | Happy |
| You speak (mic hears you) | Listening (wide mint eyes that grow with your voice) |
| Processing / AI thinking | Thinking (eyes look up and around) |
| You ask for a song, before it starts | Anticipate (eager bounce, eyes glance up) |
| The song starts | Excited burst, then the song's own mood |
| JARVIS talks | Mouth lip-syncs to his real voice loudness |
| AI chat reply | Laughing for jokes, Sad for apologies, Love, Excited, Sleepy, Thinking... picked from his words |
| Error | Confused |

**Commands:** hello = Wink - thanks = Shy - how are you = Happy - what time = Wink - what's playing = Love -
louder = Excited - quieter = Sleepy - mute = Shy - unmute = Happy - pause = Sleepy - resume = Happy -
stop = Sad - next / previous = Surprised - shuffle = Excited - repeat = Love - theme = Wink -
song not found = Confused - wake word "Jarvis" = Surprised.

**While a song plays**, JARVIS listens to it once when it loads and decides its vibe
(tempo, loudness, bass, shown in the console as "Song mood"):

| Vibe | Faces used |
|---|---|
| HYPE (fast and loud) | Excited, Dance, Laughing, Rock, Sing, Happy |
| GROOVE | Groove, Dance, Happy, Sing, Wink, Love |
| CHILL | Chill, Happy, Sing, Love, Shy, Sleepy |
| DREAMY (slow and soft) | Love, Chill, Sing, Shy, Sleepy |

Bass-heavy songs also get the headbanging **Rock** face. While playing, the face also
* bounces on every bass beat, pulses the screen frame and sends shock rings,
* shows a 64-bar LED equalizer along the bottom (real FFT) and floating music notes,
* switches face every 5 - 11 s, picking livelier faces when the music is louder than usual,
* reacts to a sudden **drop** (Excited) or a quiet **breakdown** (Love / Surprised),
* winks every ~16 beats,
* changes colour with the mood (pink for Love, red for Rock, blue for Sad...) and follows the theme colour.

## Face mood picker
On the right panel, **FACE MOOD: AUTO** lets you force any expression to preview it
(Happy, Sad, Angry, Love, Rock, Dance...). Set it back to AUTO to let JARVIS drive.
You can also click the forehead (Happy) or double-click the face (Excited).

## Customize
Everything is in the `robotface` folder:
* `robotface/moods.py` - `INTENT_FACE` (command -> expression), `POOLS` (song vibe -> expressions),
  the song analysis thresholds, and the words that make JARVIS look sad / happy / etc.
* `robotface/expressions.py` - every expression. Add a new one by copying a `_make(...)` line.
* `robotface/reactor.py` - timing (sleep after 75 s / 150 s), mood colours, the equalizer and notes.

## Notes
* `api_key.txt` is your own Anthropic key, kept as it was so AI chat keeps working. Don't share this folder
  (or zip) with anyone while it contains your key.
* The face needs no extra downloads: it is drawn with PySide6, like the rest of JARVIS.
* The original Mark IX notes are in README.md.

## Cute robot voice
Default voice is "Bubbles - very cute & soft": a young neural voice pitched way up, with harsh highs softened.
buzz with ffmpeg (no extra install). Pick another in VOICE LAB: "softer" = squeaky but not buzzy,
or the old human voices at the bottom of the list. Use the Pace slider to speed it up.
Tweak the effect in `FX_CHAINS` near the top of jarvis_music.py (`asetrate` = pitch, higher = squeakier).

## Make an installer (JARVIS_Setup.exe)
Double-click **BUILD_INSTALLER.bat** (Python 3.10-3.13 + internet needed once; it installs Inno Setup via winget
if missing). It builds `installer\JARVIS_Setup.exe` with the robot-face app icon, Start Menu and Desktop
shortcuts and an uninstaller. Installs per-user (no admin needed). Put your key in `api_key.txt` inside the
install folder (`%LOCALAPPDATA%\Programs\JARVIS`).
