"""
Sphere Bot - С поддержкой прокси для России
"""
import os
import sqlite3
import logging
from datetime import datetime
from typing import Dict, List, Optional
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ChatMemberHandler
)
from telegram.request import HTTPXRequest
import httpx

load_dotenv()

# ========== НАСТРОЙКИ ПРОКСИ ==========
# Варианты прокси (выберите один, раскомментируйте):

# 1. SOCKS5 прокси (купить на @ProxyBot или @socks_proxy_bot)
# PROXY_URL = "socks5://логин:пароль@ip:порт"

# 2. HTTP прокси
# PROXY_URL = "http://логин:пароль@ip:порт"

# 3. Если используете VPN на компьютере - прокси не нужен
PROXY_URL = os.getenv('PROXY_URL', None)

# 4. Альтернатива: использовать API через бота-посредника (см. ниже)

# ========== ОСТАЛЬНАЯ КОНФИГУРАЦИЯ ==========
BOT_TOKEN = os.getenv('BOT_TOKEN', '8210967207:AAGyK0j-q5pafNO4QmyAX3AJqCJ7WzJ2B_g')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
STATS_INTERVAL = int(os.getenv('STATS_INTERVAL', '86400'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_database.db')
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'ru')
SUPPORTED_LANGUAGES = ['ru', 'en']

os.makedirs('logs', exist_ok=True)
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ==================== ПЕРЕВОДЫ ====================
TEXTS = {
    'ru': {
        'welcome': '👋 Добро пожаловать в Sphere Bot!\nУправляйте каналами: подписчики, статистика, посты.',
        'help': '/start - Меню\n/channels - Каналы\n/add_channel - Добавить\n/stats - Статистика\n/post текст - Пост\n/cancel - Отмена',
        'not_authorized': '❌ Нет прав.',
        'no_channels': '❌ Нет каналов. Перешлите сообщение из канала боту.',
        'channel_added': '✅ Канал добавлен: {title}',
        'channel_removed': '✅ Канал удалён',
        'channel_selected': '✅ Выбран: {title}',
        'channel_not_set': '❌ Выберите канал в "Мои каналы"',
        'stats': '📊 Статистика\n👥 Подписчиков: {subscribers}\n➕ Новых: {new_subs}\n➖ Отписок: {unsubs}',
        'post_sent': '✅ Пост отправлен',
        'post_error': '❌ Ошибка: {error}',
        'language_changed': '✅ Язык: {language}',
        'no_text': '❌ Укажите текст: /post текст',
        'button_format': '❌ Формат: кнопка|ссылка, кнопка2|ссылка2',
    },
    'en': {
        'welcome': '👋 Welcome to Sphere Bot!\nManage channels: subscribers, stats, posts.',
        'help': '/start - Menu\n/channels - List\n/add_channel - Add\n/stats - Stats\n/post text - Post\n/cancel - Cancel',
        'not_authorized': '❌ No permission.',
        'no_channels': '❌ No channels. Forward a message from your channel.',
        'channel_added': '✅ Channel added: {title}',
        'channel_removed': '✅ Channel removed',
        'channel_selected': '✅ Selected: {title}',
        'channel_not_set': '❌ Select a channel in "My Channels"',
        'stats': '📊 Statistics\n👥 Subscribers: {subscribers}\n➕ New: {new_subs}\n➖ Unsubscribed: {unsubs}',
        'post_sent': '✅ Post sent',
        'post_error': '❌ Error: {error}',
        'language_changed': '✅ Language: {language}',
        'no_text': '❌ Provide text: /post text',
        'button_format': '❌ Format: button|url, button2|url2',
    }
}

def get_text(user_id: int, key: str) -> str:
    lang = db.get_user_language(user_id) if 'db' in globals() else DEFAULT_LANGUAGE
    return TEXTS.get(lang, TEXTS['ru']).get(key, key)

# ==================== БАЗА ДАННЫХ ====================
class Database:
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.executescript('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    language TEXT DEFAULT 'ru',
                    current_channel TEXT
                );
                CREATE TABLE IF NOT EXISTS channels (
                    channel_id TEXT PRIMARY KEY,
                    title TEXT,
                    username TEXT,
                    admin_id INTEGER
                );
                CREATE TABLE IF NOT EXISTS user_channels (
                    user_id INTEGER,
                    channel_id TEXT,
                    PRIMARY KEY (user_id, channel_id)
                );
                CREATE TABLE IF NOT EXISTS stats (
                    channel_id TEXT,
                    date TEXT,
                    new_subs INTEGER DEFAULT 0,
                    unsubs INTEGER DEFAULT 0,
                    PRIMARY KEY (channel_id, date)
                );
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    channel_id TEXT,
                    user_id INTEGER,
                    action TEXT,
                    username TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            ''')
    
    def get_user_language(self, user_id: int) -> str:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('SELECT language FROM users WHERE user_id = ?', (user_id,))
            row = cur.fetchone()
            return row[0] if row else DEFAULT_LANGUAGE
    
    def set_user_language(self, user_id: int, lang: str):
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute('INSERT OR REPLACE INTO users (user_id, language) VALUES (?, ?)', (user_id, lang))
    
    def get_current_channel(self, user_id: int) -> Optional[str]:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('SELECT current_channel FROM users WHERE user_id = ?', (user_id,))
            row = cur.fetchone()
            return row[0] if row else None
    
    def set_current_channel(self, user_id: int, channel_id: str):
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute('INSERT OR REPLACE INTO users (user_id, current_channel) VALUES (?, ?)', (user_id, channel_id))
    
    def add_channel(self, channel_id: str, title: str, username: str, admin_id: int) -> bool:
        try:
            with sqlite3.connect(DATABASE_PATH) as conn:
                conn.execute('INSERT INTO channels (channel_id, title, username, admin_id) VALUES (?, ?, ?, ?)',
                           (channel_id, title, username, admin_id))
                conn.execute('INSERT OR IGNORE INTO user_channels (user_id, channel_id) VALUES (?, ?)', (admin_id, channel_id))
            return True
        except sqlite3.IntegrityError:
            return False
    
    def remove_channel(self, channel_id: str, user_id: int) -> bool:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('SELECT admin_id FROM channels WHERE channel_id = ?', (channel_id,))
            row = cur.fetchone()
            if not row or row[0] != user_id:
                return False
            conn.execute('DELETE FROM channels WHERE channel_id = ?', (channel_id,))
            conn.execute('DELETE FROM user_channels WHERE channel_id = ?', (channel_id,))
        return True
    
    def get_user_channels(self, user_id: int) -> List[Dict]:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('''
                SELECT c.channel_id, c.title, c.username 
                FROM channels c JOIN user_channels uc ON c.channel_id = uc.channel_id
                WHERE uc.user_id = ?
            ''', (user_id,))
            return [{'channel_id': r[0], 'title': r[1] or r[2] or r[0], 'username': r[2]} for r in cur.fetchall()]
    
    def get_all_channel_ids(self) -> List[str]:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('SELECT channel_id FROM channels')
            return [r[0] for r in cur.fetchall()]
    
    def get_channel_admins(self, channel_id: str) -> List[int]:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('SELECT user_id FROM user_channels WHERE channel_id = ?', (channel_id,))
            return [r[0] for r in cur.fetchall()]
    
    def add_subscriber(self, channel_id: str, user_id: int, username: str):
        today = datetime.now().date().isoformat()
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute('INSERT INTO history (channel_id, user_id, action, username) VALUES (?, ?, "join", ?)',
                        (channel_id, user_id, username))
            conn.execute('''INSERT INTO stats (channel_id, date, new_subs) VALUES (?, ?, 1)
                         ON CONFLICT(channel_id, date) DO UPDATE SET new_subs = new_subs + 1''',
                        (channel_id, today))
    
    def add_unsubscriber(self, channel_id: str, user_id: int, username: str):
        today = datetime.now().date().isoformat()
        with sqlite3.connect(DATABASE_PATH) as conn:
            conn.execute('INSERT INTO history (channel_id, user_id, action, username) VALUES (?, ?, "leave", ?)',
                        (channel_id, user_id, username))
            conn.execute('''INSERT INTO stats (channel_id, date, unsubs) VALUES (?, ?, 1)
                         ON CONFLICT(channel_id, date) DO UPDATE SET unsubs = unsubs + 1''',
                        (channel_id, today))
    
    def get_stats(self, channel_id: str, days: int = 7) -> Dict:
        with sqlite3.connect(DATABASE_PATH) as conn:
            cur = conn.execute('''
                SELECT SUM(new_subs), SUM(unsubs) FROM stats 
                WHERE channel_id = ? AND date >= date('now', '-' || ? || ' days')
            ''', (channel_id, days))
            new_subs, unsubs = cur.fetchone()
            new_subs = new_subs or 0
            unsubs = unsubs or 0
            
            cur = conn.execute('''
                SELECT COUNT(*) FROM (
                    SELECT user_id, MAX(created_at) as last
                    FROM history WHERE channel_id = ?
                    GROUP BY user_id
                    HAVING last = (SELECT created_at FROM history h2 
                                   WHERE h2.channel_id = history.channel_id 
                                   AND h2.user_id = history.user_id 
                                   ORDER BY created_at DESC LIMIT 1)
                    AND (SELECT action FROM history h3 
                         WHERE h3.channel_id = history.channel_id 
                         AND h3.user_id = history.user_id 
                         ORDER BY created_at DESC LIMIT 1) = 'join'
                )
            ''', (channel_id,))
            subscribers = cur.fetchone()[0] or 0
            return {'subscribers': subscribers, 'new_subs': new_subs, 'unsubs': unsubs}

db = Database()

# ==================== СОСТОЯНИЯ ====================
user_states: Dict[int, Dict] = {}

def is_admin(user_id: int) -> bool:
    return not ADMIN_IDS or user_id in ADMIN_IDS

# ==================== ОБРАБОТЧИКИ ====================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    keyboard = [
        [InlineKeyboardButton("📢 Мои каналы", callback_data="channels")],
        [InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("✍️ Создать пост", callback_data="create_post")],
        [InlineKeyboardButton("🌐 Язык", callback_data="language")],
    ]
    await update.message.reply_text(get_text(user_id, 'welcome') + "\n\n👇 Выберите действие:",
                                   reply_markup=InlineKeyboardMarkup(keyboard))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(get_text(update.effective_user.id, 'help'))

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_states:
        del user_states[user_id]
        await update.message.reply_text("❌ Отменено")
    else:
        await update.message.reply_text("Нет активных действий")

async def channels_list(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None):
    user_id = update.effective_user.id if update.effective_user else message.from_user.id
    if not is_admin(user_id):
        await (update.message or message).reply_text(get_text(user_id, 'not_authorized'))
        return
    
    channels = db.get_user_channels(user_id)
    if not channels:
        await (update.message or message).reply_text(get_text(user_id, 'no_channels'))
        return
    
    current = db.get_current_channel(user_id)
    keyboard = []
    for ch in channels:
        marker = "✅ " if ch['channel_id'] == current else ""
        keyboard.append([InlineKeyboardButton(f"{marker}{ch['title']}", callback_data=f"select_{ch['channel_id']}")])
    keyboard.append([InlineKeyboardButton("🏠 Главное меню", callback_data="menu")])
    
    await (update.message or message).reply_text("📢 Ваши каналы:", reply_markup=InlineKeyboardMarkup(keyboard))

async def add_channel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(get_text(user_id, 'not_authorized'))
        return
    await update.message.reply_text("📝 Перешлите любое сообщение из вашего канала боту")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE, message=None, days=7):
    user_id = update.effective_user.id if update.effective_user else message.from_user.id
    if not is_admin(user_id):
        await (update.message or message).reply_text(get_text(user_id, 'not_authorized'))
        return
    
    channel_id = db.get_current_channel(user_id)
    if not channel_id:
        await (update.message or message).reply_text(get_text(user_id, 'channel_not_set'))
        return
    
    stats = db.get_stats(channel_id, days)
    text = get_text(user_id, 'stats').format(**stats)
    keyboard = [[InlineKeyboardButton("📅 7 дней", callback_data="stats_7"),
                 InlineKeyboardButton("📅 30 дней", callback_data="stats_30")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]
    await (update.message or message).reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def post_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text(get_text(user_id, 'not_authorized'))
        return
    
    channel_id = db.get_current_channel(user_id)
    if not channel_id:
        await update.message.reply_text(get_text(user_id, 'channel_not_set'))
        return
    
    if not context.args:
        await update.message.reply_text(get_text(user_id, 'no_text'))
        return
    
    text = ' '.join(context.args)
    try:
        await context.bot.send_message(chat_id=channel_id, text=text)
        await update.message.reply_text(get_text(user_id, 'post_sent'))
    except Exception as e:
        await update.message.reply_text(get_text(user_id, 'post_error').format(error=str(e)))

async def handle_forward(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    
    forward = None
    if update.message.forward_origin:
        if hasattr(update.message.forward_origin, 'chat'):
            forward = update.message.forward_origin.chat
        elif hasattr(update.message.forward_origin, 'sender_chat'):
            forward = update.message.forward_origin.sender_chat
    elif update.message.forward_from_chat:
        forward = update.message.forward_from_chat
    
    if not forward or forward.type != 'channel':
        return
    
    channel_id = str(forward.id)
    title = forward.title or channel_id
    username = forward.username
    
    try:
        bot_member = await context.bot.get_chat_member(channel_id, context.bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await update.message.reply_text("❌ Бот должен быть администратором канала")
            return
        
        if db.add_channel(channel_id, title, username, user_id):
            db.set_current_channel(user_id, channel_id)
            await update.message.reply_text(get_text(user_id, 'channel_added').format(title=title))
        else:
            await update.message.reply_text("⚠️ Канал уже добавлен")
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_states:
        return
    
    state = user_states[user_id]
    text = update.message.text
    
    if state.get('action') == 'awaiting_post':
        channel_id = state['channel_id']
        try:
            await context.bot.send_message(chat_id=channel_id, text=text)
            await update.message.reply_text(get_text(user_id, 'post_sent'))
        except Exception as e:
            await update.message.reply_text(get_text(user_id, 'post_error').format(error=str(e)))
        del user_states[user_id]

async def chat_member_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.chat_member:
        return
    
    chat_id = str(update.chat_member.chat.id)
    if chat_id not in db.get_all_channel_ids():
        return
    
    old = update.chat_member.old_chat_member.status
    new = update.chat_member.new_chat_member.status
    user = update.chat_member.new_chat_member.user
    if not user:
        return
    
    if old not in ['member', 'administrator', 'creator'] and new in ['member', 'administrator', 'creator']:
        db.add_subscriber(chat_id, user.id, user.username or user.first_name)
        for admin_id in db.get_channel_admins(chat_id):
            try:
                await context.bot.send_message(admin_id, f"✅ +1 подписчик\n👤 {user.first_name}\n🆔 {user.id}")
            except:
                pass
    elif old in ['member', 'administrator', 'creator'] and new not in ['member', 'administrator', 'creator']:
        db.add_unsubscriber(chat_id, user.id, user.username or user.first_name)
        for admin_id in db.get_channel_admins(chat_id):
            try:
                await context.bot.send_message(admin_id, f"❌ -1 подписчик\n👤 {user.first_name}\n🆔 {user.id}")
            except:
                pass

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if not is_admin(user_id):
        await query.edit_message_text(get_text(user_id, 'not_authorized'))
        return
    
    data = query.data
    
    if data == "menu":
        keyboard = [
            [InlineKeyboardButton("📢 Мои каналы", callback_data="channels")],
            [InlineKeyboardButton("➕ Добавить канал", callback_data="add_channel")],
            [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
            [InlineKeyboardButton("✍️ Создать пост", callback_data="create_post")],
            [InlineKeyboardButton("🌐 Язык", callback_data="language")],
        ]
        await query.edit_message_text(get_text(user_id, 'welcome') + "\n\n👇 Выберите действие:",
                                     reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "channels":
        channels = db.get_user_channels(user_id)
        if not channels:
            await query.edit_message_text(get_text(user_id, 'no_channels'))
            return
        current = db.get_current_channel(user_id)
        keyboard = []
        for ch in channels:
            marker = "✅ " if ch['channel_id'] == current else ""
            keyboard.append([InlineKeyboardButton(f"{marker}{ch['title']}", callback_data=f"select_{ch['channel_id']}")])
        keyboard.append([InlineKeyboardButton("🏠 Назад", callback_data="menu")])
        await query.edit_message_text("📢 Ваши каналы:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "add_channel":
        await query.edit_message_text("📝 Перешлите любое сообщение из вашего канала боту",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Назад", callback_data="menu")]]))
    
    elif data == "stats":
        channel_id = db.get_current_channel(user_id)
        if not channel_id:
            await query.edit_message_text(get_text(user_id, 'channel_not_set'))
            return
        stats = db.get_stats(channel_id, 7)
        text = get_text(user_id, 'stats').format(**stats)
        keyboard = [[InlineKeyboardButton("📅 7 дней", callback_data="stats_7"),
                     InlineKeyboardButton("📅 30 дней", callback_data="stats_30")],
                    [InlineKeyboardButton("🏠 Назад", callback_data="menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("stats_"):
        days = int(data.split("_")[1])
        channel_id = db.get_current_channel(user_id)
        if not channel_id:
            await query.edit_message_text(get_text(user_id, 'channel_not_set'))
            return
        stats = db.get_stats(channel_id, days)
        text = get_text(user_id, 'stats').format(**stats)
        keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="stats")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data == "create_post":
        channel_id = db.get_current_channel(user_id)
        if not channel_id:
            await query.edit_message_text(get_text(user_id, 'channel_not_set'))
            return
        user_states[user_id] = {'action': 'awaiting_post', 'channel_id': channel_id}
        await query.edit_message_text("✍️ Отправьте текст поста\n\nДля отмены: /cancel",
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("❌ Отмена", callback_data="menu")]]))
    
    elif data == "language":
        keyboard = [
            [InlineKeyboardButton("Русский", callback_data="lang_ru")],
            [InlineKeyboardButton("English", callback_data="lang_en")],
            [InlineKeyboardButton("🏠 Назад", callback_data="menu")],
        ]
        await query.edit_message_text("Выберите язык:", reply_markup=InlineKeyboardMarkup(keyboard))
    
    elif data.startswith("lang_"):
        lang = data.split("_")[1]
        db.set_user_language(user_id, lang)
        await query.edit_message_text(get_text(user_id, 'language_changed').format(language=lang.upper()),
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]))
    
    elif data.startswith("select_"):
        channel_id = data.replace("select_", "")
        db.set_current_channel(user_id, channel_id)
        channels = db.get_user_channels(user_id)
        ch = next((c for c in channels if c['channel_id'] == channel_id), None)
        title = ch['title'] if ch else channel_id
        await query.edit_message_text(get_text(user_id, 'channel_selected').format(title=title),
                                     reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Главное меню", callback_data="menu")]]))

async def periodic_stats(context: ContextTypes.DEFAULT_TYPE):
    for admin_id in ADMIN_IDS:
        channels = db.get_user_channels(admin_id)
        for ch in channels:
            stats = db.get_stats(ch['channel_id'], 7)
            text = f"📊 Статистика {ch['title']}:\n👥 {stats['subscribers']} (+{stats['new_subs']}/-{stats['unsubs']})"
            try:
                await context.bot.send_message(admin_id, text)
            except:
                pass

# ==================== ЗАПУСК С ПРОКСИ ====================
def main():
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN не установлен")
        return
    
    # Настройка прокси
    request_kwargs = {}
    if PROXY_URL:
        logger.info(f"Используется прокси: {PROXY_URL}")
        # Для SOCKS5 нужно установить: pip install httpx[socks]
        # Если ошибка, поставьте: pip install 'httpx[socks]'
        request_kwargs['proxy'] = PROXY_URL
    
    # Создаём кастомный клиент с прокси
    if PROXY_URL:
        http_client = httpx.AsyncClient(proxy=PROXY_URL, timeout=httpx.Timeout(30.0))
        request = HTTPXRequest(client=http_client)
    else:
        request = HTTPXRequest()
    
    app = Application.builder().token(BOT_TOKEN).request(request).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel))
    app.add_handler(CommandHandler("channels", lambda u,c: channels_list(u,c)))
    app.add_handler(CommandHandler("add_channel", add_channel_command))
    app.add_handler(CommandHandler("stats", stats_command))
    app.add_handler(CommandHandler("post", post_command))
    
    app.add_handler(MessageHandler(filters.FORWARDED, handle_forward))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(ChatMemberHandler(chat_member_handler))
    app.add_handler(CallbackQueryHandler(button_callback))
    
    if STATS_INTERVAL > 0 and app.job_queue:
        app.job_queue.run_repeating(periodic_stats, interval=STATS_INTERVAL, first=10)
    
    logger.info("Бот запущен" + (" с прокси" if PROXY_URL else ""))
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()