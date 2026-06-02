"""
Sphere Bot - Упрощённый бот для управления Telegram-каналами
Все функции в одном файле
"""
import os
import sqlite3
import logging
import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from dotenv import load_dotenv

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Poll
from telegram.ext import (
    Application, CommandHandler, MessageHandler, CallbackQueryHandler,
    ContextTypes, filters, ChatMemberHandler
)

# ==================== КОНФИГУРАЦИЯ ====================
load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN', '8210967207:AAGyK0j-q5pafNO4QmyAX3AJqCJ7WzJ2B_g')
ADMIN_IDS = [int(x) for x in os.getenv('ADMIN_IDS', '').split(',') if x.strip()]
STATS_INTERVAL = int(os.getenv('STATS_INTERVAL', '86400'))
DATABASE_PATH = os.getenv('DATABASE_PATH', 'bot_database.db')
DEFAULT_LANGUAGE = os.getenv('DEFAULT_LANGUAGE', 'ru')
SUPPORTED_LANGUAGES = ['ru', 'en']

# ==================== ЛОГИРОВАНИЕ ====================
os.makedirs('logs', exist_ok=True)
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ==================== ПЕРЕВОДЫ ====================
TEXTS = {
    'ru': {
        'welcome': '👋 Добро пожаловать в Sphere Bot!\n\nУправляйте своими каналами: подписчики, статистика, посты.',
        'help': '/start - Главное меню\n/channels - Список каналов\n/add_channel - Добавить канал\n/stats - Статистика\n/post [текст] - Отправить пост\n/cancel - Отмена',
        'not_authorized': '❌ Нет прав.',
        'no_channels': '❌ Нет каналов. Перешлите сообщение из канала боту.',
        'channel_added': '✅ Канал добавлен: {title}',
        'channel_removed': '✅ Канал удалён',
        'channel_selected': '✅ Выбран канал: {title}',
        'channel_not_set': '❌ Сначала выберите канал в меню "Мои каналы"',
        'stats': '📊 Статистика\n👥 Подписчиков: {subscribers}\n➕ Новых: {new_subs}\n➖ Отписок: {unsubs}',
        'post_sent': '✅ Пост отправлен',
        'post_error': '❌ Ошибка: {error}',
        'language_changed': '✅ Язык: {language}',
        'no_text': '❌ Укажите текст: /post текст',
        'button_format': '❌ Формат: кнопка|ссылка, кнопка2|ссылка2',
    },
    'en': {
        'welcome': '👋 Welcome to Sphere Bot!\nManage your channels: subscribers, stats, posts.',
        'help': '/start - Main menu\n/channels - List channels\n/add_channel - Add channel\n/stats - Statistics\n/post [text] - Send post\n/cancel - Cancel',
        'not_authorized': '❌ No permission.',
        'no_channels': '❌ No channels. Forward a message from your channel to the bot.',
        'channel_added': '✅ Channel added: {title}',
        'channel_removed': '✅ Channel removed',
        'channel_selected': '✅ Selected channel: {title}',
        'channel_not_set': '❌ Select a channel in "My Channels" first',
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

# ==================== СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ====================
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
        await update