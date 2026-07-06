# ani.py - Single file for Render deployment
import os
import threading
import requests
import sqlite3
import datetime
import logging
import traceback
from flask import Flask, jsonify
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# === LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === CONFIG ===
BOT_TOKEN = os.environ.get('BOT_TOKEN', '8820258117:AAHZ4nzlXfXYQURZ1wU0hbhj9bswRRvjE6c')
API_URL = "https://sher-osint-india-num-info.vercel.app/api?number={}"
OWNER_IDS = [5546171977, 8781746926]
SUPPORT_USERNAME = "@Mohtdader90"
DEVELOPER_USERNAME = "@AloneDigital"

# === DATABASE ===
def init_db():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            verified INTEGER DEFAULT 1,
            credits INTEGER DEFAULT 10,
            searches INTEGER DEFAULT 0,
            join_date TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS pending_users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            request_date TEXT
        )''')
        c.execute('''CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )''')
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('verification_required', 'false')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('free_searches', '0')")
        c.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('offer_message', '')")
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"DB init error: {e}")

init_db()

def get_user(user_id):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = c.fetchone()
        conn.close()
        return user
    except:
        return None

def add_user(user_id, username, first_name):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, join_date) VALUES (?, ?, ?, ?)",
                  (user_id, username or "User", first_name or "User", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except:
        pass

def update_credits(user_id, amount):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE users SET credits = credits + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        conn.close()
    except:
        pass

def update_searches(user_id):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE users SET searches = searches + 1 WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def get_pending_users():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM pending_users")
        users = c.fetchall()
        conn.close()
        return users
    except:
        return []

def add_pending_user(user_id, username, first_name):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("INSERT OR REPLACE INTO pending_users (user_id, username, first_name, request_date) VALUES (?, ?, ?, ?)",
                  (user_id, username or "User", first_name or "User", datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit()
        conn.close()
    except:
        pass

def verify_user(user_id):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE users SET verified = 1 WHERE user_id = ?", (user_id,))
        c.execute("DELETE FROM pending_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def reject_user(user_id):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("DELETE FROM pending_users WHERE user_id = ?", (user_id,))
        conn.commit()
        conn.close()
    except:
        pass

def get_all_users():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT * FROM users")
        users = c.fetchall()
        conn.close()
        return users
    except:
        return []

def get_all_verified_users():
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT user_id FROM users WHERE verified = 1")
        users = c.fetchall()
        conn.close()
        return users
    except:
        return []

def get_setting(key):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = c.fetchone()
        conn.close()
        return result[0] if result else None
    except:
        return None

def update_setting(key, value):
    try:
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute("UPDATE settings SET value = ? WHERE key = ?", (value, key))
        conn.commit()
        conn.close()
    except:
        pass

def is_owner(user_id):
    return user_id in OWNER_IDS

# === SAFE SEND ===
async def safe_send(update, text, reply_markup=None):
    try:
        if update and update.message:
            await update.message.reply_text(text, reply_markup=reply_markup)
        elif update and update.callback_query:
            await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
        else:
            logger.warning("No valid update")
            return False
        return True
    except Exception as e:
        logger.error(f"Safe send error: {e}")
        return False

# === COMMANDS ===

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user or not update.message:
            return
        
        user = update.effective_user
        add_user(user.id, user.username, user.first_name)
        user_data = get_user(user.id)
        verification_required = get_setting('verification_required') == 'true'
        offer_message = get_setting('offer_message') or ""
        
        credits = user_data[3] if user_data and len(user_data) > 3 else 10
        searches = user_data[4] if user_data and len(user_data) > 4 else 0
        is_verified = user_data[3] if user_data and len(user_data) > 3 else 1
        
        can_use = is_verified == 1 or not verification_required
        
        if can_use:
            keyboard = [
                [InlineKeyboardButton("🔍 Search Number", callback_data="search")],
                [InlineKeyboardButton("👤 My Profile", callback_data="profile")],
                [InlineKeyboardButton("📞 Support", callback_data="support")],
                [InlineKeyboardButton("👑 Owner", callback_data="owner")]
            ]
            if is_owner(user.id):
                keyboard.append([InlineKeyboardButton("⚙️ Owner Panel", callback_data="owner_panel")])
            
            msg = f"✅ Welcome {user.first_name}!\n\n"
            msg += f"💀 NUM INFO BOT\n"
            msg += f"💳 Credits: {credits}\n"
            msg += f"🔍 Searches: {searches}\n"
            
            if offer_message:
                msg += f"\n📢 {offer_message}\n"
            
            msg += f"\nSelect an option:"
            
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        else:
            add_pending_user(user.id, user.username, user.first_name)
            keyboard = [[InlineKeyboardButton("📞 Contact Support", url=f"https://t.me/{SUPPORT_USERNAME[1:]}")]]
            await update.message.reply_text(
                f"⏳ Hello {user.first_name}!\n\n"
                f"Your account is pending verification.\n"
                f"Contact: {SUPPORT_USERNAME}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
    except Exception as e:
        logger.error(f"Start error: {e}")

async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user or not update.message:
            return
        
        user_id = update.effective_user.id
        user_data = get_user(user_id)
        verification_required = get_setting('verification_required') == 'true'
        
        if not user_data:
            await update.message.reply_text("❌ Use /start first.")
            return
        
        is_verified = user_data[3] if len(user_data) > 3 else 1
        can_use = is_verified == 1 or not verification_required
        
        if not can_use:
            await update.message.reply_text("❌ You are not verified!")
            return
        
        credits = user_data[3] if len(user_data) > 3 else 0
        
        if credits <= 0:
            await update.message.reply_text("❌ Insufficient credits! Contact @Mohtdader90")
            return
        
        query = " ".join(context.args)
        if not query:
            await update.message.reply_text("❌ /search 9876543210")
            return
        
        update_credits(user_id, -1)
        update_searches(user_id)
        
        try:
            response = requests.get(API_URL.format(query), timeout=20)
            data = response.json()
        except Exception as e:
            update_credits(user_id, 1)
            await update.message.reply_text(f"⚠️ API Error: {str(e)[:50]}")
            return
        
        if not data.get("success"):
            update_credits(user_id, 1)
            await update.message.reply_text("❌ Number not found!")
            return
        
        details = data.get("number_detail", {})
        user_data = get_user(user_id)
        new_credits = user_data[3] if user_data and len(user_data) > 3 else 0
        
        msg = f"📞 Number: {query}\n"
        msg += f"👤 Name: {details.get('name', 'N/A')}\n"
        msg += f"📧 Email: {details.get('email', 'N/A')}\n"
        msg += f"👨‍👦 Father: {details.get('father_name', 'N/A')}\n"
        msg += f"📡 Operator: {details.get('operator', 'N/A')}\n"
        msg += f"🌐 Circle: {details.get('circle', 'N/A')}\n"
        msg += f"📍 Address: {details.get('full_address', 'N/A')}\n"
        msg += f"🏙️ City: {details.get('village_city', 'N/A')}\n"
        msg += f"📮 Pincode: {details.get('pincode', 'N/A')}\n"
        msg += f"🗺️ State: {details.get('state', 'N/A')}\n"
        msg += f"\n💳 Credits Left: {new_credits}"
        
        await update.message.reply_text(msg)
        
    except Exception as e:
        logger.error(f"Search error: {e}")

async def owner_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if update and update.callback_query:
            query = update.callback_query
            await query.answer()
            user_id = query.from_user.id
        elif update and update.message:
            user_id = update.effective_user.id
        else:
            return
        
        if not is_owner(user_id):
            if update and update.message:
                await update.message.reply_text("❌ Owner only!")
            elif update and update.callback_query:
                await update.callback_query.edit_message_text("❌ Owner only!")
            return
        
        pending = get_pending_users()
        verification_required = get_setting('verification_required') == 'true'
        free_searches = int(get_setting('free_searches') or 0)
        offer_message = get_setting('offer_message') or "No active offer"
        
        keyboard = []
        
        if verification_required and pending:
            keyboard.append([InlineKeyboardButton("📋 Pending Users", callback_data="pending_list")])
        
        status_text = "✅ ON" if verification_required else "❌ OFF"
        keyboard.append([InlineKeyboardButton(f"🔐 Verification: {status_text}", callback_data="toggle_verification")])
        
        keyboard.extend([
            [InlineKeyboardButton("👥 All Users", callback_data="all_users")],
            [InlineKeyboardButton("📊 Stats", callback_data="stats")],
            [InlineKeyboardButton("➕ Add Credits", callback_data="add_credits")],
            [InlineKeyboardButton("🎉 Free Searches", callback_data="free_searches")],
            [InlineKeyboardButton("📢 Set Offer", callback_data="set_offer")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")]
        ])
        
        msg = f"👑 Owner Panel\n\n"
        msg += f"📋 Pending Users: {len(pending) if verification_required else 'N/A (Disabled)'}\n"
        msg += f"🔐 Verification: {'ON' if verification_required else 'OFF'}\n"
        msg += f"🎉 Free Searches: {free_searches}\n"
        msg += f"📢 Offer: {offer_message[:30]}...\n\n"
        msg += f"Select an option:"
        
        if update and update.message:
            await update.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        elif update and update.callback_query:
            await update.callback_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(keyboard))
        
    except Exception as e:
        logger.error(f"Owner panel error: {e}")

# === OWNER COMMANDS ===

async def add_credits(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        if not is_owner(user_id):
            await update.message.reply_text("❌ Access denied!")
            return
        
        args = context.args
        if len(args) != 2:
            await update.message.reply_text("❌ /addcredits USER_ID AMOUNT")
            return
        
        try:
            target_id = int(args[0])
            amount = int(args[1])
            update_credits(target_id, amount)
            await update.message.reply_text(f"✅ Added {amount} credits to user {target_id}!")
        except:
            await update.message.reply_text("❌ Invalid input!")
    except Exception as e:
        logger.error(f"Add credits error: {e}")

async def free_searches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        if not is_owner(user_id):
            await update.message.reply_text("❌ Access denied!")
            return
        
        args = context.args
        if len(args) != 1:
            await update.message.reply_text("❌ /freesearches AMOUNT")
            return
        
        try:
            amount = int(args[0])
            update_setting('free_searches', str(amount))
            users = get_all_verified_users()
            for user in users:
                update_credits(user[0], amount)
            await update.message.reply_text(f"✅ Added {amount} free credits to all users!")
        except:
            await update.message.reply_text("❌ Invalid amount!")
    except Exception as e:
        logger.error(f"Free searches error: {e}")

async def set_offer(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        if not is_owner(user_id):
            await update.message.reply_text("❌ Access denied!")
            return
        
        message = " ".join(context.args)
        if not message:
            await update.message.reply_text("❌ /offer MESSAGE")
            return
        
        update_setting('offer_message', message)
        await update.message.reply_text(f"✅ Offer set:\n\n📢 {message}")
    except Exception as e:
        logger.error(f"Set offer error: {e}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.effective_user:
            return
        
        user_id = update.effective_user.id
        if not is_owner(user_id):
            await update.message.reply_text("❌ Access denied!")
            return
        
        message = " ".join(context.args)
        if not message:
            await update.message.reply_text("❌ /broadcast MESSAGE")
            return
        
        users = get_all_users()
        success = 0
        for user in users:
            try:
                await context.bot.send_message(user[0], f"📢 Broadcast\n\n{message}")
                success += 1
            except:
                pass
        
        await update.message.reply_text(f"✅ Broadcast sent to {success} users!")
    except Exception as e:
        logger.error(f"Broadcast error: {e}")

# === BUTTON HANDLER ===

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.callback_query:
            return
        
        query = update.callback_query
        await query.answer()
        user_id = query.from_user.id
        data = query.data
        
        if data == "search":
            await query.edit_message_text("Send: /search 9876543210")
        
        elif data == "profile":
            user_data = get_user(user_id)
            if user_data:
                msg = f"👤 Profile\n\n"
                msg += f"ID: {user_data[0]}\n"
                msg += f"Name: {user_data[2]}\n"
                msg += f"Credits: {user_data[3]}\n"
                msg += f"Searches: {user_data[4]}\n"
                msg += f"Joined: {user_data[5]}"
                await query.edit_message_text(msg)
            else:
                await query.edit_message_text("❌ User not found!")
        
        elif data == "support":
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="back")]]
            await query.edit_message_text(
                f"📞 Support\n\nContact: {SUPPORT_USERNAME}\nDeveloper: {DEVELOPER_USERNAME}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "owner":
            keyboard = [
                [InlineKeyboardButton("👑 Owner Panel", callback_data="owner_panel")],
                [InlineKeyboardButton("🔙 Back", callback_data="back")]
            ]
            await query.edit_message_text(
                f"👑 Owner Info\n\nOwner: {SUPPORT_USERNAME}\nDeveloper: {DEVELOPER_USERNAME}",
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        
        elif data == "owner_panel":
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            await owner_panel(update, context)
        
        elif data == "pending_list":
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            pending = get_pending_users()
            if not pending:
                await query.edit_message_text("✅ No pending users!")
                return
            
            await query.edit_message_text("📋 Pending Users:")
            for user in pending:
                keyboard = [
                    [
                        InlineKeyboardButton("✅ Approve", callback_data=f"approve_{user[0]}"),
                        InlineKeyboardButton("❌ Reject", callback_data=f"reject_{user[0]}")
                    ]
                ]
                await query.message.reply_text(
                    f"🆔 ID: {user[0]}\n👤 Name: {user[2]}\n🔹 @{user[1] if user[1] != 'NoUsername' else 'N/A'}",
                    reply_markup=InlineKeyboardMarkup(keyboard)
                )
        
        elif data.startswith("approve_"):
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            target_id = int(data.split("_")[1])
            verify_user(target_id)
            update_credits(target_id, 10)
            await query.edit_message_text(f"✅ User {target_id} verified!")
            try:
                await context.bot.send_message(target_id, "🎉 Verified! You got 10 credits!")
            except:
                pass
        
        elif data.startswith("reject_"):
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            target_id = int(data.split("_")[1])
            reject_user(target_id)
            await query.edit_message_text(f"❌ User {target_id} rejected!")
        
        elif data == "toggle_verification":
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            current = get_setting('verification_required') == 'true'
            new_value = 'false' if current else 'true'
            update_setting('verification_required', new_value)
            status = "OFF" if new_value == 'false' else "ON"
            await query.edit_message_text(f"✅ Verification {status}!")
        
        elif data == "add_credits":
            await query.edit_message_text("Send: /addcredits USER_ID AMOUNT")
        
        elif data == "free_searches":
            await query.edit_message_text("Send: /freesearches AMOUNT")
        
        elif data == "set_offer":
            await query.edit_message_text("Send: /offer MESSAGE")
        
        elif data == "broadcast":
            await query.edit_message_text("Send: /broadcast MESSAGE")
        
        elif data == "all_users":
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            users = get_all_users()
            verified = sum(1 for u in users if u[3] == 1)
            pending = get_pending_users()
            await query.edit_message_text(
                f"👥 All Users\n\n"
                f"Total: {len(users)}\n"
                f"Verified: {verified}\n"
                f"Pending: {len(pending)}"
            )
        
        elif data == "stats":
            if not is_owner(user_id):
                await query.edit_message_text("❌ Access denied!")
                return
            conn = sqlite3.connect('users.db')
            c = conn.cursor()
            c.execute("SELECT SUM(searches) FROM users")
            total_searches = c.fetchone()[0] or 0
            c.execute("SELECT SUM(credits) FROM users")
            total_credits = c.fetchone()[0] or 0
            conn.close()
            users = get_all_users()
            await query.edit_message_text(
                f"📊 Bot Stats\n\n"
                f"Users: {len(users)}\n"
                f"Searches: {total_searches}\n"
                f"Credits: {total_credits}"
            )
        
        elif data == "back":
            await start(update, context)
        
    except Exception as e:
        logger.error(f"Button handler error: {e}")
        try:
            await query.edit_message_text("⚠️ Error occurred. Try again.")
        except:
            pass

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        if not update or not update.message or not update.effective_user:
            return
        
        text = update.message.text.strip()
        if text.isdigit() and len(text) == 10:
            context.args = [text]
            await search_command(update, context)
    except Exception as e:
        logger.error(f"Handle message error: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    logger.error(f"Error: {context.error}")
    logger.error(traceback.format_exc())
    try:
        if update and update.effective_user:
            await context.bot.send_message(
                update.effective_user.id,
                "⚠️ An error occurred. Please try again."
            )
    except:
        pass

# === BOT FUNCTION ===
def run_bot():
    """Bot ko chalane ka function"""
    try:
        app = Application.builder().token(BOT_TOKEN).build()
        
        app.add_handler(CommandHandler("start", start))
        app.add_handler(CommandHandler("search", search_command))
        app.add_handler(CommandHandler("owner", owner_panel))
        app.add_handler(CommandHandler("addcredits", add_credits))
        app.add_handler(CommandHandler("freesearches", free_searches))
        app.add_handler(CommandHandler("offer", set_offer))
        app.add_handler(CommandHandler("broadcast", broadcast))
        app.add_handler(CallbackQueryHandler(button_handler))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
        app.add_error_handler(error_handler)
        
        print("🔥 Bot is running successfully!")
        print(f"👑 Owners: {OWNER_IDS}")
        app.run_polling()
        
    except Exception as e:
        logger.error(f"Bot error: {e}")
        raise

# === FLASK APP FOR RENDER ===
flask_app = Flask(__name__)

@flask_app.route('/')
def home():
    return "🤖 Bot is running 24/7!"

@flask_app.route('/health')
def health():
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }), 200

# === MAIN ===
if __name__ == '__main__':
    # Bot ko background thread mein start karo
    bot_thread = threading.Thread(target=run_bot)
    bot_thread.daemon = True  # Background thread
    bot_thread.start()
    
    # Flask server start karo
    port = int(os.environ.get('PORT', 5000))
    print(f"🚀 Flask server starting on port {port}")
    flask_app.run(host='0.0.0.0', port=port)
