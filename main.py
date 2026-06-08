import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
import sqlite3
import re
import logging

# Configure the logging format engine
logging.basicConfig(
    level=logging.INFO, # Sets the threshold: ignores DEBUG, logs INFO and up
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)

# Create a designated logger instance named after this module
logger = logging.getLogger("slates_bot")

load_dotenv()

def init_db():
    conn = sqlite3.connect("slates.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS slates (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        owner_id TEXT NOT NULL,
        content TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        shared_with TEXT
        )''')
    
    conn.commit()
    conn.close()

init_db()

app = App(token=os.environ.get("SLACK_BOT_TOKEN"))

@app.command("/slates-ping")
def handle_ping_command(ack, respond, command):
    ack()

    user_id = command["user_id"]
    logger.info("/slates-ping invoked by user=%s", user_id)
    respond(f"Hello <@{user_id}>! Pong!")


@app.command("/slates")
def handle_slates_command(ack, respond, command):
    ack()
    
    user_id = command["user_id"]
    raw_text = command.get("text", "").strip()
    logger.info("/slates invoked by user=%s text=%r", user_id, raw_text)

    if not raw_text:
        logger.info("/slates missing subcommand for user=%s", user_id)
        respond("Try `/slates save <text>` or `/slates paste <id>`")
        return

    parts = raw_text.split(" ", 1)
    subcommand = parts[0].lower()
    args = parts[1] if len(parts) > 1 else ""

    conn = sqlite3.connect("slates.db")
    cursor = conn.cursor()
    if subcommand == "save":
        if not args:
            logger.info("/slates save rejected for user=%s due to empty text", user_id)
            respond("Please provide some text to save. Usage: `/slates save <text>`")
            return
        
        cursor.execute("INSERT INTO slates (owner_id, content) VALUES (?, ?)", (user_id, args))
        conn.commit()
        slate_id = cursor.lastrowid
        logger.info("Saved slate id=%s for user=%s", slate_id, user_id)
        respond(f"Saved your slate with ID: {slate_id}")

    elif subcommand == "paste":
        if not args.isdigit():
            logger.info("/slates paste rejected for user=%s invalid id=%r", user_id, args)
            respond("Please provide a valid slate ID. Usage: `/slates paste <id>`")
            return
        
        slate_id = int(args)
        logger.info("User=%s requested slate id=%s", user_id, slate_id)
        cursor.execute("SELECT content, owner_id, shared_with FROM slates WHERE id = ?", (slate_id,))
        result = cursor.fetchone()

        if result:
            content, owner_id, shared_with = result

            shared_users = set(shared_with.split(",")) if shared_with else []

            if user_id != owner_id and user_id not in shared_users:
                logger.warning("Access denied for user=%s on slate id=%s", user_id, slate_id)
                respond("You do not have permission to view this slate.")
                return
            
            logger.info("Slate id=%s delivered to user=%s", slate_id, user_id)
            respond(f"{content}")
        else:
            logger.info("Slate id=%s not found for user=%s", slate_id, user_id)
            respond(f"No slate found with ID: {slate_id}")

    elif subcommand == "delete":
        if not args.isdigit():
            logger.info("/slates delete rejected for user=%s invalid id=%r", user_id, args)
            respond("Please provide a valid slate ID. Usage: `/slates delete <id>`")
            return
        
        slate_id = int(args)
        logger.info("User=%s requested delete for slate id=%s", user_id, slate_id)
        cursor.execute("DELETE FROM slates WHERE id = ? AND owner_id = ?", (slate_id, user_id))
        conn.commit()

        if cursor.rowcount > 0:
            logger.info("Deleted slate id=%s for user=%s", slate_id, user_id)
            respond(f"Deleted slate with ID: {slate_id}")
        else:
            logger.info("Delete failed for user=%s slate id=%s", user_id, slate_id)
            respond(f"No slate found with ID: {slate_id} that belongs to you.")

    elif subcommand == "list":
        logger.info("Listing slates for user=%s", user_id)
        cursor.execute("SELECT id FROM slates WHERE owner_id = ?", (user_id,))
        slates = cursor.fetchall()
        if slates:
            slate_ids = [str(s[0]) for s in slates]
            logger.info("Found %d slates for user=%s", len(slate_ids), user_id)
            respond(f"Your slates: {', '.join(slate_ids)}")
        else:
            logger.info("No slates found for user=%s", user_id)
            respond("You don't have any saved slates yet.")

    elif subcommand == "share":
        logger.info("/slates share invoked by user=%s args=%r", user_id, args)
        pattern = r"(?P<id>\d+)\s+<@(?P<user>[A-Z0-9]+)(?:\|[^>]+)?>|(?P<id_alt>\d+)\s+@(?P<user_alt>[\w.-]+)"
        match = re.match(pattern, args)
        if not match:
            logger.info("/slates share rejected for user=%s invalid args=%r", user_id, args)
            respond("Please provide a valid slate ID and user mention. Usage: `/slates share <id> @user`")
            return
        
        slate_id = int(match.group("id") or match.group("id_alt"))
        target_user_id = match.group("user") or match.group("user_alt")

        cursor.execute("SELECT shared_with FROM slates WHERE id = ? AND owner_id = ?", (slate_id, user_id))
        result = cursor.fetchone()

        if not result:
            logger.info("Share failed for user=%s slate id=%s", user_id, slate_id)
            respond(f"No slate found with ID: {slate_id} that belongs to you.")
            return
        
        shared_with = result[0]
        if shared_with:
            shared_users = set(shared_with.split(","))
        else:
            shared_users = set()

        shared_users.add(target_user_id)
        updated_shared_with = ",".join(shared_users)

        cursor.execute("UPDATE slates SET shared_with = ? WHERE id = ?", (updated_shared_with, slate_id))
        conn.commit()
        logger.info("Shared slate id=%s from user=%s with user=%s", slate_id, user_id, target_user_id)
        respond(f"Shared slate {slate_id} with <@{target_user_id}>")

    else:
        logger.info("Unknown /slates subcommand=%r user=%s", subcommand, user_id)
        respond("Unknown subcommand. Try `/slates save <text>` or `/slates paste <id>`")

    conn.close()

@app.command("/slates-help")
def handle_slates_help_command(ack, respond):
    ack()
    logger.info("/slates-help invoked")
    help_text = (
        "Available commands:\n"
        "`/slates save <text>` - Save a new slate with the provided text.\n"
        "`/slates paste <id>` - Retrieve and display the content of a slate by its ID.\n"
        "`/slates delete <id>` - Delete a slate by its ID (only if you are the owner).\n"
        "`/slates list` - List all your saved slates with their IDs.\n"
        "`/slates share <id> @user` - Share a slate with another user by their ID and mention.\n"
    )
    respond(help_text)

@app.event("app_mention")
def handle_app_mention_events(body, say):
    user_id = body["event"]["user"]
    logger.info("app_mention event from user=%s", user_id)
    say(f"Hello <@{user_id}>! How can I assist you with your slates? Try `/slates-help` for commands.")

@app.event("message")
def handle_message_events(body, say):
    event = body.get("event", {})
    text = event.get("text", "")
    user_id = event.get("user", "")

    if "hello" in text.lower() or "hi" in text.lower():
        logger.info("message event greeting from user=%s text=%r", user_id, text)
        say(f"Hi <@{user_id}>! How can I assist you with your slates? Try `/slates-help` for commands.")

    if "67" in text:
        logger.info("message event contains '67' from user=%s text=%r", user_id, text)
        say(f"please go see some psychiatrist, you are not mentally well...")

if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    handler.start()