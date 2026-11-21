# Chatbox

A deliberately small full-stack project: **REST API + SQL + LLM chat + authentication**.

- **REST API** — FastAPI, auto docs at `/docs`
- **SQL** — SQLite (`chatbox.db`), tables for users, conversations, messages
- **LLM chat** — any OpenAI-compatible endpoint; runs in mock mode with no key
- **Auth** — email + password (PBKDF2), JWT in an httpOnly cookie
- **Frontend** — plain HTML/CSS/JS, no build step

## Run it

```powershell
cd C:\Users\MightyMatcha\Desktop\OpenChamber\Projects\chatbox
.\run.ps1
```

`run.ps1` creates `.venv`, installs dependencies the first time, then serves the app.
(The manual equivalent is in the next section.)

Open http://127.0.0.1:8000, create an account, and chat.
The API docs are at http://127.0.0.1:8000/docs.

A demo account already exists in the local database: `demo@local.dev` / `password123`.
Delete `chatbox.db` for a clean start — it is recreated on the next launch.

<details>
<summary>Manual setup without run.ps1</summary>

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
$env:PYTHONPATH = "."
uvicorn app.main:app --reload
```

</details>

Without configuration the assistant answers in **mock mode** (a local canned reply).
To use a real model, create `.env`:

```
LLM_API_KEY=sk-...
LLM_MODEL=gpt-4o-mini
# optional, for any OpenAI-compatible provider:
# LLM_BASE_URL=https://openrouter.ai/api/v1
```

Then restart the server. `LLM_BASE_URL` + `LLM_MODEL` are all it takes to point at
Groq, Together, OpenRouter, a local llama.cpp server, and so on.

## Layout

```
run.ps1       one-command start (venv + deps + server)
app/
  main.py     REST routes and the chat flow
  db.py       SQLite schema and connection helpers
  auth.py     password hashing, JWTs, current_user dependency
  llm.py      OpenAI-compatible client + mock fallback
  models.py   pydantic request/response shapes
  config.py   .env loading and settings
web/
  index.html  auth screen + chat UI
  app.js      fetch calls against the API
  style.css   styles
chatbox.db    created on first run (ignored by git)
.secret       generated session-signing key (ignored by git)
```

## REST API

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/health` | status + whether mock mode is on |
| POST | `/api/auth/register` | create account, sets session cookie |
| POST | `/api/auth/login` | log in, sets session cookie |
| POST | `/api/auth/logout` | clear session cookie |
| GET | `/api/auth/me` | current user |
| GET | `/api/conversations` | list your chats |
| POST | `/api/conversations` | create a chat |
| DELETE | `/api/conversations/{id}` | delete a chat and its messages |
| GET | `/api/conversations/{id}/messages` | message history |
| POST | `/api/conversations/{id}/messages` | send a message, get the reply |

Every `/api/conversations/*` route requires the session cookie, so each user only
ever sees their own rows. Cookies are used by the browser; for scripts you can also
send `Authorization: Bearer <token>`.

Example with curl:

```powershell
curl.exe -c cookies.txt -X POST http://127.0.0.1:8000/api/auth/register `
  -H "Content-Type: application/json" `
  -d '{\"email\":\"a@b.co\",\"password\":\"password123\"}'

curl.exe -b cookies.txt -X POST http://127.0.0.1:8000/api/conversations `
  -H "Content-Type: application/json" -d '{}'

curl.exe -b cookies.txt -X POST http://127.0.0.1:8000/api/conversations/1/messages `
  -H "Content-Type: application/json" -d '{\"content\":\"hello\"}'
```

## Notes / next steps

- Set `APP_SECRET` in the environment (or `.env`) for a stable signing key; otherwise
  one is generated into `.secret` on first run.
- `secure=True` on the cookie is a one-line change in `app/auth.py` once you serve over HTTPS.
- Chat replies are not streamed, to keep the code short. Streaming would mean an
  SSE endpoint plus a `fetch` reader in `app.js`.
- Good first extensions: rename chats, per-user rate limiting, a token counter,
  or a `POST /api/auth/password` route.
