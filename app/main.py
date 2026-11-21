"""REST API + static frontend for Chatbox."""

import sqlite3

from fastapi import Depends, FastAPI, HTTPException, Response, status
from fastapi.staticfiles import StaticFiles

from . import config, llm
from .auth import (
    clear_session_cookie,
    create_token,
    current_user,
    hash_password,
    set_session_cookie,
    verify_password,
)
from .db import get_db, init_db
from .models import (
    ChatOut,
    ConversationIn,
    ConversationOut,
    Credentials,
    MessageIn,
    MessageOut,
    UserOut,
)

init_db()

app = FastAPI(
    title="Chatbox",
    description="A small REST + SQLite + auth + LLM chat app.",
    version="1.0.0",
)

CONTEXT_MESSAGES = 20  # how much history to send to the model


def to_message(row: sqlite3.Row) -> MessageOut:
    return MessageOut(
        id=row["id"], role=row["role"], content=row["content"], created_at=row["created_at"]
    )


def to_conversation(row: sqlite3.Row) -> ConversationOut:
    return ConversationOut(id=row["id"], title=row["title"], updated_at=row["updated_at"])


def load_conversation(db: sqlite3.Connection, conversation_id: int, user_id: int) -> sqlite3.Row:
    row = db.execute(
        "SELECT * FROM conversations WHERE id = ? AND user_id = ?",
        (conversation_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Conversation not found")
    return row


# --- health ------------------------------------------------------------------

@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "mock_mode": config.MOCK_MODE, "model": config.LLM_MODEL}


# --- auth --------------------------------------------------------------------

@app.post("/api/auth/register", response_model=UserOut, status_code=201)
def register(
    body: Credentials,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> UserOut:
    exists = db.execute("SELECT 1 FROM users WHERE email = ?", (body.email,)).fetchone()
    if exists:
        raise HTTPException(status.HTTP_409_CONFLICT, "That email is already registered")

    cursor = db.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (body.email, hash_password(body.password)),
    )
    db.commit()
    set_session_cookie(response, create_token(cursor.lastrowid))
    return UserOut(id=cursor.lastrowid, email=body.email)


@app.post("/api/auth/login", response_model=UserOut)
def login(
    body: Credentials,
    response: Response,
    db: sqlite3.Connection = Depends(get_db),
) -> UserOut:
    row = db.execute("SELECT * FROM users WHERE email = ?", (body.email,)).fetchone()
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Wrong email or password")

    set_session_cookie(response, create_token(row["id"]))
    return UserOut(id=row["id"], email=row["email"])


@app.post("/api/auth/logout", status_code=204)
def logout(response: Response) -> None:
    clear_session_cookie(response)


@app.get("/api/auth/me", response_model=UserOut)
def me(user: sqlite3.Row = Depends(current_user)) -> UserOut:
    return UserOut(id=user["id"], email=user["email"])


# --- conversations -----------------------------------------------------------

@app.get("/api/conversations", response_model=list[ConversationOut])
def list_conversations(
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(current_user),
) -> list[ConversationOut]:
    rows = db.execute(
        "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC, id DESC",
        (user["id"],),
    ).fetchall()
    return [to_conversation(row) for row in rows]


@app.post("/api/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(
    body: ConversationIn,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(current_user),
) -> ConversationOut:
    title = (body.title or "").strip() or "New chat"
    cursor = db.execute(
        "INSERT INTO conversations (user_id, title) VALUES (?, ?)",
        (user["id"], title[:120]),
    )
    db.commit()
    row = db.execute("SELECT * FROM conversations WHERE id = ?", (cursor.lastrowid,)).fetchone()
    return to_conversation(row)


@app.delete("/api/conversations/{conversation_id}", status_code=204)
def delete_conversation(
    conversation_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(current_user),
) -> Response:
    load_conversation(db, conversation_id, user["id"])
    db.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
    db.commit()
    return Response(status_code=204)


@app.get("/api/conversations/{conversation_id}/messages", response_model=list[MessageOut])
def list_messages(
    conversation_id: int,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(current_user),
) -> list[MessageOut]:
    load_conversation(db, conversation_id, user["id"])
    rows = db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id",
        (conversation_id,),
    ).fetchall()
    return [to_message(row) for row in rows]


@app.post("/api/conversations/{conversation_id}/messages", response_model=ChatOut, status_code=201)
async def send_message(
    conversation_id: int,
    body: MessageIn,
    db: sqlite3.Connection = Depends(get_db),
    user: sqlite3.Row = Depends(current_user),
) -> ChatOut:
    conversation = load_conversation(db, conversation_id, user["id"])

    history = db.execute(
        "SELECT role, content FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT ?",
        (conversation_id, CONTEXT_MESSAGES),
    ).fetchall()
    history = list(reversed(history))

    db.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'user', ?)",
        (conversation_id, body.content),
    )
    db.execute("UPDATE conversations SET updated_at = datetime('now') WHERE id = ?", (conversation_id,))

    # Name the chat after its first question.
    if len(history) == 0 and conversation["title"] == "New chat":
        db.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (body.content[:60], conversation_id),
        )
    db.commit()

    payload = [{"role": row["role"], "content": row["content"]} for row in history]
    payload.append({"role": "user", "content": body.content})

    try:
        answer = await llm.complete(payload)
    except llm.LLMError as exc:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc))

    if not answer:
        answer = "(The model returned an empty reply.)"

    db.execute(
        "INSERT INTO messages (conversation_id, role, content) VALUES (?, 'assistant', ?)",
        (conversation_id, answer),
    )
    db.commit()

    new_rows = db.execute(
        "SELECT * FROM messages WHERE conversation_id = ? ORDER BY id DESC LIMIT 2",
        (conversation_id,),
    ).fetchall()
    new_messages = [to_message(row) for row in reversed(new_rows)]

    conversation = load_conversation(db, conversation_id, user["id"])
    return ChatOut(conversation=to_conversation(conversation), messages=new_messages)


# --- frontend ----------------------------------------------------------------

app.mount("/", StaticFiles(directory=config.WEB_DIR, html=True), name="web")
