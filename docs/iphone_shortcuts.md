# iPhone Shortcuts — recipes for Maez signal ingest

All Shortcuts use one action pattern:

**Get Contents of URL**
- URL: `https://api.maez.live/api/iphone/ingest`
- Method: `POST`
- Headers:
  - `X-Maez-Token`: `tpFTQtyFrjhVCSY1FlOV-k42N5LB1_n8WbmqXhUECFE`
  - `Content-Type`: `application/json`
- Request Body: `JSON` (paste the body for each shortcut below)

Where you see `<Magic Variable>` in angle brackets, tap the field and insert the matching iOS magic variable (Calendar Event Title, Current Location, Current Weather, etc.).

---

## Tier 1 — The big 3 (build these first, ~20 min)

### 1. Calendar event starting
**Automation → Event Starts**
```json
{
  "kind": "calendar",
  "data": {
    "title": "<Event Title>",
    "start": "<Event Start Date>",
    "end": "<Event End Date>",
    "location": "<Event Location>"
  }
}
```

### 2a. Arrive home
**Automation → When I Arrive → Home**
```json
{"kind": "arrive_home", "data": {}}
```

### 2b. Leave home
**Automation → When I Leave → Home**
```json
{"kind": "leave_home", "data": {}}
```

### 2c. Arrive work
**Automation → When I Arrive → Work**
```json
{"kind": "arrive_work", "data": {}}
```

### 2d. Leave work
**Automation → When I Leave → Work**
```json
{"kind": "leave_work", "data": {}}
```

### 3. Focus mode change
**Automation → Focus → When turned on → Work (one per Focus mode)**
```json
{"kind": "focus_mode", "data": {"mode": "work", "active": true}}
```
Build a pair (on + off) per mode you use: work, sleep, personal, dnd.

---

## Tier 2 — Body state (~10 min)

### 4. Morning sleep summary
**Automation → Time of Day → 8:00 AM**
Add a "Find Sleep Samples" (Health) action to pull last night's sleep, then POST.
```json
{
  "kind": "sleep",
  "data": {
    "duration_hours": <Sleep Hours>,
    "bedtime": "<Bed Start>",
    "wake": "<Bed End>"
  }
}
```

### 5. Workout end
**Automation → End of Workout**
```json
{
  "kind": "workout",
  "data": {
    "type": "<Workout Type>",
    "duration_min": <Workout Duration>,
    "distance_km": <Workout Distance>,
    "calories": <Active Energy>
  }
}
```

### 6. Mindfulness session end
**Automation → End of Mindfulness Session** (if you use Apple's Mindfulness)
```json
{"kind": "mindfulness", "data": {"duration_min": <Duration>, "app": "Mindfulness"}}
```

---

## Tier 3 — Inner life (highest personality signal per byte)

### 7. Manual note button (home screen icon)
**Shortcut (not automation) → add to Home Screen**
Step 1: *Ask for Input* → "What's on your mind?"
Step 2: POST
```json
{"kind": "manual_note", "data": {"text": "<Provided Input>"}}
```

### 8. Morning intention (home screen icon, or 7am automation)
Step 1: *Ask for Input* → "What matters today?"
Step 2: POST
```json
{"kind": "intention", "data": {"when": "morning", "text": "<Provided Input>"}}
```

### 9. Evening reflection (home screen icon, or 9pm automation)
Step 1: *Ask for Input* → "How was today?"
Step 2: POST
```json
{"kind": "reflection", "data": {"text": "<Provided Input>"}}
```

### 10. Mood check (home screen icon)
Step 1: *Choose from Menu* → options: "1 low / 2 / 3 meh / 4 good / 5 great"
Step 2: *Set Variable* → map to rating number
Step 3: POST
```json
{"kind": "mood_check", "data": {"rating": <Rating>, "note": ""}}
```

---

## Tier 4 — Ambient context (polish)

### 11. Weather check-in (morning automation or on arrive_work)
Add *Get Current Weather* action first, then POST.
```json
{
  "kind": "weather",
  "data": {
    "conditions": "<Weather Conditions>",
    "temp_c": <Temperature>,
    "place": "<City>"
  }
}
```

### 12. Commute start (CarPlay connect or on leave_home)
```json
{"kind": "commute", "data": {"mode": "drive", "duration_min": 0}}
```
Chain a second POST at *Disconnect* with actual duration for the full picture.

### 13. Currently playing (optional, can be noisy)
**Shortcut triggered manually or via Music automation**
```json
{
  "kind": "now_playing",
  "data": {
    "title": "<Current Track Title>",
    "artist": "<Current Track Artist>",
    "app": "Music"
  }
}
```

### 14. Book highlight (Apple Books — manual shortcut)
Select text in Books → Share → Run Shortcut.
```json
{
  "kind": "reading",
  "data": {
    "title": "<Book Title>",
    "author": "<Book Author>",
    "highlight": "<Shortcut Input>"
  }
}
```

### 15. Heart rate spike (advanced — HealthKit query every 30 min)
Use *Find Heart Rate Samples* → filter > 100 bpm in last 5 min.
Only POST if spike detected.
```json
{"kind": "heart_rate_spike", "data": {"bpm": <Sample>, "context": "at_rest"}}
```

### 16. With people (manual tag, home screen)
Step 1: *Select Multiple Contacts*
Step 2: POST
```json
{"kind": "with_people", "data": {"names": [<Selected Contact Names>]}}
```

---

## Suggested home screen cluster

Put these as Shortcut buttons on your Home Screen so they're one tap:

- 📝 **Tell Maez** → `manual_note`
- 🌅 **Intention** → `intention` (morning)
- 🌙 **Reflection** → `reflection` (evening)
- 😌 **Mood** → `mood_check`
- 👥 **With** → `with_people`

Put these as **Automations** (run without asking):

- Calendar events starting
- Arrive / leave home + work
- Focus mode on / off (per mode)
- Morning sleep summary
- Workout end
- Mindfulness end

---

## What to skip for now

- Battery level (noisy)
- Continuous location (privacy-heavy, low marginal signal over transitions)
- Steps goal reached (low signal)
- Screen unlock events (surveillance vibe)

---

## Troubleshooting

- **401 unauthorized** — token mismatch. Copy the value from `config/.env` exactly, no quotes.
- **400 unknown kind** — the `kind` field must match the allowlist in `skills/iphone_ingest.py`.
- **Body not parsed** — make sure "Request Body" is set to `JSON` (not Form), and the body starts with `{`.
- **Shortcut silently fails** — turn off "Ask Before Running" on automations; iOS will otherwise never fire them unattended.
