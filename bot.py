import os
import json
import random
import logging
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
from playwright.sync_api import sync_playwright
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    ContextTypes, filters
)

# Load config
CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
with open(CONFIG_PATH, "r") as f:
    config = json.load(f)

BOT_TOKEN = config.get("bot_token", os.environ.get("BOT_TOKEN", ""))
OWNER_ID = config.get("owner_id", 6416848944)
WEBSITE_URL = config.get("website_url", "")
LOGIN_URL = config.get("login_url", "")
NAME_POOL = config.get("name_pool", ["user"])

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store signed up users
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "users.json")

def load_users():
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, "r") as f:
                return json.load(f)
    except Exception:
        pass
    return {}

def save_users(users):
    with open(DATA_FILE, "w") as f:
        json.dump(users, f, indent=2)

users = load_users()

def generate_username():
    """Generate a random username from name pool."""
    name = random.choice(NAME_POOL)
    number = random.randint(100, 999)
    return f"{name.lower()}_{number}"

def generate_email():
    """Generate a realistic-looking email."""
    first_names = [
        "muhammad", "john", "david", "sarah", "ahmed", "mary",
        "ali", "grace", "daniel", "esther", "michael", "rachel",
        "ibrahim", "fatima", "chinedu", "amara", "yusuf", "zainab",
        "emeka", "ngozi", "tunde", "kemi", "musa", "ada",
        "sadiq", "benita", "glory", "blessing", "victor", "hauwa"
    ]
    last_names = [
        "muhammad", "smith", "johnson", "williams", "brown", "jones",
        "garcia", "miller", "davis", "wilson", "anderson", "taylor",
        "thomas", "moore", "martin", "jackson", "white", "harris",
        "clark", "lewis", "okonkwo", "adeyemi", "obinna", "nwosu",
        "ibrahim", "ali", "hassan", "osei", "mensah", "kamara"
    ]
    domains = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com"]
    
    first = random.choice(first_names)
    last = random.choice(last_names)
    domain = random.choice(domains)
    
    # Random separator: nothing, dot, or number
    separator = random.choice(["", ".", "_", str(random.randint(1, 99))])
    
    return f"{first}{separator}{last}@{domain}"

def signup_on_website(username, email="", password=""):
    """Use browser to sign up on the website."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            
            page.goto(WEBSITE_URL, timeout=30000)
            
            # Fill signup form
            username_selector = f"input[name='{config.get('username_field', 'username')}'], input#username, input[type='text']"
            page.fill(username_selector, username)
            
            if email:
                email_selector = f"input[name='{config.get('email_field', 'email')}'], input#email, input[type='email']"
                try:
                    page.fill(email_selector, email)
                except Exception:
                    pass
            
            if password:
                password_selector = f"input[name='{config.get('password_field', 'password')}'], input#password, input[type='password']"
                try:
                    page.fill(password_selector, password)
                except Exception:
                    pass
            
            # Click submit
            submit_selector = config.get("submit_button", "button[type='submit']")
            page.click(submit_selector)
            
            # Wait for response
            page.wait_for_timeout(3000)
            
            browser.close()
            return True, "Account created successfully!"
            
    except Exception as e:
        return False, f"Error: {str(e)}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command."""
    if update.message.from_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Access denied.")
        return
    
    await update.message.reply_text(
        "🤖 *Signup Bot*\n\n"
        "Commands:\n"
        "/newuser - Generate username & signup\n"
        "/signup <username> - Custom username\n"
        "/list - View all signed up users\n"
        "/config - View current settings\n"
        "/seturl <url> - Change website URL\n"
        "/test - Test browser connection",
        parse_mode="Markdown"
    )

async def new_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Auto-generate username and signup."""
    if update.message.from_user.id != OWNER_ID:
        return
    
    username = generate_username()
    email = generate_email()
    success, message = signup_on_website(username, email)
    
    if success:
        users[username] = {"status": "active", "email": email, "method": "auto"}
        save_users(users)
        await update.message.reply_text(
            f"✅ *Account Created!*\n\n"
            f"Username: `{username}`\n"
            f"Email: `{email}`\n"
            f"Website: {WEBSITE_URL}",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(f"❌ {message}")

async def signup_custom(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Signup with custom username."""
    if update.message.from_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /signup <username>")
        return
    
    username = context.args[0]
    success, message = signup_on_website(username)
    
    if success:
        users[username] = {"status": "active", "method": "custom"}
        save_users(users)
        await update.message.reply_text(f"✅ Account `{username}` created!", parse_mode="Markdown")
    else:
        await update.message.reply_text(f"❌ {message}")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all signed up users."""
    if update.message.from_user.id != OWNER_ID:
        return
    
    if not users:
        await update.message.reply_text("No users signed up yet.")
        return
    
    msg = "📋 *Signed Up Users*\n\n"
    for username, data in users.items():
        msg += f"• {username} - {data.get('status', 'unknown')}\n"
    
    msg += f"\nTotal: {len(users)} users"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def show_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current config."""
    if update.message.from_user.id != OWNER_ID:
        return
    
    await update.message.reply_text(
        f"⚙️ *Current Config*\n\n"
        f"Website: {WEBSITE_URL}\n"
        f"Login URL: {LOGIN_URL}\n"
        f"Name pool: {len(NAME_POOL)} names\n"
        f"Users signed up: {len(users)}",
        parse_mode="Markdown"
    )

async def set_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Change website URL."""
    if update.message.from_user.id != OWNER_ID:
        return
    
    if not context.args:
        await update.message.reply_text("Usage: /seturl <new_url>")
        return
    
    global WEBSITE_URL
    WEBSITE_URL = context.args[0]
    config["website_url"] = WEBSITE_URL
    
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)
    
    await update.message.reply_text(f"✅ URL updated: {WEBSITE_URL}")

async def test_connection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Test browser connection to website."""
    if update.message.from_user.id != OWNER_ID:
        return
    
    await update.message.reply_text("🔄 Testing browser connection...")
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(WEBSITE_URL, timeout=15000)
            title = page.title()
            browser.close()
            await update.message.reply_text(
                f"✅ Connection successful!\n\n"
                f"Website: {WEBSITE_URL}\n"
                f"Page title: {title}"
            )
    except Exception as e:
        await update.message.reply_text(f"❌ Connection failed: {str(e)}")

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.end_headers()

    def log_message(self, *args):
        pass

def run_health_server():
    port = int(os.environ.get("PORT", 8080))
    server = HTTPServer(("0.0.0.0", port), HealthHandler)
    server.serve_forever()

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("newuser", new_user))
    app.add_handler(CommandHandler("signup", signup_custom))
    app.add_handler(CommandHandler("list", list_users))
    app.add_handler(CommandHandler("config", show_config))
    app.add_handler(CommandHandler("seturl", set_url))
    app.add_handler(CommandHandler("test", test_connection))

    threading.Thread(target=run_health_server, daemon=True).start()

    print("🤖 Signup Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
