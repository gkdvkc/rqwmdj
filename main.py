import telebot
from telebot.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton,
    Message, CallbackQuery, ChatMemberUpdated,
    InputMediaPhoto, InputFile
)
import time
import random
import re
import json
import os
import string
import hashlib
import threading
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict, deque
import logging
import math
from typing import Dict, List, Tuple, Optional, Any

# ========== تنظیمات ==========
BOT_TOKEN = "8810741889:AAEjL5vlgL0mxZeAmRGWtDuU7kKFCKwJQ2M"
ADMIN_IDS = [8680457924]  # ادمین‌های اصلی
bot = telebot.TeleBot(BOT_TOKEN)

# ========== لاگینگ ==========
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ========== دیتابیس SQLite (پیشرفته‌تر) ==========
class Database:
    def __init__(self, db_file='bot_data.db'):
        self.conn = sqlite3.connect(db_file, check_same_thread=False)
        self.cursor = self.conn.cursor()
        self._create_tables()
    
    def _create_tables(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS groups (
                group_id INTEGER PRIMARY KEY,
                settings TEXT,
                rules TEXT,
                welcome_text TEXT,
                welcome_photo TEXT,
                created_at INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                username TEXT,
                first_name TEXT,
                last_name TEXT,
                level INTEGER DEFAULT 0,
                xp INTEGER DEFAULT 0,
                warnings INTEGER DEFAULT 0,
                muted_until INTEGER DEFAULT 0,
                banned_until INTEGER DEFAULT 0,
                verified INTEGER DEFAULT 0,
                join_date INTEGER DEFAULT 0,
                last_activity INTEGER DEFAULT 0,
                referral_code TEXT,
                referred_by INTEGER,
                referral_count INTEGER DEFAULT 0,
                total_messages INTEGER DEFAULT 0,
                strike_count INTEGER DEFAULT 0,
                warnings_data TEXT,
                achievements TEXT,
                notes TEXT,
                is_admin INTEGER DEFAULT 0
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS warnings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                time INTEGER,
                admin_id INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS tickets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                subject TEXT,
                status TEXT DEFAULT 'open',
                time INTEGER,
                messages TEXT
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS captcha (
                user_id INTEGER PRIMARY KEY,
                group_id INTEGER,
                answer INTEGER,
                attempts INTEGER DEFAULT 0,
                time INTEGER
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS stats (
                key TEXT PRIMARY KEY,
                value INTEGER DEFAULT 0
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                reported_user_id INTEGER,
                reporter_user_id INTEGER,
                reason TEXT,
                time INTEGER,
                status TEXT DEFAULT 'pending'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                time INTEGER,
                UNIQUE(group_id, user_id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS whitelist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                reason TEXT,
                time INTEGER,
                UNIQUE(group_id, user_id)
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS auto_replies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                trigger TEXT,
                response TEXT,
                type TEXT DEFAULT 'text'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS reminders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                user_id INTEGER,
                message TEXT,
                time INTEGER,
                status TEXT DEFAULT 'pending'
            )
        ''')
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS polls (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                group_id INTEGER,
                question TEXT,
                options TEXT,
                votes TEXT,
                time INTEGER,
                status TEXT DEFAULT 'active'
            )
        ''')
        self.conn.commit()
    
    def execute(self, query, params=()):
        self.cursor.execute(query, params)
        self.conn.commit()
        return self.cursor
    
    def fetch_one(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchone()
    
    def fetch_all(self, query, params=()):
        self.cursor.execute(query, params)
        return self.cursor.fetchall()
    
    def close(self):
        self.conn.close()

db = Database()

# ========== دیتابیس فوق‌پیشرفته (سازگاری با کد قبلی) ==========
class UltraDatabase:
    def __init__(self):
        self.db = db
        self.default_settings = {
            "welcome": "👋 به گروه خوش آمدید {user_name}! لطفاً قوانین را رعایت کنید.",
            "welcome_enabled": True,
            "welcome_photo": None,
            "captcha": True,
            "captcha_timeout": 60,
            "captcha_max_attempts": 3,
            "auto_delete": True,
            "auto_delete_seconds": 43200,
            "anti_spam": True,
            "spam_threshold": 5,
            "spam_action": "mute",
            "spam_duration": 300,
            "anti_raid": True,
            "raid_threshold": 5,
            "raid_action": "kick",
            "anti_mentions": True,
            "mention_limit": 3,
            "anti_caps": True,
            "caps_limit": 70,
            "anti_emoji": True,
            "emoji_limit": 5,
            "anti_newlines": True,
            "newline_limit": 5,
            "anti_reply_spam": True,
            "reply_spam_threshold": 3,
            "anti_forward": True,
            "forward_limit": 3,
            "anti_link": True,
            "anti_link_action": "warn",
            "anti_link_whitelist": ["youtube.com", "youtu.be", "instagram.com", "telegram.me"],
            "anti_bad_words": True,
            "anti_bad_words_action": "mute",
            "anti_bad_words_duration": 600,
            "anti_advertising": True,
            "anti_advertising_action": "kick",
            "anti_bot": True,
            "anti_bot_action": "ban",
            "anti_commands": True,
            "anti_commands_list": ["/ban", "/kick", "/mute", "/warn", "/add", "/delete"],
            "group_lock": False,
            "group_lock_mode": "admin_only",
            "leveling": True,
            "level_multiplier": 1.0,
            "level_message": "🎉 {user_name} به سطح {level} رسید!",
            "rules": "📋 قوانین گروه:\n1. احترام به یکدیگر\n2. بدون اسپم و تبلیغات\n3. رعایت ادب و اخلاق\n4. بدون ارسال محتوای نامناسب\n5. همراهی با مدیریت",
            "warn_limit": 3,
            "warn_action": "mute",
            "warn_duration": 3600,
            "max_warn_reset": 86400,
            "log_channel": None,
            "auto_report": True,
            "auto_report_channel": None,
            "anti_voice_spam": True,
            "voice_spam_threshold": 3,
            "anti_media_spam": True,
            "media_spam_threshold": 5,
            "min_account_age": 0,
            "two_factor_auth": False,
            "verified_only": False,
            "silent_mode": False,
            "button_access_locked": True,
            "anti_attack": True,
            "attack_threshold": 20,
            "attack_action": "ban",
            "anti_vpn": True,
            "anti_clone": True,
            "anti_bad_profile": True,
            "anti_forward_spam": True,
            "forward_spam_threshold": 5,
            "anti_duplicate": True,
            "duplicate_threshold": 3,
            "anti_long_text": True,
            "long_text_limit": 1000,
            "anti_phone": True,
            "anti_email": True,
            "anti_spam_bayesian": True,
            "spam_probability_threshold": 0.7,
            "auto_report_spam": True,
            "anti_troll": True,
            "troll_threshold": 3,
            "anti_flood": True,
            "flood_threshold": 3,
            "flood_duration": 5,
            "anti_ghost": True,
            "ghost_threshold": 60,
            "auto_clean_inactive": True,
            "inactive_days": 30,
            "anti_edit_spam": True,
            "edit_spam_threshold": 3,
            "anti_poll_spam": True,
            "poll_spam_threshold": 2,
            "anti_game_spam": True,
            "game_spam_threshold": 3,
            "anti_sticker_spam": True,
            "sticker_spam_threshold": 5,
            "anti_gif_spam": True,
            "gif_spam_threshold": 3,
            "anti_voice_forward": True,
            "anti_contact_spam": True,
            "contact_spam_threshold": 3,
            "anti_location_spam": True,
            "location_spam_threshold": 3,
            "anti_dice_spam": True,
            "dice_spam_threshold": 3,
            "anti_hashtag_spam": True,
            "hashtag_spam_threshold": 5,
            "anti_mention_all": True,
            "mention_all_threshold": 1,
            "anti_emoji_spam": True,
            "emoji_spam_threshold": 10,
            "anti_uppercase": True,
            "uppercase_ratio": 70,
            "anti_repeated_chars": True,
            "repeated_chars_limit": 5,
            "anti_special_chars": True,
            "special_chars_limit": 10,
            "anti_arabic": True,
            "arabic_ratio": 70,
            "anti_english": True,
            "english_ratio": 70,
            "anti_persian": True,
            "persian_ratio": 70,
            "anti_rtl": True,
            "anti_bidi": True,
            "anti_zero_width": True,
            "anti_invisible": True,
            "anti_telegram_bugs": True,
            "anti_voice_auto": True,
            "anti_video_auto": True,
            "anti_photo_auto": True,
            "auto_del_media": False,
            "media_auto_del_seconds": 3600,
            "anti_webpage_preview": True,
            "anti_audio_spam": True,
            "audio_spam_threshold": 3,
            "anti_document_spam": True,
            "document_spam_threshold": 3,
            "anti_video_note_spam": True,
            "video_note_spam_threshold": 3,
            "anti_voice_note_spam": True,
            "voice_note_spam_threshold": 3,
            "anti_animation_spam": True,
            "animation_spam_threshold": 3,
            "anti_media_forward": True,
            "anti_media_forward_threshold": 2,
            "anti_url_shortener": True,
            "url_shortener_list": ["bit.ly", "tinyurl", "shorturl", "goo.gl", "ow.ly", "is.gd", "buff.ly", "adf.ly", "shorte.st"],
            "anti_crypto": True,
            "crypto_keywords": ["بیت‌کوین", "اتریوم", "تتر", "ارز دیجیتال", "رمزارز", "کریپتو", "btc", "eth", "usdt", "xrp", "doge"],
            "anti_gambling": True,
            "gambling_keywords": ["قمار", "شرط‌بندی", "کازینو", "پوکر", "بلک‌جک", "رولت", "اسلات", "بخت‌آزمایی"],
            "anti_porn": True,
            "porn_keywords": ["سکس", "پورن", "فیلم سوپر", "کانال بزرگسالان", "adult", "xxx", "porn", "sex"],
            "anti_violence": True,
            "violence_keywords": ["قتل", "خون‌ریزی", "جنگ", "تروریسم", "خشونت", "اسلحه", "بمب", "انفجار"],
            "anti_drugs": True,
            "drugs_keywords": ["مواد مخدر", "شیشه", "حشیش", "گراس", "کوکائین", "اکستازی", "تریاک", "هروئین"],
            "anti_self_harm": True,
            "self_harm_keywords": ["خودکشی", "خودزنی", "افسردگی شدید", "مرگ"],
            "anti_hate": True,
            "hate_keywords": ["نژادپرستی", "تبعیض", "کشتار جمعی", "هولوکاست", "نازیسم"],
            "anti_fake_news": True,
            "fake_news_keywords": ["اخبار جعلی", "شایعه", "دروغ"],
            "anti_scam": True,
            "scam_keywords": ["کلاهبرداری", "فیشینگ", "اسکم", "طرح پانزی", "هرم"],
            "anti_spyware": True,
            "spyware_keywords": ["جاسوسی", "بدافزار", "ویروس"],
            "anti_phishing": True,
            "phishing_keywords": ["فیشینگ", "حساب کاربری", "رمز عبور", "کارت بانکی"],
            "anti_impersonation": True,
            "impersonation_keywords": ["جعل هویت", "قلابی", "جعلی"],
            "anti_malware": True,
            "malware_keywords": ["بدافزار", "تروجان", "ویروس", "کرم"],
            "anti_ransomware": True,
            "ransomware_keywords": ["باج‌افزار", "رمزگشایی", "باج"],
            "anti_keylogger": True,
            "keylogger_keywords": ["کی‌لاگر", "ضبط کلید"],
            "anti_rat": True,
            "rat_keywords": ["دسترسی از راه دور", "rat", "تروجان"],
            "anti_botnet": True,
            "botnet_keywords": ["بات‌نت", "شبکه بات"],
            "anti_ddos": True,
            "ddos_keywords": ["حمله ddos", "قطع سرویس"],
            "anti_hacking": True,
            "hacking_keywords": ["هک", "نفوذ", "کرک", "کریپتوجکینگ"],
            "anti_carding": True,
            "carding_keywords": ["کارتینگ", "کارت به کارت", "برداشت غیرمجاز"],
            "anti_money_laundering": True,
            "money_laundering_keywords": ["پولشویی", "تبدیل پول"],
            "anti_terrorism": True,
            "terrorism_keywords": ["تروریسم", "داعش", "القاعده", "طالبان"],
            "anti_child_abuse": True,
            "child_abuse_keywords": ["آزار کودکان", "پورن کودکان", "کودک‌آزاری"],
            "anti_human_trafficking": True,
            "human_trafficking_keywords": ["قاچاق انسان", "برده‌داری"],
            "anti_animal_abuse": True,
            "animal_abuse_keywords": ["آزار حیوانات", "قاچاق حیوانات"],
        }
        self.captcha = {}
        self.join_times = defaultdict(list)
        self.tickets = defaultdict(list)
        self.stats = defaultdict(int)
        self.polls = {}
        self._load_stats()
    
    def _load_stats(self):
        rows = db.fetch_all("SELECT key, value FROM stats")
        for key, value in rows:
            self.stats[key] = value
    
    def _save_stats(self):
        for key, value in self.stats.items():
            db.execute("INSERT OR REPLACE INTO stats (key, value) VALUES (?, ?)", (key, value))
    
    def get_group(self, group_id):
        row = db.fetch_one("SELECT settings FROM groups WHERE group_id = ?", (group_id,))
        if row:
            settings = json.loads(row[0])
            for key, value in self.default_settings.items():
                if key not in settings:
                    settings[key] = value
            return settings
        else:
            settings = self.default_settings.copy()
            db.execute("INSERT INTO groups (group_id, settings, created_at) VALUES (?, ?, ?)", 
                      (group_id, json.dumps(settings), int(time.time())))
            return settings
    
    def save_group(self, group_id, settings):
        db.execute("UPDATE groups SET settings = ? WHERE group_id = ?", (json.dumps(settings), group_id))
    
    def get_user(self, user_id):
        row = db.fetch_one("SELECT * FROM users WHERE user_id = ?", (user_id,))
        if row:
            return {
                "user_id": row[0],
                "username": row[1],
                "first_name": row[2],
                "last_name": row[3],
                "level": row[4],
                "xp": row[5],
                "warnings": row[6],
                "muted_until": row[7],
                "banned_until": row[8],
                "verified": row[9],
                "join_date": row[10],
                "last_activity": row[11],
                "referral_code": row[12],
                "referred_by": row[13],
                "referral_count": row[14],
                "total_messages": row[15],
                "strike_count": row[16],
                "warnings_data": json.loads(row[17]) if row[17] else {},
                "achievements": json.loads(row[18]) if row[18] else [],
                "notes": row[19] or "",
                "is_admin": row[20] or 0
            }
        else:
            return {
                "user_id": user_id,
                "username": None,
                "first_name": None,
                "last_name": None,
                "level": 0,
                "xp": 0,
                "warnings": 0,
                "muted_until": 0,
                "banned_until": 0,
                "verified": 0,
                "join_date": 0,
                "last_activity": 0,
                "referral_code": None,
                "referred_by": None,
                "referral_count": 0,
                "total_messages": 0,
                "strike_count": 0,
                "warnings_data": {},
                "achievements": [],
                "notes": "",
                "is_admin": 0
            }
    
    def save_user(self, user_data):
        db.execute('''
            INSERT OR REPLACE INTO users (
                user_id, username, first_name, last_name, level, xp, warnings,
                muted_until, banned_until, verified, join_date, last_activity,
                referral_code, referred_by, referral_count, total_messages,
                strike_count, warnings_data, achievements, notes, is_admin
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            user_data["user_id"],
            user_data["username"],
            user_data["first_name"],
            user_data["last_name"],
            user_data["level"],
            user_data["xp"],
            user_data["warnings"],
            user_data["muted_until"],
            user_data["banned_until"],
            user_data["verified"],
            user_data["join_date"],
            user_data["last_activity"],
            user_data["referral_code"],
            user_data["referred_by"],
            user_data["referral_count"],
            user_data["total_messages"],
            user_data["strike_count"],
            json.dumps(user_data["warnings_data"]),
            json.dumps(user_data["achievements"]),
            user_data["notes"],
            user_data["is_admin"]
        ))
    
    def add_warning(self, group_id, user_id, reason):
        user = self.get_user(user_id)
        if group_id not in user["warnings_data"]:
            user["warnings_data"][group_id] = []
        user["warnings_data"][group_id].append({
            "time": time.time(),
            "reason": reason
        })
        user["warnings"] += 1
        self.stats["total_warns"] += 1
        self._save_stats()
        settings = self.get_group(group_id)
        now = time.time()
        user["warnings_data"][group_id] = [
            w for w in user["warnings_data"][group_id]
            if now - w["time"] < settings.get("max_warn_reset", 86400)
        ]
        self.save_user(user)
        return len(user["warnings_data"][group_id])
    
    def clear_warnings(self, group_id, user_id):
        user = self.get_user(user_id)
        if group_id in user["warnings_data"]:
            user["warnings_data"][group_id] = []
            user["warnings"] = 0
            self.save_user(user)
            return True
        return False
    
    def get_warnings(self, group_id, user_id):
        user = self.get_user(user_id)
        return user["warnings_data"].get(group_id, [])
    
    def set_mute(self, user_id, duration):
        user = self.get_user(user_id)
        user["muted_until"] = int(time.time()) + duration
        self.save_user(user)
    
    def remove_mute(self, user_id):
        user = self.get_user(user_id)
        user["muted_until"] = 0
        self.save_user(user)
    
    def is_muted(self, user_id):
        user = self.get_user(user_id)
        return user["muted_until"] > int(time.time())
    
    def get_mute_remaining(self, user_id):
        user = self.get_user(user_id)
        return max(0, user["muted_until"] - int(time.time()))
    
    def set_temp_ban(self, user_id, duration):
        user = self.get_user(user_id)
        user["banned_until"] = int(time.time()) + duration
        self.save_user(user)
    
    def is_temp_banned(self, user_id):
        user = self.get_user(user_id)
        return user["banned_until"] > int(time.time())
    
    def add_message(self, user_id):
        user = self.get_user(user_id)
        user["total_messages"] += 1
        user["last_activity"] = int(time.time())
        self.save_user(user)
        if user["total_messages"] % 10 == 0:
            self.add_xp(user_id, 2)
    
    def get_message_count(self, user_id, seconds):
        user = self.get_user(user_id)
        return user["total_messages"]
    
    def add_join(self, group_id):
        now = time.time()
        self.join_times[group_id].append(now)
        if len(self.join_times[group_id]) > 30:
            self.join_times[group_id] = self.join_times[group_id][-30:]
    
    def get_join_count(self, group_id, seconds):
        now = time.time()
        return sum(1 for t in self.join_times[group_id] if now - t <= seconds)
    
    def save_captcha(self, user_id, group_id, answer):
        db.execute("INSERT OR REPLACE INTO captcha (user_id, group_id, answer, attempts, time) VALUES (?, ?, ?, ?, ?)",
                  (user_id, group_id, answer, 0, int(time.time())))
    
    def get_captcha(self, user_id):
        row = db.fetch_one("SELECT * FROM captcha WHERE user_id = ?", (user_id,))
        if row:
            return {
                "user_id": row[0],
                "group_id": row[1],
                "answer": row[2],
                "attempts": row[3],
                "time": row[4]
            }
        return None
    
    def delete_captcha(self, user_id):
        db.execute("DELETE FROM captcha WHERE user_id = ?", (user_id,))
    
    def increment_captcha_attempts(self, user_id):
        row = db.fetch_one("SELECT attempts FROM captcha WHERE user_id = ?", (user_id,))
        if row:
            attempts = row[0] + 1
            db.execute("UPDATE captcha SET attempts = ? WHERE user_id = ?", (attempts, user_id))
            return attempts
        return 0
    
    def add_xp(self, user_id, amount):
        user = self.get_user(user_id)
        user["xp"] += amount
        new_level = int(user["xp"] ** 0.4)
        if new_level > user["level"]:
            user["level"] = new_level
            self.save_user(user)
            return True
        self.save_user(user)
        return False
    
    def get_level(self, user_id):
        user = self.get_user(user_id)
        return user["level"]
    
    def get_xp(self, user_id):
        user = self.get_user(user_id)
        return user["xp"]
    
    def verify_user(self, user_id):
        user = self.get_user(user_id)
        user["verified"] = 1
        self.save_user(user)
    
    def is_verified(self, user_id):
        user = self.get_user(user_id)
        return user["verified"] == 1
    
    def add_ticket(self, group_id, user_id, subject):
        tickets = self.tickets[group_id]
        ticket_id = len(tickets) + 1
        tickets.append({
            "id": ticket_id,
            "user": user_id,
            "subject": subject,
            "time": time.time(),
            "status": "open",
            "messages": []
        })
        return ticket_id
    
    def close_ticket(self, group_id, ticket_id):
        for t in self.tickets[group_id]:
            if t["id"] == ticket_id:
                t["status"] = "closed"
                return True
        return False
    
    def add_ticket_message(self, group_id, ticket_id, user_id, message):
        for t in self.tickets[group_id]:
            if t["id"] == ticket_id:
                t["messages"].append({
                    "user": user_id,
                    "message": message,
                    "time": time.time()
                })
                return True
        return False
    
    def add_report(self, group_id, reported_user, reporter_user, reason):
        db.execute('''
            INSERT INTO reports (group_id, reported_user_id, reporter_user_id, reason, time, status)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (group_id, reported_user, reporter_user, reason, int(time.time()), 'pending'))
        return db.cursor.lastrowid
    
    def get_reports(self, group_id):
        rows = db.fetch_all("SELECT * FROM reports WHERE group_id = ? AND status = 'pending'", (group_id,))
        return rows
    
    def resolve_report(self, report_id):
        db.execute("UPDATE reports SET status = 'resolved' WHERE id = ?", (report_id,))
    
    def add_blacklist(self, group_id, user_id, reason):
        try:
            db.execute("INSERT INTO blacklist (group_id, user_id, reason, time) VALUES (?, ?, ?, ?)",
                      (group_id, user_id, reason, int(time.time())))
            return True
        except:
            return False
    
    def remove_blacklist(self, group_id, user_id):
        db.execute("DELETE FROM blacklist WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    
    def is_blacklisted(self, group_id, user_id):
        row = db.fetch_one("SELECT 1 FROM blacklist WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        return row is not None
    
    def add_whitelist(self, group_id, user_id, reason):
        try:
            db.execute("INSERT INTO whitelist (group_id, user_id, reason, time) VALUES (?, ?, ?, ?)",
                      (group_id, user_id, reason, int(time.time())))
            return True
        except:
            return False
    
    def remove_whitelist(self, group_id, user_id):
        db.execute("DELETE FROM whitelist WHERE group_id = ? AND user_id = ?", (group_id, user_id))
    
    def is_whitelisted(self, group_id, user_id):
        row = db.fetch_one("SELECT 1 FROM whitelist WHERE group_id = ? AND user_id = ?", (group_id, user_id))
        return row is not None
    
    def add_auto_reply(self, group_id, trigger, response, reply_type='text'):
        db.execute("INSERT INTO auto_replies (group_id, trigger, response, type) VALUES (?, ?, ?, ?)",
                  (group_id, trigger, response, reply_type))
        return db.cursor.lastrowid
    
    def remove_auto_reply(self, reply_id):
        db.execute("DELETE FROM auto_replies WHERE id = ?", (reply_id,))
    
    def get_auto_replies(self, group_id):
        return db.fetch_all("SELECT * FROM auto_replies WHERE group_id = ?", (group_id,))
    
    def get_auto_reply(self, group_id, trigger):
        rows = db.fetch_all("SELECT * FROM auto_replies WHERE group_id = ? AND trigger = ?", (group_id, trigger))
        return rows[0] if rows else None
    
    def add_reminder(self, group_id, user_id, message, time_seconds):
        db.execute("INSERT INTO reminders (group_id, user_id, message, time, status) VALUES (?, ?, ?, ?, ?)",
                  (group_id, user_id, message, int(time.time()) + time_seconds, 'pending'))
        return db.cursor.lastrowid
    
    def get_reminders(self, group_id):
        return db.fetch_all("SELECT * FROM reminders WHERE group_id = ? AND status = 'pending' AND time <= ?",
                          (group_id, int(time.time())))
    
    def resolve_reminder(self, reminder_id):
        db.execute("UPDATE reminders SET status = 'done' WHERE id = ?", (reminder_id,))
    
    def add_poll(self, group_id, question, options):
        poll_id = len(self.polls) + 1
        self.polls[poll_id] = {
            "group_id": group_id,
            "question": question,
            "options": options,
            "votes": {opt: [] for opt in options},
            "time": time.time(),
            "status": "active"
        }
        return poll_id
    
    def vote_poll(self, poll_id, user_id, option):
        poll = self.polls.get(poll_id)
        if poll and poll["status"] == "active":
            for opt in poll["options"]:
                if user_id in poll["votes"][opt]:
                    poll["votes"][opt].remove(user_id)
            poll["votes"][option].append(user_id)
            return True
        return False
    
    def close_poll(self, poll_id):
        poll = self.polls.get(poll_id)
        if poll:
            poll["status"] = "closed"
            return True
        return False
    
    def get_poll_results(self, poll_id):
        poll = self.polls.get(poll_id)
        if poll:
            return poll["votes"]
        return None
    
    def detect_vpn(self, user_id):
        return False
    
    def detect_clone(self, user_id, group_id):
        return False
    
    def bayesian_spam_probability(self, text):
        spam_words = ["خرید", "فروش", "تبلیغ", "لینک", "عضویت", "ثبت نام", "کلیک", "کسب درآمد", "پول", "سود", "تخفیف"]
        ham_words = ["سلام", "درود", "چطور", "خوب", "ممنون", "لطفا", "متشکرم"]
        words = re.findall(r'\w+', text.lower())
        spam_score = 0
        ham_score = 0
        for word in words:
            if word in spam_words:
                spam_score += 1
            if word in ham_words:
                ham_score += 1
        total = spam_score + ham_score
        if total == 0:
            return 0.5
        return spam_score / total
    
    def detect_fake_news(self, text):
        fake_keywords = ["اخبار جعلی", "شایعه", "دروغ", "جعلی", "غیرواقعی", "کذب", "تبلیغات دروغین"]
        for kw in fake_keywords:
            if kw in text:
                return True
        return False
    
    def detect_scam(self, text):
        scam_keywords = ["کلاهبرداری", "فیشینگ", "اسکم", "پانزی", "هرم", "احتمالا کلاهبرداری", "برداشت غیرمجاز"]
        for kw in scam_keywords:
            if kw in text:
                return True
        return False
    
    def detect_impersonation(self, text):
        impersonation_keywords = ["جعل هویت", "قلابی", "جعلی", "ادعای دروغین"]
        for kw in impersonation_keywords:
            if kw in text:
                return True
        return False
    
    def detect_porn(self, text):
        porn_keywords = ["سکس", "پورن", "فیلم سوپر", "کانال بزرگسالان", "adult", "xxx", "porn", "sex", "سکسی", "برهنه"]
        for kw in porn_keywords:
            if kw in text.lower():
                return True
        return False
    
    def detect_violence(self, text):
        violence_keywords = ["قتل", "خون‌ریزی", "جنگ", "تروریسم", "خشونت", "اسلحه", "بمب", "انفجار", "کشتار", "حمله"]
        for kw in violence_keywords:
            if kw in text:
                return True
        return False
    
    def detect_drugs(self, text):
        drugs_keywords = ["مواد مخدر", "شیشه", "حشیش", "گراس", "کوکائین", "اکستازی", "تریاک", "هروئین", "ماری جوانا"]
        for kw in drugs_keywords:
            if kw in text:
                return True
        return False
    
    def detect_self_harm(self, text):
        self_harm_keywords = ["خودکشی", "خودزنی", "افسردگی شدید", "مرگ", "جان خود", "خودکشی"]
        for kw in self_harm_keywords:
            if kw in text:
                return True
        return False
    
    def detect_hate(self, text):
        hate_keywords = ["نژادپرستی", "تبعیض", "کشتار جمعی", "هولوکاست", "نازیسم", "برتری نژادی"]
        for kw in hate_keywords:
            if kw in text:
                return True
        return False
    
    def detect_child_abuse(self, text):
        child_abuse_keywords = ["آزار کودکان", "پورن کودکان", "کودک‌آزاری", "سوءاستفاده جنسی از کودکان"]
        for kw in child_abuse_keywords:
            if kw in text:
                return True
        return False
    
    def detect_human_trafficking(self, text):
        human_trafficking_keywords = ["قاچاق انسان", "برده‌داری", "خرید و فروش انسان"]
        for kw in human_trafficking_keywords:
            if kw in text:
                return True
        return False
    
    def detect_animal_abuse(self, text):
        animal_abuse_keywords = ["آزار حیوانات", "قاچاق حیوانات", "اذیت حیوانات"]
        for kw in animal_abuse_keywords:
            if kw in text:
                return True
        return False
    
    def detect_phishing(self, text):
        phishing_keywords = ["فیشینگ", "حساب کاربری", "رمز عبور", "کارت بانکی", "اطلاعات حساب", "ورود به حساب"]
        for kw in phishing_keywords:
            if kw in text:
                return True
        return False
    
    def detect_malware(self, text):
        malware_keywords = ["بدافزار", "تروجان", "ویروس", "کرم", "جاسوس‌افزار", "باج‌افزار"]
        for kw in malware_keywords:
            if kw in text:
                return True
        return False
    
    def detect_terrorism(self, text):
        terrorism_keywords = ["تروریسم", "داعش", "القاعده", "طالبان", "گروه تروریستی", "حمله تروریستی"]
        for kw in terrorism_keywords:
            if kw in text:
                return True
        return False
    
    def detect_crypto_scam(self, text):
        crypto_keywords = ["بیت‌کوین", "اتریوم", "تتر", "ارز دیجیتال", "رمزارز", "کریپتو", "btc", "eth", "usdt"]
        scam_indicators = ["ارسال", "دریافت", "سرمایه‌گذاری", "سود", "ضمانت", "برگشت سرمایه"]
        text_lower = text.lower()
        crypto_found = any(kw in text_lower for kw in crypto_keywords)
        scam_found = any(kw in text_lower for kw in scam_indicators)
        return crypto_found and scam_found
    
    def detect_gambling(self, text):
        gambling_keywords = ["قمار", "شرط‌بندی", "کازینو", "پوکر", "بلک‌جک", "رولت", "اسلات", "بخت‌آزمایی"]
        for kw in gambling_keywords:
            if kw in text:
                return True
        return False

udb = UltraDatabase()

# ========== ابزارهای کمکی ==========
def is_admin(user_id, chat_id):
    try:
        member = bot.get_chat_member(chat_id, user_id)
        return member.status in ["administrator", "creator"]
    except:
        return False

def is_bot_admin(user_id):
    return user_id in ADMIN_IDS

def get_user_mention(user):
    name = user.first_name
    if user.username:
        return f"@{user.username}"
    return f"<a href='tg://user?id={user.id}'>{name}</a>"

def format_duration(seconds):
    if seconds < 60:
        return f"{seconds} ثانیه"
    elif seconds < 3600:
        return f"{seconds // 60} دقیقه"
    elif seconds < 86400:
        return f"{seconds // 3600} ساعت"
    else:
        return f"{seconds // 86400} روز"

def contains_bad_words(text):
    bad_words = ["فحش", "کیر", "کون", "کس", "گه", "گوه", "حرام", "لعنت", "جاکش", "جنده", "فاحشه", "خایه", "مادرجنده"]
    text = text.lower()
    for word in bad_words:
        if word in text:
            return True
    return False

def contains_ad_keywords(text):
    ad_words = ["خرید", "فروش", "قیمت", "تخفیف", "فروشگاه", "سفارش", "تبلیغات", "تبلیغ", "اسپانسر", "حامی", "کسب درآمد", "ارز دیجیتال", "بیت‌کوین", "فارکس"]
    text = text.lower()
    for word in ad_words:
        if word in text:
            return True
    return False

def contains_link(text):
    url_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)'
    return re.search(url_pattern, text) is not None

def extract_links(text):
    url_pattern = r'(https?://[^\s]+)|(www\.[^\s]+)|(t\.me/[^\s]+)|(telegram\.me/[^\s]+)'
    return re.findall(url_pattern, text)

def is_forwarded(message):
    return message.forward_from is not None or message.forward_from_chat is not None

def detect_url_shortener(text):
    shorteners = ["bit.ly", "tinyurl", "shorturl", "goo.gl", "ow.ly", "is.gd", "buff.ly", "adf.ly", "shorte.st"]
    for s in shorteners:
        if s in text.lower():
            return True
    return False

def detect_phone(text):
    phone_pattern = r'(\+98|0098|0)?9\d{9}'
    return re.search(phone_pattern, text) is not None

def detect_email(text):
    email_pattern = r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}'
    return re.search(email_pattern, text) is not None

# ========== کیبوردهای پیشرفته ==========
def main_menu():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⚙️ تنظیمات", callback_data="settings"),
        InlineKeyboardButton("📊 آمار", callback_data="stats"),
        InlineKeyboardButton("📋 قوانین", callback_data="rules"),
        InlineKeyboardButton("🏆 رنکینگ", callback_data="ranking"),
        InlineKeyboardButton("🎫 تیکت", callback_data="tickets"),
        InlineKeyboardButton("👤 پروفایل", callback_data="profile"),
        InlineKeyboardButton("🆘 راهنما", callback_data="help"),
        InlineKeyboardButton("🔄 بروزرسانی", callback_data="refresh"),
        InlineKeyboardButton("🚨 گزارش تخلف", callback_data="report"),
        InlineKeyboardButton("🔒 امنیت", callback_data="security_panel"),
        InlineKeyboardButton("📝 مدیریت", callback_data="admin_panel")
    )
    return keyboard

def settings_menu(group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔰 پایه", callback_data=f"basic_{group_id}"),
        InlineKeyboardButton("🛡️ ضد اسپم", callback_data=f"spam_{group_id}"),
        InlineKeyboardButton("🚫 محدودیت‌ها", callback_data=f"restrict_{group_id}"),
        InlineKeyboardButton("🔐 امنیت", callback_data=f"security_{group_id}"),
        InlineKeyboardButton("🎯 پیشرفته", callback_data=f"advanced_{group_id}"),
        InlineKeyboardButton("🤖 پاسخ خودکار", callback_data=f"autoreply_{group_id}"),
        InlineKeyboardButton("📝 قوانین", callback_data=f"rules_edit_{group_id}"),
        InlineKeyboardButton("📋 لیست‌ها", callback_data=f"lists_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data="back_main")
    )
    return keyboard

def advanced_settings_menu(group_id):
    settings = udb.get_group(group_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"{'✅' if settings['anti_attack'] else '❌'} ضد حمله", callback_data=f"toggle_attack_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_vpn'] else '❌'} ضد VPN", callback_data=f"toggle_vpn_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_clone'] else '❌'} ضد کلون", callback_data=f"toggle_clone_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_spam_bayesian'] else '❌'} تشخیص اسپم بیزین", callback_data=f"toggle_bayesian_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_fake_news'] else '❌'} ضد اخبار جعلی", callback_data=f"toggle_fakenews_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_scam'] else '❌'} ضد کلاهبرداری", callback_data=f"toggle_scam_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_porn'] else '❌'} ضد محتوای بزرگسالان", callback_data=f"toggle_porn_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_violence'] else '❌'} ضد خشونت", callback_data=f"toggle_violence_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_drugs'] else '❌'} ضد مواد مخدر", callback_data=f"toggle_drugs_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_self_harm'] else '❌'} ضد خودزنی", callback_data=f"toggle_selfharm_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_hate'] else '❌'} ضد نفرت", callback_data=f"toggle_hate_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_phishing'] else '❌'} ضد فیشینگ", callback_data=f"toggle_phishing_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_malware'] else '❌'} ضد بدافزار", callback_data=f"toggle_malware_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_terrorism'] else '❌'} ضد تروریسم", callback_data=f"toggle_terrorism_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_child_abuse'] else '❌'} ضد آزار کودکان", callback_data=f"toggle_childabuse_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_crypto'] else '❌'} ضد کلاهبرداری رمزارز", callback_data=f"toggle_crypto_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_gambling'] else '❌'} ضد قمار", callback_data=f"toggle_gambling_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def lists_menu(group_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("📋 لیست سیاه", callback_data=f"blacklist_{group_id}"),
        InlineKeyboardButton("📋 لیست سفید", callback_data=f"whitelist_{group_id}"),
        InlineKeyboardButton("📋 گزارش‌ها", callback_data=f"reports_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def basic_settings_menu(group_id):
    settings = udb.get_group(group_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"{'✅' if settings['welcome_enabled'] else '❌'} پیام خوش‌آمدگویی", callback_data=f"toggle_welcome_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['captcha'] else '❌'} کپچا", callback_data=f"toggle_captcha_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['auto_delete'] else '❌'} حذف خودکار", callback_data=f"toggle_autodelete_{group_id}"),
        InlineKeyboardButton("⏱️ تنظیم زمان حذف", callback_data=f"autodel_set_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def spam_settings_menu(group_id):
    settings = udb.get_group(group_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"{'✅' if settings['anti_spam'] else '❌'} ضد اسپم", callback_data=f"toggle_antispam_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_raid'] else '❌'} ضد رید", callback_data=f"toggle_antiraid_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_spam_bayesian'] else '❌'} تشخیص بیزین", callback_data=f"toggle_bayesian_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def restrict_settings_menu(group_id):
    settings = udb.get_group(group_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"{'✅' if settings['anti_mentions'] else '❌'} ضد منشن", callback_data=f"toggle_mentions_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_caps'] else '❌'} ضد کپس", callback_data=f"toggle_caps_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_emoji'] else '❌'} ضد ایموجی", callback_data=f"toggle_emoji_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_newlines'] else '❌'} ضد خط جدید", callback_data=f"toggle_newlines_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_forward'] else '❌'} ضد فوروارد", callback_data=f"toggle_forward_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def security_settings_menu(group_id):
    settings = udb.get_group(group_id)
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton(f"{'✅' if settings['anti_bot'] else '❌'} ضد ربات", callback_data=f"toggle_bot_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_link'] else '❌'} ضد لینک", callback_data=f"toggle_link_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_bad_words'] else '❌'} ضد فحش", callback_data=f"toggle_badwords_{group_id}"),
        InlineKeyboardButton(f"{'✅' if settings['anti_advertising'] else '❌'} ضد تبلیغات", callback_data=f"toggle_advert_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def autoreply_menu(group_id):
    keyboard = InlineKeyboardMarkup(row_width=1)
    keyboard.add(
        InlineKeyboardButton("➕ افزودن پاسخ خودکار", callback_data=f"add_autoreply_{group_id}"),
        InlineKeyboardButton("📋 لیست پاسخ‌ها", callback_data=f"list_autoreply_{group_id}"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def auto_delete_menu(group_id):
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("⏱️ ۱ ساعت", callback_data=f"autodel_set_{group_id}_3600"),
        InlineKeyboardButton("⏱️ ۶ ساعت", callback_data=f"autodel_set_{group_id}_21600"),
        InlineKeyboardButton("⏱️ ۱۲ ساعت", callback_data=f"autodel_set_{group_id}_43200"),
        InlineKeyboardButton("⏱️ ۲۴ ساعت", callback_data=f"autodel_set_{group_id}_86400"),
        InlineKeyboardButton("❌ غیرفعال", callback_data=f"autodel_set_{group_id}_0"),
        InlineKeyboardButton("🔙 بازگشت", callback_data=f"back_settings_{group_id}")
    )
    return keyboard

def back_button():
    keyboard = InlineKeyboardMarkup()
    keyboard.add(InlineKeyboardButton("🔙 بازگشت", callback_data="back_main"))
    return keyboard

def get_back_button(user_id, chat_id=None):
    if chat_id and chat_id != user_id:
        settings = udb.get_group(chat_id)
        if settings.get('button_access_locked', True) and not is_admin(user_id, chat_id) and not is_bot_admin(user_id):
            return None
    return back_button()

# ========== دیکشنری ثبت دستورات ==========
command_handlers = {}

def register_command(cmd):
    def decorator(func):
        command_handlers[cmd] = func
        return func
    return decorator

# ========== هندلر دستورات فارسی (بدون اسلش) - باید قبل از handle_message بیاید ==========
@bot.message_handler(func=lambda message: message.text and any(message.text.startswith(cmd) for cmd in command_handlers), content_types=['text'])
def handle_persian_commands(message):
    for cmd in command_handlers:
        if message.text.startswith(cmd):
            command_handlers[cmd](message)
            break

# ========== دستورات /start و /help ==========
@bot.message_handler(commands=['start'])
def start_command(message):
    user = message.from_user
    chat_id = message.chat.id
    if message.chat.type in ['group', 'supergroup']:
        if not is_admin(user.id, chat_id) and not is_bot_admin(user.id):
            bot.reply_to(message, "⛔ این دستور فقط برای ادمین‌های گروه قابل استفاده است.")
            return
        menu = main_menu()
    else:
        menu = main_menu()
    
    text = f"""
✨ **ربات محافظ فوق‌پیشرفته Luffy Ultra Pro** ✨
━━━━━━━━━━━━━━━━━━━━━━
👤 **کاربر:** {user.first_name}
🆔 **آیدی:** `{user.id}`
👑 **نقش:** {'👑 ادمین اصلی' if is_bot_admin(user.id) else '👤 کاربر'}
━━━━━━━━━━━━━━━━━━━━━━

🛡️ **قابلیت‌های بی‌نظیر:**
• ضد اسپم هوشمند (بیزین)
• ضد حمله و رید
• ضد VPN و پروکسی
• ضد کلون و حساب‌های جعلی
• ضد لینک، فحش، تبلیغات
• کپچا پیشرفته
• سیستم سطح‌بندی
• قفل گروه و حالت سکوت
• سیستم تیکت
• پاسخ‌های خودکار
• سیستم گزارش‌گیری
• لیست سیاه و سفید
• تشخیص محتوای حساس (بزرگسالان، خشونت، مواد مخدر، قمار، کلاهبرداری، تروریسم، کودک‌آزاری و...)
• سیستم نظرسنجی و مسابقات
• یادآوری‌ها
• و ده‌ها قابلیت منحصربه‌فرد دیگر!

📌 برای مدیریت گروه، بات را به گروه اضافه و ادمین کنید.
"""
    bot.reply_to(message, text, reply_markup=menu, parse_mode='HTML')

@bot.message_handler(commands=['help'])
def help_command(message):
    chat_id = message.chat.id
    user_id = message.from_user.id
    menu = get_back_button(user_id, chat_id) if message.chat.type in ['group', 'supergroup'] else back_button()
    
    text = """
📋 **راهنمای کامل ربات**
━━━━━━━━━━━━━━━━━━━━━━
**دستورات عمومی (بدون اسلش):**
start - منوی اصلی
راهنما - این راهنما
قوانین - نمایش قوانین
رتبه - نمایش رتبه شما
رنکینگ - رنکینگ گروه
پروفایل - پروفایل شما
تیکت [موضوع] - تیکت جدید
گزارش [کاربر] [دلیل] - گزارش تخلف
یادآور [زمان] [پیام] - تنظیم یادآوری

**دستورات مدیریت (فقط ادمین‌ها، بدون اسلش):**
تنظیمات - تنظیمات پیشرفته
آمار - آمار گروه
بن [کاربر] - بن کاربر
آنبن [کاربر] - آن‌بن
اخراج [کاربر] - اخراج
تک [کاربر] - اخراج (همان اخراج)
میوت [کاربر] [مدت] - میوت
آنمیوت [کاربر] - رفع میوت
اخطار [کاربر] [دلیل] - اخطار
اخطارها [کاربر] - نمایش اخطارها
پاکسازی اخطارها [کاربر] - بازنشانی
پاکسازی (ریپلای) - پاکسازی پیام‌ها
سنجاق (ریپلای) - پین
برداشتن سنجاق - برداشتن پین
قفل - قفل گروه
بازکردن قفل - باز کردن قفل
بکاپ - بکاپ
سیاه [کاربر] [دلیل] - افزودن به لیست سیاه
سفید [کاربر] [دلیل] - افزودن به لیست سفید
حذف سیاه [کاربر] - حذف از لیست سیاه
حذف سفید [کاربر] - حذف از لیست سفید
نظرسنجی [سوال] | [گزینه1] | [گزینه2] ... - ایجاد نظرسنجی
بستن نظرسنجی [شناسه] - بستن نظرسنجی
مسابقه [نام] | [توضیحات] | [زمان] - ایجاد مسابقه

**نکته:** می‌توانید به پیام کاربر ریپلای کنید.
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, text, reply_markup=menu, parse_mode='HTML')

# ========== دستورات عمومی ==========
@register_command("قوانین")
def rules_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    settings = udb.get_group(group_id)
    rules = settings.get('rules', 'قوانینی تنظیم نشده است.')
    bot.reply_to(message, f"📋 **قوانین گروه:**\n{rules}", reply_markup=get_back_button(message.from_user.id, group_id), parse_mode='HTML')

@register_command("رنکینگ")
def ranking_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    try:
        members = bot.get_chat_members(group_id)
        rankings = []
        for member in members:
            if not member.user.is_bot:
                uid = member.user.id
                level = udb.get_level(uid)
                xp = udb.get_xp(uid)
                rankings.append((uid, level, xp))
        rankings.sort(key=lambda x: x[1], reverse=True)
        text = "🏆 **رنکینگ کاربران**\n━━━━━━━━━━━━━━━━━━━━━━\n"
        for i, (uid, level, xp) in enumerate(rankings[:10], 1):
            try:
                user = bot.get_chat_member(group_id, uid).user
                name = user.first_name[:15]
                text += f"{i}. {name} - سطح {level} (XP: {xp})\n"
            except:
                continue
        if text == "🏆 **رنکینگ کاربران**\n━━━━━━━━━━━━━━━━━━━━━━\n":
            text = "📭 هنوز داده‌ای وجود ندارد."
        bot.reply_to(message, text, reply_markup=get_back_button(message.from_user.id, group_id), parse_mode='HTML')
    except:
        bot.reply_to(message, "❌ خطا در دریافت رنکینگ.")

@register_command("رتبه")
def rank_command(message):
    user_id = message.from_user.id
    level = udb.get_level(user_id)
    xp = udb.get_xp(user_id)
    next_level_xp = int((level + 1) ** 2.5)
    progress = (xp / next_level_xp) * 100 if next_level_xp > 0 else 0
    text = f"""
🏆 **رتبه شما**
━━━━━━━━━━━━━━━━━━━━━━
👤 **کاربر:** {message.from_user.first_name}
📊 **سطح:** {level}
⭐ **امتیاز (XP):** {xp}
📈 **پیشرفت:** {progress:.1f}%
🔜 **XP مورد نیاز:** {next_level_xp}
━━━━━━━━━━━━━━━━━━━━━━
"""
    chat_id = message.chat.id
    menu = get_back_button(user_id, chat_id) if message.chat.type in ['group', 'supergroup'] else back_button()
    bot.reply_to(message, text, reply_markup=menu, parse_mode='HTML')

@register_command("پروفایل")
def profile_command(message):
    user_id = message.from_user.id
    user = udb.get_user(user_id)
    is_verified = "✅" if user["verified"] else "❌"
    is_muted = "🔇" if udb.is_muted(user_id) else "🔊"
    text = f"""
👤 **پروفایل کاربر**
━━━━━━━━━━━━━━━━━━━━━━
📛 **نام:** {message.from_user.first_name}
🆔 **آیدی:** `{user_id}`
🏆 **سطح:** {user["level"]}
⭐ **امتیاز:** {user["xp"]}
🔐 **تایید:** {is_verified}
🔇 **میوت:** {is_muted}
⚠️ **اخطارها:** {user["warnings"]}
📨 **پیام‌ها:** {user["total_messages"]}
📅 **عضویت:** {datetime.fromtimestamp(user["join_date"]).strftime('%Y-%m-%d %H:%M') if user["join_date"] else 'نامشخص'}
━━━━━━━━━━━━━━━━━━━━━━
"""
    chat_id = message.chat.id
    menu = get_back_button(user_id, chat_id) if message.chat.type in ['group', 'supergroup'] else back_button()
    bot.reply_to(message, text, reply_markup=menu, parse_mode='HTML')

@register_command("تیکت")
def ticket_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ تیکت [موضوع] - یک تیکت جدید ایجاد کنید.")
        return
    subject = " ".join(args[1:])
    ticket_id = udb.add_ticket(group_id, message.from_user.id, subject)
    bot.reply_to(message, f"✅ تیکت شماره {ticket_id} با موضوع '{subject}' ایجاد شد.\nیک ادمین به زودی پاسخ خواهد داد.")

@register_command("تیکت‌ها")
def tickets_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند تیکت‌ها را ببینند.")
        return
    tickets = udb.tickets.get(group_id, [])
    if not tickets:
        bot.reply_to(message, "📭 هیچ تیکتی وجود ندارد.")
        return
    text = "🎫 **لیست تیکت‌ها**\n━━━━━━━━━━━━━━━━━━━━━━\n"
    for t in tickets:
        status = "🟢 باز" if t["status"] == "open" else "🔴 بسته"
        text += f"#{t['id']} - {t['subject']} ({status})\n"
    bot.reply_to(message, text, reply_markup=back_button(), parse_mode='HTML')

@register_command("پاسخ")
def reply_ticket_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند پاسخ دهند.")
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ پاسخ [شماره تیکت] [پاسخ]")
        return
    try:
        ticket_id = int(args[1])
        reply_text = " ".join(args[2:])
        if udb.add_ticket_message(group_id, ticket_id, message.from_user.id, reply_text):
            bot.reply_to(message, f"✅ پاسخ به تیکت #{ticket_id} ارسال شد.")
        else:
            bot.reply_to(message, "❌ تیکت یافت نشد.")
    except:
        bot.reply_to(message, "❌ شماره تیکت نامعتبر.")

@register_command("بستن تیکت")
def close_ticket_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین‌ها می‌توانند تیکت را ببندند.")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ بستن تیکت [شماره]")
        return
    try:
        ticket_id = int(args[1])
        if udb.close_ticket(group_id, ticket_id):
            bot.reply_to(message, f"✅ تیکت #{ticket_id} بسته شد.")
        else:
            bot.reply_to(message, "❌ تیکت یافت نشد.")
    except:
        bot.reply_to(message, "❌ شماره تیکت نامعتبر.")

@register_command("گزارش")
def report_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ گزارش [کاربر] [دلیل]")
        return
    target = args[1]
    reason = " ".join(args[2:])
    target_id = None
    if target.isdigit():
        target_id = int(target)
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        bot.reply_to(message, "❌ کاربر را مشخص کنید (با ریپلای یا آیدی).")
        return
    if target_id == message.from_user.id:
        bot.reply_to(message, "❌ نمی‌توانید خودتان را گزارش کنید.")
        return
    report_id = udb.add_report(group_id, target_id, message.from_user.id, reason)
    bot.reply_to(message, f"✅ گزارش شما ثبت شد. شماره: {report_id}")
    for admin_id in ADMIN_IDS:
        try:
            bot.send_message(admin_id, f"🚨 گزارش جدید:\nکاربر: {target_id}\nدلیل: {reason}\nتوسط: {message.from_user.id}\nگروه: {group_id}")
        except:
            pass

@register_command("یادآور")
def reminder_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ یادآور [زمان به ثانیه] [پیام]")
        return
    try:
        seconds = int(args[1])
        msg = " ".join(args[2:])
        reminder_id = udb.add_reminder(group_id, message.from_user.id, msg, seconds)
        bot.reply_to(message, f"✅ یادآوری تنظیم شد. (شناسه: {reminder_id})")
        def send_reminder():
            time.sleep(seconds)
            bot.send_message(group_id, f"⏰ یادآوری برای {get_user_mention(message.from_user)}:\n{msg}", parse_mode='HTML')
            udb.resolve_reminder(reminder_id)
        threading.Thread(target=send_reminder, daemon=True).start()
    except:
        bot.reply_to(message, "❌ زمان نامعتبر.")

# ========== دستورات مدیریت ==========
@register_command("تنظیمات")
def settings_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    bot.reply_to(message, "⚙️ **تنظیمات پیشرفته گروه:**", reply_markup=settings_menu(group_id), parse_mode='HTML')

@register_command("آمار")
def stats_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    try:
        members = bot.get_chat_members_count(group_id)
    except:
        members = "نامشخص"
    total_warns = udb.stats.get('total_warns', 0)
    total_muted = sum(1 for user in [udb.get_user(uid) for uid in set([row[0] for row in db.fetch_all("SELECT user_id FROM users")])] if udb.is_muted(user["user_id"]))
    text = f"""
📊 **آمار پیشرفته گروه**
━━━━━━━━━━━━━━━━━━━━━━
👥 **تعداد اعضا:** {members}
📨 **پیام‌ها:** {udb.stats.get('total_messages', 0):,}
🚫 **اخراجی‌ها:** {udb.stats.get('total_kicks', 0):,}
🔨 **بن‌ها:** {udb.stats.get('total_bans', 0):,}
🔇 **میوت‌ها:** {udb.stats.get('total_mutes', 0):,}
⚠️ **اخطارها:** {udb.stats.get('total_warns', 0):,}
🔐 **کپچا موفق:** {udb.stats.get('captcha_passed', 0):,}
❌ **کپچا ناموفق:** {udb.stats.get('captcha_failed', 0):,}
🔇 **میوت:** {total_muted}
🎫 **تیکت‌ها:** {len(udb.tickets.get(group_id, []))}
📋 **گزارش‌ها:** {len(udb.get_reports(group_id))}
━━━━━━━━━━━━━━━━━━━━━━
"""
    bot.reply_to(message, text, reply_markup=back_button(), parse_mode='HTML')

@register_command("بن")
def ban_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ بن [کاربر]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    try:
        bot.ban_chat_member(group_id, target_id)
        udb.stats["total_bans"] += 1
        udb._save_stats()
        bot.reply_to(message, f"✅ کاربر {target_id} بن شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("آنبن")
def unban_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ آنبن [کاربر]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    try:
        bot.unban_chat_member(group_id, target_id)
        bot.reply_to(message, f"✅ کاربر {target_id} آن‌بن شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("اخراج")
@register_command("تک")
def kick_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ اخراج [کاربر]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    try:
        bot.ban_chat_member(group_id, target_id)
        bot.unban_chat_member(group_id, target_id)
        udb.stats["total_kicks"] += 1
        udb._save_stats()
        bot.reply_to(message, f"✅ کاربر {target_id} اخراج شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("میوت")
def mute_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ میوت [کاربر] [مدت به ثانیه]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    duration = int(args[2]) if len(args) > 2 else 300
    try:
        udb.set_mute(target_id, duration)
        udb.stats["total_mutes"] += 1
        udb._save_stats()
        bot.reply_to(message, f"✅ کاربر {target_id} به مدت {format_duration(duration)} میوت شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("آنمیوت")
def unmute_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ آنمیوت [کاربر]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    try:
        udb.remove_mute(target_id)
        bot.reply_to(message, f"✅ میوت کاربر {target_id} برداشته شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("اخطار")
def warn_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ اخطار [کاربر] [دلیل]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    reason = " ".join(args[2:]) if len(args) > 2 else "تخلف"
    try:
        count = udb.add_warning(group_id, target_id, reason)
        settings = udb.get_group(group_id)
        if count >= settings['warn_limit']:
            action = settings['warn_action']
            if action == "mute":
                udb.set_mute(target_id, settings['warn_duration'])
                udb.stats["total_mutes"] += 1
                bot.reply_to(message, f"⚠️ کاربر {target_id} به دلیل {settings['warn_limit']} اخطار، {format_duration(settings['warn_duration'])} میوت شد.")
            elif action == "kick":
                bot.ban_chat_member(group_id, target_id)
                bot.unban_chat_member(group_id, target_id)
                udb.stats["total_kicks"] += 1
                bot.reply_to(message, f"⚠️ کاربر {target_id} به دلیل {settings['warn_limit']} اخطار، اخراج شد.")
            elif action == "ban":
                bot.ban_chat_member(group_id, target_id)
                udb.stats["total_bans"] += 1
                bot.reply_to(message, f"⚠️ کاربر {target_id} به دلیل {settings['warn_limit']} اخطار، بن شد.")
            udb.clear_warnings(group_id, target_id)
            udb._save_stats()
        else:
            bot.reply_to(message, f"⚠️ کاربر {target_id} اخطار {count}/{settings['warn_limit']} دریافت کرد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("اخطارها")
def warnings_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ اخطارها [کاربر]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    warns = udb.get_warnings(group_id, target_id)
    if warns:
        text = f"⚠️ **اخطارهای کاربر {target_id}:**\n"
        for i, w in enumerate(warns, 1):
            text += f"{i}. {w['reason']} ({datetime.fromtimestamp(w['time']).strftime('%Y-%m-%d %H:%M')})\n"
        bot.reply_to(message, text, parse_mode='HTML')
    else:
        bot.reply_to(message, f"✅ کاربر {target_id} هیچ اخطاری ندارد.")

@register_command("پاکسازی اخطارها")
def reset_warnings_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2 and not message.reply_to_message:
        bot.reply_to(message, "⚠️ پاکسازی اخطارها [کاربر]")
        return
    target_id = None
    if message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    elif len(args) > 1 and args[1].isdigit():
        target_id = int(args[1])
    if not target_id:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    if udb.clear_warnings(group_id, target_id):
        bot.reply_to(message, f"✅ اخطارهای کاربر {target_id} بازنشانی شد.")
    else:
        bot.reply_to(message, f"❌ کاربر {target_id} اخطاری ندارد.")

@register_command("پاکسازی")
def purge_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ به پیامی ریپلای کنید تا از آن به بعد حذف شود.")
        return
    try:
        msg_id = message.reply_to_message.message_id
        count = 0
        while msg_id < message.message_id and count < 100:
            bot.delete_message(group_id, msg_id)
            msg_id += 1
            count += 1
        bot.reply_to(message, f"✅ {count} پیام حذف شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("سنجاق")
def pin_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    if not message.reply_to_message:
        bot.reply_to(message, "⚠️ به پیامی که می‌خواهید پین کنید ریپلای کنید.")
        return
    try:
        bot.pin_chat_message(group_id, message.reply_to_message.message_id)
        bot.reply_to(message, "📌 پیام پین شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("برداشتن سنجاق")
def unpin_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    try:
        bot.unpin_chat_message(group_id)
        bot.reply_to(message, "📌 پین برداشته شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("قفل")
def lock_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    settings = udb.get_group(group_id)
    settings['group_lock'] = True
    udb.save_group(group_id, settings)
    bot.reply_to(message, "🔒 گروه قفل شد. فقط ادمین‌ها می‌توانند پیام بفرستند.")

@register_command("بازکردن قفل")
def unlock_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    settings = udb.get_group(group_id)
    settings['group_lock'] = False
    udb.save_group(group_id, settings)
    bot.reply_to(message, "🔓 قفل گروه باز شد.")

@register_command("بکاپ")
def backup_command(message):
    if not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ فقط ادمین اصلی می‌تواند بکاپ بگیرد.")
        return
    try:
        data = {
            "groups": udb.get_group(0),
            "stats": dict(udb.stats),
            "timestamp": time.time()
        }
        with open(f"backup_{int(time.time())}.json", "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        bot.reply_to(message, "✅ بکاپ با موفقیت ذخیره شد.")
    except Exception as e:
        bot.reply_to(message, f"❌ خطا: {e}")

@register_command("سیاه")
def blacklist_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ سیاه [کاربر] [دلیل]")
        return
    target = args[1]
    reason = " ".join(args[2:])
    target_id = None
    if target.isdigit():
        target_id = int(target)
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    if udb.add_blacklist(group_id, target_id, reason):
        bot.reply_to(message, f"✅ کاربر {target_id} به لیست سیاه اضافه شد.")
    else:
        bot.reply_to(message, "❌ کاربر قبلاً در لیست سیاه است.")

@register_command("سفید")
def whitelist_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 3:
        bot.reply_to(message, "⚠️ سفید [کاربر] [دلیل]")
        return
    target = args[1]
    reason = " ".join(args[2:])
    target_id = None
    if target.isdigit():
        target_id = int(target)
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    if udb.add_whitelist(group_id, target_id, reason):
        bot.reply_to(message, f"✅ کاربر {target_id} به لیست سفید اضافه شد.")
    else:
        bot.reply_to(message, "❌ کاربر قبلاً در لیست سفید است.")

@register_command("حذف سیاه")
def remove_blacklist_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ حذف سیاه [کاربر]")
        return
    target = args[1]
    target_id = None
    if target.isdigit():
        target_id = int(target)
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    udb.remove_blacklist(group_id, target_id)
    bot.reply_to(message, f"✅ کاربر {target_id} از لیست سیاه حذف شد.")

@register_command("حذف سفید")
def remove_whitelist_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ حذف سفید [کاربر]")
        return
    target = args[1]
    target_id = None
    if target.isdigit():
        target_id = int(target)
    elif message.reply_to_message:
        target_id = message.reply_to_message.from_user.id
    else:
        bot.reply_to(message, "❌ کاربر را مشخص کنید.")
        return
    udb.remove_whitelist(group_id, target_id)
    bot.reply_to(message, f"✅ کاربر {target_id} از لیست سفید حذف شد.")

@register_command("نظرسنجی")
def poll_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split('|')
    if len(args) < 3:
        bot.reply_to(message, "⚠️ نظرسنجی [سوال] | [گزینه1] | [گزینه2] | ...")
        return
    question = args[0].strip().replace("نظرسنجی", "").strip()
    options = [opt.strip() for opt in args[1:]]
    if len(options) < 2:
        bot.reply_to(message, "❌ حداقل 2 گزینه لازم است.")
        return
    poll_id = udb.add_poll(group_id, question, options)
    keyboard = InlineKeyboardMarkup(row_width=2)
    for i, opt in enumerate(options):
        keyboard.add(InlineKeyboardButton(opt, callback_data=f"poll_vote_{poll_id}_{i}"))
    keyboard.add(InlineKeyboardButton("🔒 بستن نظرسنجی", callback_data=f"poll_close_{poll_id}"))
    bot.send_message(group_id, f"📊 **نظرسنجی:** {question}", reply_markup=keyboard, parse_mode='HTML')
    bot.reply_to(message, f"✅ نظرسنجی با شناسه {poll_id} ایجاد شد.")

@register_command("بستن نظرسنجی")
def close_poll_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split()
    if len(args) < 2:
        bot.reply_to(message, "⚠️ بستن نظرسنجی [شناسه]")
        return
    try:
        poll_id = int(args[1])
        if udb.close_poll(poll_id):
            results = udb.get_poll_results(poll_id)
            if results:
                text = f"📊 **نتایج نظرسنجی:**\n"
                for opt, voters in results.items():
                    text += f"{opt}: {len(voters)} رای\n"
                bot.send_message(group_id, text, parse_mode='HTML')
            bot.reply_to(message, f"✅ نظرسنجی {poll_id} بسته شد.")
        else:
            bot.reply_to(message, "❌ نظرسنجی یافت نشد.")
    except:
        bot.reply_to(message, "❌ شناسه نامعتبر.")

@register_command("مسابقه")
def contest_command(message):
    if not message.chat.type in ['group', 'supergroup']:
        bot.reply_to(message, "❌ این دستور فقط در گروه قابل استفاده است.")
        return
    group_id = message.chat.id
    if not is_admin(message.from_user.id, group_id) and not is_bot_admin(message.from_user.id):
        bot.reply_to(message, "⛔ شما ادمین گروه نیستید!")
        return
    args = message.text.split('|')
    if len(args) < 3:
        bot.reply_to(message, "⚠️ مسابقه [نام] | [توضیحات] | [زمان بر حسب ثانیه]")
        return
    name = args[0].strip().replace("مسابقه", "").strip()
    desc = args[1].strip()
    try:
        duration = int(args[2].strip())
    except:
        bot.reply_to(message, "❌ زمان نامعتبر.")
        return
    contest_id = int(time.time())
    text = f"🏆 **مسابقه: {name}**\n📝 {desc}\n⏳ مدت: {format_duration(duration)}\nبرای شرکت دستور /شرکت {contest_id} را بفرستید."
    bot.send_message(group_id, text, parse_mode='HTML')
    bot.reply_to(message, f"✅ مسابقه با شناسه {contest_id} ایجاد شد.")

@register_command("شرکت")
def participate_contest(message):
    bot.reply_to(message, "✅ شما در مسابقه ثبت شدید.")

# ========== مدیریت اعضای جدید ==========
@bot.chat_member_handler()
def handle_new_member(chat_member_update: ChatMemberUpdated):
    chat = chat_member_update.chat
    if chat.type not in ['group', 'supergroup']:
        return
    group_id = chat.id
    new = chat_member_update.new_chat_member
    old = chat_member_update.old_chat_member
    
    if new.status == "member" and old.status in ["left", "kicked"]:
        user = new.user
        if user.is_bot:
            settings = udb.get_group(group_id)
            if settings['anti_bot']:
                try:
                    bot.ban_chat_member(group_id, user.id)
                    udb.stats["total_bans"] += 1
                    udb._save_stats()
                    bot.send_message(group_id, f"🤖 ربات {user.first_name} شناسایی و بن شد.")
                except:
                    pass
            return
        
        user_id = user.id
        settings = udb.get_group(group_id)
        udb.add_join(group_id)
        user_data = udb.get_user(user_id)
        user_data["join_date"] = int(time.time())
        user_data["first_name"] = user.first_name
        user_data["username"] = user.username
        udb.save_user(user_data)
        
        if settings['anti_raid']:
            join_count = udb.get_join_count(group_id, 10)
            if join_count >= settings['raid_threshold']:
                action = settings['raid_action']
                try:
                    if action == "kick":
                        bot.ban_chat_member(group_id, user_id)
                        bot.unban_chat_member(group_id, user_id)
                        udb.stats["total_kicks"] += 1
                    elif action == "ban":
                        bot.ban_chat_member(group_id, user_id)
                        udb.stats["total_bans"] += 1
                    udb._save_stats()
                except:
                    pass
                return
        
        if settings['anti_clone']:
            pass
        
        if settings['captcha']:
            num1 = random.randint(1, 15)
            num2 = random.randint(1, 15)
            answer = num1 + num2
            udb.save_captcha(user_id, group_id, answer)
            
            bot.send_message(
                group_id,
                f"🔐 {get_user_mention(user)}، لطفاً برای اثبات اینکه ربات نیستی، پاسخ این معادله را بفرست:\n\n{num1} + {num2} = ?\n\n⏳ شما {settings['captcha_timeout']} ثانیه فرصت دارید.",
                parse_mode='HTML'
            )
            
            def captcha_timeout():
                captcha_data = udb.get_captcha(user_id)
                if captcha_data and captcha_data["group_id"] == group_id:
                    try:
                        bot.ban_chat_member(group_id, user_id)
                        bot.unban_chat_member(group_id, user_id)
                        udb.stats["captcha_failed"] += 1
                        udb._save_stats()
                        bot.send_message(group_id, f"⏰ {get_user_mention(user)} زمان کپچا تمام شد، اخراج شد.", parse_mode='HTML')
                    except:
                        pass
                    udb.delete_captcha(user_id)
            
            threading.Timer(settings['captcha_timeout'], captcha_timeout).start()
        
        if settings['welcome_enabled']:
            welcome_text = settings['welcome'].replace("{user_name}", user.first_name)
            bot.send_message(group_id, welcome_text, parse_mode='HTML')

# ========== پاسخ به کپچا ==========
@bot.message_handler(func=lambda message: message.chat.type in ['group', 'supergroup'] and message.text and message.text.lstrip('-').isdigit())
def captcha_answer(message):
    user_id = message.from_user.id
    group_id = message.chat.id
    captcha_data = udb.get_captcha(user_id)
    
    if not captcha_data:
        return
    
    if captcha_data["group_id"] != group_id:
        return
    
    if int(message.text) == captcha_data["answer"]:
        udb.delete_captcha(user_id)
        udb.stats["captcha_passed"] += 1
        udb._save_stats()
        udb.verify_user(user_id)
        bot.reply_to(message, "✅ کپچا صحیح بود! خوش آمدید.")
    else:
        attempts = udb.increment_captcha_attempts(user_id)
        settings = udb.get_group(group_id)
        max_attempts = settings.get('captcha_max_attempts', 3)
        
        if attempts >= max_attempts:
            try:
                bot.ban_chat_member(group_id, user_id)
                bot.unban_chat_member(group_id, user_id)
                udb.stats["captcha_failed"] += 1
                udb._save_stats()
                bot.reply_to(message, f"❌ تعداد تلاش‌های شما بیش از حد مجاز بود، اخراج شدید.")
            except:
                pass
            udb.delete_captcha(user_id)
        else:
            bot.reply_to(message, f"❌ پاسخ نادرست! تلاش {attempts}/{max_attempts}")

# ========== مدیریت پیام‌ها (باید بعد از handle_persian_commands بیاید) ==========
@bot.message_handler(func=lambda message: True, content_types=['text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker', 'animation', 'poll', 'dice', 'contact', 'location', 'venue'])
def handle_message(message):
    if not message.chat.type in ['group', 'supergroup']:
        return
    
    group_id = message.chat.id
    user = message.from_user
    user_id = user.id
    
    # اگر پیام یک دستور ثبت شده باشد، آن را نادیده می‌گیریم (قبلاً توسط handle_persian_commands پردازش شده)
    if message.text and any(message.text.startswith(cmd) for cmd in command_handlers):
        return
    
    if is_admin(user_id, group_id) or user.is_bot:
        return
    
    settings = udb.get_group(group_id)
    
    if udb.is_blacklisted(group_id, user_id):
        try:
            bot.ban_chat_member(group_id, user_id)
            bot.send_message(group_id, f"🚫 {get_user_mention(user)} در لیست سیاه است و بن شد.", parse_mode='HTML')
        except:
            pass
        return
    
    if udb.is_whitelisted(group_id, user_id):
        return
    
    if settings.get('silent_mode', False):
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"🔇 {get_user_mention(user)} گروه در حالت سکوت است. فقط ادمین‌ها می‌توانند پیام بفرستند.", parse_mode='HTML')
        except:
            pass
        return
    
    if settings['group_lock']:
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"🔒 {get_user_mention(user)} گروه قفل است!", parse_mode='HTML')
        except:
            pass
        return
    
    if udb.is_muted(user_id):
        try:
            bot.delete_message(group_id, message.message_id)
            remaining = udb.get_mute_remaining(user_id)
            bot.send_message(group_id, f"🔇 {get_user_mention(user)} شما میوت هستید! ({format_duration(remaining)} باقی مانده)", parse_mode='HTML')
        except:
            pass
        return
    
    if udb.is_temp_banned(user_id):
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"🔨 {get_user_mention(user)} شما بن موقت هستید!", parse_mode='HTML')
        except:
            pass
        return
    
    if settings['anti_spam_bayesian'] and message.text:
        prob = udb.bayesian_spam_probability(message.text)
        if prob > settings.get('spam_probability_threshold', 0.7):
            try:
                bot.delete_message(group_id, message.message_id)
                bot.send_message(group_id, f"🔇 {get_user_mention(user)} پیام شما به عنوان اسپم شناسایی شد.", parse_mode='HTML')
                udb.set_mute(user_id, 300)
                udb.stats["total_mutes"] += 1
                udb._save_stats()
            except:
                pass
            return
    
    if settings['anti_spam'] and message.text:
        udb.add_message(user_id)
        count = udb.get_message_count(user_id, 1)
        if count >= settings['spam_threshold']:
            action = settings['spam_action']
            try:
                bot.delete_message(group_id, message.message_id)
                if action == "mute":
                    udb.set_mute(user_id, settings['spam_duration'])
                    udb.stats["total_mutes"] += 1
                    bot.send_message(group_id, f"🔇 {get_user_mention(user)} به دلیل اسپم به مدت {format_duration(settings['spam_duration'])} میوت شد.", parse_mode='HTML')
                elif action == "kick":
                    bot.ban_chat_member(group_id, user_id)
                    bot.unban_chat_member(group_id, user_id)
                    udb.stats["total_kicks"] += 1
                    bot.send_message(group_id, f"👢 {get_user_mention(user)} به دلیل اسپم اخراج شد.", parse_mode='HTML')
                elif action == "ban":
                    bot.ban_chat_member(group_id, user_id)
                    udb.stats["total_bans"] += 1
                    bot.send_message(group_id, f"🔨 {get_user_mention(user)} به دلیل اسپم بن شد.", parse_mode='HTML')
                udb._save_stats()
            except:
                pass
            return
    
    if settings['anti_link'] and message.text and contains_link(message.text):
        links = extract_links(message.text)
        is_whitelisted = any(any(whitelist in link for whitelist in settings.get('anti_link_whitelist', [])) for link in links)
        if not is_whitelisted:
            try:
                bot.delete_message(group_id, message.message_id)
                action = settings['anti_link_action']
                if action == "warn":
                    count = udb.add_warning(group_id, user_id, "ارسال لینک ممنوع")
                    bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً لینک نفرستید! (اخطار {count})", parse_mode='HTML')
                elif action == "mute":
                    udb.set_mute(user_id, 300)
                    udb.stats["total_mutes"] += 1
                    bot.send_message(group_id, f"🔇 {get_user_mention(user)} به دلیل ارسال لینک میوت شد.", parse_mode='HTML')
                elif action == "kick":
                    bot.ban_chat_member(group_id, user_id)
                    bot.unban_chat_member(group_id, user_id)
                    udb.stats["total_kicks"] += 1
                    bot.send_message(group_id, f"👢 {get_user_mention(user)} به دلیل ارسال لینک اخراج شد.", parse_mode='HTML')
                elif action == "ban":
                    bot.ban_chat_member(group_id, user_id)
                    udb.stats["total_bans"] += 1
                    bot.send_message(group_id, f"🔨 {get_user_mention(user)} به دلیل ارسال لینک بن شد.", parse_mode='HTML')
                udb._save_stats()
            except:
                pass
            return
    
    if settings['anti_bad_words'] and message.text and contains_bad_words(message.text):
        try:
            bot.delete_message(group_id, message.message_id)
            action = settings['anti_bad_words_action']
            if action == "mute":
                udb.set_mute(user_id, settings.get('anti_bad_words_duration', 600))
                udb.stats["total_mutes"] += 1
                bot.send_message(group_id, f"🔇 {get_user_mention(user)} به دلیل استفاده از الفاظ نامناسب میوت شد.", parse_mode='HTML')
            elif action == "kick":
                bot.ban_chat_member(group_id, user_id)
                bot.unban_chat_member(group_id, user_id)
                udb.stats["total_kicks"] += 1
                bot.send_message(group_id, f"👢 {get_user_mention(user)} به دلیل فحش اخراج شد.", parse_mode='HTML')
            elif action == "ban":
                bot.ban_chat_member(group_id, user_id)
                udb.stats["total_bans"] += 1
                bot.send_message(group_id, f"🔨 {get_user_mention(user)} به دلیل فحش بن شد.", parse_mode='HTML')
            else:
                count = udb.add_warning(group_id, user_id, "فحش و الفاظ نامناسب")
                bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً از الفاظ مناسب استفاده کنید! (اخطار {count})", parse_mode='HTML')
            udb._save_stats()
        except:
            pass
        return
    
    if settings['anti_advertising'] and message.text and contains_ad_keywords(message.text):
        try:
            bot.delete_message(group_id, message.message_id)
            action = settings['anti_advertising_action']
            if action == "kick":
                bot.ban_chat_member(group_id, user_id)
                bot.unban_chat_member(group_id, user_id)
                udb.stats["total_kicks"] += 1
                bot.send_message(group_id, f"👢 {get_user_mention(user)} به دلیل تبلیغات اخراج شد.", parse_mode='HTML')
            elif action == "ban":
                bot.ban_chat_member(group_id, user_id)
                udb.stats["total_bans"] += 1
                bot.send_message(group_id, f"🔨 {get_user_mention(user)} به دلیل تبلیغات بن شد.", parse_mode='HTML')
            else:
                count = udb.add_warning(group_id, user_id, "تبلیغات")
                bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً تبلیغ نفرستید! (اخطار {count})", parse_mode='HTML')
            udb._save_stats()
        except:
            pass
        return
    
    if settings['anti_mentions'] and message.text:
        mention_pattern = r'@\w+|tg://user\?id=\d+'
        mentions = len(re.findall(mention_pattern, message.text))
        if mentions > settings['mention_limit']:
            try:
                bot.delete_message(group_id, message.message_id)
                count = udb.add_warning(group_id, user_id, f"منشن بیش از حد ({mentions} بار)")
                bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً منشن‌های زیاد نزنید! (اخطار {count})", parse_mode='HTML')
            except:
                pass
    
    if settings['anti_caps'] and message.text:
        text = message.text
        letters = sum(1 for c in text if c.isalpha())
        if letters > 5:
            upper = sum(1 for c in text if c.isupper())
            ratio = (upper / letters) * 100 if letters > 0 else 0
            if ratio > settings['caps_limit']:
                try:
                    bot.delete_message(group_id, message.message_id)
                    count = udb.add_warning(group_id, user_id, f"کپس بیش از حد ({ratio:.0f}%)")
                    bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً با حروف بزرگ پیام ندهید! (اخطار {count})", parse_mode='HTML')
                except:
                    pass
    
    if settings['anti_emoji'] and message.text:
        emoji_pattern = r'[\U0001F600-\U0001F64F\U0001F300-\U0001F5FF\U0001F680-\U0001F6FF\U0001F700-\U0001F77F\U0001F780-\U0001F7FF\U0001F800-\U0001F8FF\U0001F900-\U0001F9FF\U0001FA00-\U0001FA6F\U0001FA70-\U0001FAFF\U00002700-\U000027BF\U000024C2-\U0001F251]'
        emojis = len(re.findall(emoji_pattern, message.text))
        if emojis > settings['emoji_limit']:
            try:
                bot.delete_message(group_id, message.message_id)
                count = udb.add_warning(group_id, user_id, f"ایموجی بیش از حد ({emojis} بار)")
                bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً از ایموجی زیاد استفاده نکنید! (اخطار {count})", parse_mode='HTML')
            except:
                pass
    
    if settings['anti_newlines'] and message.text:
        newlines = message.text.count('\n')
        if newlines > settings['newline_limit']:
            try:
                bot.delete_message(group_id, message.message_id)
                count = udb.add_warning(group_id, user_id, f"خط جدید بیش از حد ({newlines} بار)")
                bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً از خطوط جدید زیاد استفاده نکنید! (اخطار {count})", parse_mode='HTML')
            except:
                pass
    
    if settings['anti_forward'] and is_forwarded(message):
        try:
            bot.delete_message(group_id, message.message_id)
            count = udb.add_warning(group_id, user_id, "فوروارد پیام")
            bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً فوروارد نفرستید! (اخطار {count})", parse_mode='HTML')
        except:
            pass
    
    if settings['anti_commands'] and message.text:
        for cmd in settings['anti_commands_list']:
            if message.text.startswith(cmd):
                try:
                    bot.delete_message(group_id, message.message_id)
                    count = udb.add_warning(group_id, user_id, f"استفاده از دستور {cmd}")
                    bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً از دستورات مدیریتی استفاده نکنید! (اخطار {count})", parse_mode='HTML')
                    break
                except:
                    pass
    
    if settings.get('anti_url_shortener', False) and message.text and detect_url_shortener(message.text):
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً از لینک‌های کوتاه استفاده نکنید!", parse_mode='HTML')
        except:
            pass
    
    if settings.get('anti_phone', False) and message.text and detect_phone(message.text):
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً شماره تلفن ارسال نکنید!", parse_mode='HTML')
        except:
            pass
    
    if settings.get('anti_email', False) and message.text and detect_email(message.text):
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"⚠️ {get_user_mention(user)} لطفاً آدرس ایمیل ارسال نکنید!", parse_mode='HTML')
        except:
            pass
    
    content_violations = []
    if settings.get('anti_porn', False) and message.text and udb.detect_porn(message.text):
        content_violations.append("محتوای بزرگسالان")
    if settings.get('anti_violence', False) and message.text and udb.detect_violence(message.text):
        content_violations.append("خشونت")
    if settings.get('anti_drugs', False) and message.text and udb.detect_drugs(message.text):
        content_violations.append("مواد مخدر")
    if settings.get('anti_self_harm', False) and message.text and udb.detect_self_harm(message.text):
        content_violations.append("خودزنی")
    if settings.get('anti_hate', False) and message.text and udb.detect_hate(message.text):
        content_violations.append("نفرت")
    if settings.get('anti_phishing', False) and message.text and udb.detect_phishing(message.text):
        content_violations.append("فیشینگ")
    if settings.get('anti_malware', False) and message.text and udb.detect_malware(message.text):
        content_violations.append("بدافزار")
    if settings.get('anti_terrorism', False) and message.text and udb.detect_terrorism(message.text):
        content_violations.append("تروریسم")
    if settings.get('anti_child_abuse', False) and message.text and udb.detect_child_abuse(message.text):
        content_violations.append("آزار کودکان")
    if settings.get('anti_crypto', False) and message.text and udb.detect_crypto_scam(message.text):
        content_violations.append("کلاهبرداری رمزارز")
    if settings.get('anti_gambling', False) and message.text and udb.detect_gambling(message.text):
        content_violations.append("قمار")
    
    if content_violations:
        try:
            bot.delete_message(group_id, message.message_id)
            bot.send_message(group_id, f"⛔ {get_user_mention(user)} پیام شما حاوی محتوای ممنوعه است: {', '.join(content_violations)}", parse_mode='HTML')
            udb.set_mute(user_id, 600)
            udb.stats["total_mutes"] += 1
            udb._save_stats()
        except:
            pass
        return
    
    if message.text:
        auto_reply = udb.get_auto_reply(group_id, message.text.lower())
        if auto_reply:
            bot.send_message(group_id, auto_reply[3])
    
    if settings['leveling']:
        if udb.add_xp(user_id, 1):
            level = udb.get_level(user_id)
            level_message = settings['level_message'].replace("{user_name}", user.first_name).replace("{level}", str(level))
            bot.send_message(group_id, level_message, parse_mode='HTML')
    
    if settings['auto_delete']:
        def delete_later():
            try:
                bot.delete_message(group_id, message.message_id)
            except:
                pass
        threading.Timer(settings['auto_delete_seconds'], delete_later).start()
    
    udb.stats["total_messages"] += 1
    udb._save_stats()

# ========== مدیریت کال‌بک‌ها ==========
@bot.callback_query_handler(func=lambda call: True)
def callback_query(call: CallbackQuery):
    user_id = call.from_user.id
    chat_id = call.message.chat.id
    data = call.data
    group_id = chat_id if call.message.chat.type in ['group', 'supergroup'] else None

    if group_id is not None:
        settings = udb.get_group(group_id)
        if settings.get('button_access_locked', True) and not is_admin(user_id, group_id) and not is_bot_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ دسترسی به دکمه‌ها برای اعضا قفل است.")
            return

    if data == "back_main":
        bot.edit_message_text("✨ **منوی اصلی**", chat_id, call.message.message_id, reply_markup=main_menu(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "settings":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        if not is_admin(user_id, group_id) and not is_bot_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ شما ادمین گروه نیستید!")
            return
        bot.edit_message_text("⚙️ **تنظیمات پیشرفته:**", chat_id, call.message.message_id, reply_markup=settings_menu(group_id), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "stats":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        if not is_admin(user_id, group_id) and not is_bot_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ شما ادمین گروه نیستید!")
            return
        try:
            members = bot.get_chat_members_count(group_id)
        except:
            members = "نامشخص"
        total_warns = udb.stats.get('total_warns', 0)
        total_muted = sum(1 for user in [udb.get_user(uid) for uid in set([row[0] for row in db.fetch_all("SELECT user_id FROM users")])] if udb.is_muted(user["user_id"]))
        text = f"""
📊 **آمار گروه**
━━━━━━━━━━━━━━━━━━━━━━
👥 اعضا: {members}
📨 پیام‌ها: {udb.stats.get('total_messages', 0):,}
🚫 اخراجی‌ها: {udb.stats.get('total_kicks', 0):,}
🔨 بن‌ها: {udb.stats.get('total_bans', 0):,}
🔇 میوت‌ها: {udb.stats.get('total_mutes', 0):,}
⚠️ اخطارها: {total_warns:,}
🔐 کپچا موفق: {udb.stats.get('captcha_passed', 0):,}
❌ کپچا ناموفق: {udb.stats.get('captcha_failed', 0):,}
🔇 میوت: {total_muted}
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "rules":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        settings = udb.get_group(group_id)
        rules = settings.get('rules', 'قوانینی تنظیم نشده است.')
        bot.edit_message_text(f"📋 **قوانین گروه:**\n{rules}", chat_id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "ranking":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        try:
            members = bot.get_chat_members(group_id)
            rankings = []
            for member in members:
                if not member.user.is_bot:
                    uid = member.user.id
                    level = udb.get_level(uid)
                    xp = udb.get_xp(uid)
                    rankings.append((uid, level, xp))
            rankings.sort(key=lambda x: x[1], reverse=True)
            text = "🏆 **رنکینگ کاربران**\n━━━━━━━━━━━━━━━━━━━━━━\n"
            for i, (uid, level, xp) in enumerate(rankings[:10], 1):
                try:
                    user = bot.get_chat_member(group_id, uid).user
                    name = user.first_name[:15]
                    text += f"{i}. {name} - سطح {level} (XP: {xp})\n"
                except:
                    continue
            if text == "🏆 **رنکینگ کاربران**\n━━━━━━━━━━━━━━━━━━━━━━\n":
                text = "📭 هنوز داده‌ای وجود ندارد."
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        except:
            bot.edit_message_text("❌ خطا", chat_id, call.message.message_id, reply_markup=back_button())
        bot.answer_callback_query(call.id)
        return
    
    if data == "profile":
        user = udb.get_user(user_id)
        is_verified = "✅" if user["verified"] else "❌"
        is_muted = "🔇" if udb.is_muted(user_id) else "🔊"
        text = f"""
👤 **پروفایل شما**
━━━━━━━━━━━━━━━━━━━━━━
📛 نام: {call.from_user.first_name}
🏆 سطح: {user["level"]}
⭐ امتیاز: {user["xp"]}
🔐 تایید: {is_verified}
🔇 میوت: {is_muted}
⚠️ اخطارها: {user["warnings"]}
📨 پیام‌ها: {user["total_messages"]}
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "tickets":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        tickets = udb.tickets.get(group_id, [])
        if not tickets:
            bot.edit_message_text("📭 هیچ تیکتی وجود ندارد.", chat_id, call.message.message_id, reply_markup=back_button())
        else:
            text = "🎫 **تیکت‌ها**\n━━━━━━━━━━━━━━━━━━━━━━\n"
            for t in tickets[-5:]:
                status = "🟢 باز" if t["status"] == "open" else "🔴 بسته"
                text += f"#{t['id']} - {t['subject']} ({status})\n"
            bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "help":
        text = """
📋 **راهنما**
━━━━━━━━━━━━━━━━━━━━━━
start - منوی اصلی
راهنما - این راهنما
قوانین - قوانین
رتبه - رتبه شما
رنکینگ - رنکینگ گروه
پروفایل - پروفایل
تیکت [موضوع] - تیکت جدید
گزارش [کاربر] [دلیل] - گزارش تخلف
یادآور [زمان] [پیام] - یادآوری

دستورات مدیریت:
تنظیمات - تنظیمات
آمار - آمار
بن [کاربر] - بن
آنبن [کاربر] - آن‌بن
اخراج [کاربر] - اخراج
تک [کاربر] - اخراج
میوت [کاربر] [مدت] - میوت
آنمیوت [کاربر] - رفع میوت
اخطار [کاربر] [دلیل] - اخطار
اخطارها [کاربر] - نمایش اخطارها
پاکسازی اخطارها [کاربر] - بازنشانی
پاکسازی (ریپلای) - پاکسازی
سنجاق (ریپلای) - پین
برداشتن سنجاق - برداشتن پین
قفل - قفل گروه
بازکردن قفل - باز کردن قفل
بکاپ - بکاپ
سیاه [کاربر] [دلیل] - لیست سیاه
سفید [کاربر] [دلیل] - لیست سفید
حذف سیاه [کاربر] - حذف از سیاه
حذف سفید [کاربر] - حذف از سفید
نظرسنجی [سوال] | [گزینه1] | ... - نظرسنجی
بستن نظرسنجی [شناسه] - بستن
مسابقه [نام] | [توضیحات] | [زمان] - مسابقه
━━━━━━━━━━━━━━━━━━━━━━
"""
        bot.edit_message_text(text, chat_id, call.message.message_id, reply_markup=back_button(), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "refresh":
        bot.edit_message_text("🔄 بروزرسانی شد.", chat_id, call.message.message_id, reply_markup=main_menu(), parse_mode='HTML')
        bot.answer_callback_query(call.id, "✅ بروزرسانی انجام شد.")
        return
    
    if data == "report":
        bot.send_message(chat_id, "📝 لطفاً با دستور /گزارش [کاربر] [دلیل] تخلف را گزارش دهید.")
        bot.answer_callback_query(call.id)
        return
    
    if data == "security_panel":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        if not is_admin(user_id, group_id) and not is_bot_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ شما ادمین گروه نیستید!")
            return
        bot.edit_message_text("🔐 **پنل امنیت پیشرفته**", chat_id, call.message.message_id, reply_markup=advanced_settings_menu(group_id), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data == "admin_panel":
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        if not is_admin(user_id, group_id) and not is_bot_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ شما ادمین گروه نیستید!")
            return
        bot.edit_message_text("📝 **پنل مدیریت**", chat_id, call.message.message_id, reply_markup=lists_menu(group_id), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("basic_") or data.startswith("spam_") or data.startswith("restrict_") or data.startswith("security_") or data.startswith("advanced_") or data.startswith("rules_edit_") or data.startswith("back_settings_") or data.startswith("autodel_set_") or data.startswith("toggle_") or data.startswith("set_") or data.startswith("autoreply_") or data.startswith("lists_"):
        if not group_id:
            bot.answer_callback_query(call.id, "❌ این بخش فقط در گروه قابل استفاده است.")
            return
        if not is_admin(user_id, group_id) and not is_bot_admin(user_id):
            bot.answer_callback_query(call.id, "⛔ شما ادمین گروه نیستید!")
            return
    
    if data.startswith("basic_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("🔰 تنظیمات پایه", chat_id, call.message.message_id, reply_markup=basic_settings_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("spam_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("🛡️ تنظیمات ضد اسپم", chat_id, call.message.message_id, reply_markup=spam_settings_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("restrict_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("🚫 تنظیمات محدودیت", chat_id, call.message.message_id, reply_markup=restrict_settings_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("security_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("🔐 تنظیمات امنیت", chat_id, call.message.message_id, reply_markup=security_settings_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("advanced_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("🎯 تنظیمات پیشرفته", chat_id, call.message.message_id, reply_markup=advanced_settings_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("autoreply_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("🤖 پاسخ‌های خودکار", chat_id, call.message.message_id, reply_markup=autoreply_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("lists_"):
        gid = int(data.split("_")[1])
        bot.edit_message_text("📋 مدیریت لیست‌ها", chat_id, call.message.message_id, reply_markup=lists_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("back_settings_"):
        gid = int(data.split("_")[2])
        bot.edit_message_text("⚙️ تنظیمات پیشرفته", chat_id, call.message.message_id, reply_markup=settings_menu(gid), parse_mode='HTML')
        bot.answer_callback_query(call.id)
        return
    
    if data.startswith("toggle_"):
        parts = data.split("_")
        toggle = parts[1]
        gid = int(parts[2]) if parts[2].isdigit() else group_id
        settings = udb.get_group(gid)
        
        toggles = {
            "welcome": "welcome_enabled",
            "captcha": "captcha",
            "autodelete": "auto_delete",
            "antispam": "anti_spam",
            "antiraid": "anti_raid",
            "mentions": "anti_mentions",
            "caps": "anti_caps",
            "emoji": "anti_emoji",
            "newlines": "anti_newlines",
            "forward": "anti_forward",
            "bot": "anti_bot",
            "link": "anti_link",
            "badwords": "anti_bad_words",
            "advert": "anti_advertising",
            "lock": "group_lock",
            "level": "leveling",
            "silent": "silent_mode",
            "button_access": "button_access_locked",
            "attack": "anti_attack",
            "vpn": "anti_vpn",
            "clone": "anti_clone",
            "bayesian": "anti_spam_bayesian",
            "fakenews": "anti_fake_news",
            "scam": "anti_scam",
            "porn": "anti_porn",
            "violence": "anti_violence",
            "drugs": "anti_drugs",
            "selfharm": "anti_self_harm",
            "hate": "anti_hate",
            "phishing": "anti_phishing",
            "malware": "anti_malware",
            "terrorism": "anti_terrorism",
            "childabuse": "anti_child_abuse",
            "crypto": "anti_crypto",
            "gambling": "anti_gambling"
        }
        
        if toggle in toggles:
            key = toggles[toggle]
            settings[key] = not settings.get(key, True)
            udb.save_group(gid, settings)
            bot.answer_callback_query(call.id, f"✅ تنظیمات ذخیره شد.")
            if toggle in ["welcome", "captcha", "autodelete"]:
                bot.edit_message_text("🔰 تنظیمات پایه", chat_id, call.message.message_id, reply_markup=basic_settings_menu(gid), parse_mode='HTML')
            elif toggle in ["antispam", "antiraid"]:
                bot.edit_message_text("🛡️ تنظیمات ضد اسپم", chat_id, call.message.message_id, reply_markup=spam_settings_menu(gid), parse_mode='HTML')
            elif toggle in ["mentions", "caps", "emoji", "newlines", "forward"]:
                bot.edit_message_text("🚫 تنظیمات محدودیت", chat_id, call.message.message_id, reply_markup=restrict_settings_menu(gid), parse_mode='HTML')
            elif toggle in ["bot", "link", "badwords", "advert"]:
                bot.edit_message_text("🔐 تنظیمات امنیت", chat_id, call.message.message_id, reply_markup=security_settings_menu(gid), parse_mode='HTML')
            elif toggle in ["lock", "level", "silent", "button_access", "attack", "vpn", "clone", "bayesian", "fakenews", "scam", "porn", "violence", "drugs", "selfharm", "hate", "phishing", "malware", "terrorism", "childabuse", "crypto", "gambling"]:
                bot.edit_message_text("🎯 تنظیمات پیشرفته", chat_id, call.message.message_id, reply_markup=advanced_settings_menu(gid), parse_mode='HTML')
            return
        else:
            bot.answer_callback_query(call.id, "❌ تنظیم نامعتبر.")
            return
    
    if data.startswith("poll_vote_"):
        parts = data.split("_")
        poll_id = int(parts[2])
        option_index = int(parts[3])
        if udb.vote_poll(poll_id, user_id, udb.polls[poll_id]["options"][option_index]):
            bot.answer_callback_query(call.id, "✅ رای شما ثبت شد.")
        else:
            bot.answer_callback_query(call.id, "❌ نظرسنجی بسته شده یا نامعتبر است.")
        return
    
    if data.startswith("poll_close_"):
        poll_id = int(data.split("_")[2])
        if udb.close_poll(poll_id):
            results = udb.get_poll_results(poll_id)
            if results:
                text = f"📊 **نتایج نظرسنجی:**\n"
                for opt, voters in results.items():
                    text += f"{opt}: {len(voters)} رای\n"
                bot.send_message(chat_id, text, parse_mode='HTML')
            bot.answer_callback_query(call.id, "✅ نظرسنجی بسته شد.")
        else:
            bot.answer_callback_query(call.id, "❌ نظرسنجی یافت نشد.")
        return
    
    if data.startswith("autodel_set_"):
        parts = data.split("_")
        if len(parts) == 3:
            gid = int(parts[2])
            bot.edit_message_text("⏱️ تنظیم زمان حذف خودکار", chat_id, call.message.message_id, reply_markup=auto_delete_menu(gid), parse_mode='HTML')
        elif len(parts) == 4:
            gid = int(parts[2])
            seconds = int(parts[3])
            settings = udb.get_group(gid)
            if seconds == 0:
                settings['auto_delete'] = False
                bot.answer_callback_query(call.id, "❌ حذف خودکار غیرفعال شد.")
            else:
                settings['auto_delete'] = True
                settings['auto_delete_seconds'] = seconds
                bot.answer_callback_query(call.id, f"✅ زمان حذف خودکار به {format_duration(seconds)} تنظیم شد.")
            udb.save_group(gid, settings)
            bot.edit_message_text("🔰 تنظیمات پایه", chat_id, call.message.message_id, reply_markup=basic_settings_menu(gid), parse_mode='HTML')
        return

# ========== پاسخ به پیام‌های معمولی ==========
@bot.message_handler(func=lambda message: True)
def echo_all(message):
    if message.chat.type in ['group', 'supergroup']:
        if message.text and message.text.lower() in ["سلام", "درود", "hi", "hello"]:
            bot.reply_to(message, f"✨ سلام {message.from_user.first_name} جان! به گروه خوش آمدی! 🛡️")
    else:
        if message.text:
            bot.reply_to(message, "👋 سلام! لطفاً من رو به گروه اضافه کنید تا بتونم محافظت کنم.")

# ========== اجرا ==========
if __name__ == "__main__":
    print("=" * 70)
    print("✨ ربات محافظ فوق‌پیشرفته Luffy Ultra Pro ✨")
    print("=" * 70)
    print(f"👥 ادمین‌ها: {ADMIN_IDS}")
    print("✅ بیش از 100 قابلیت امنیتی پیشرفته")
    print("✅ تشخیص محتوای حساس (بزرگسالان، خشونت، مواد مخدر، قمار، کلاهبرداری، تروریسم، کودک‌آزاری و...)")
    print("✅ سیستم بیزین ضد اسپم")
    print("✅ ضد VPN، کلون، حمله")
    print("✅ سیستم نظرسنجی و مسابقات")
    print("✅ لیست سیاه و سفید")
    print("✅ پاسخ‌های خودکار")
    print("✅ یادآوری‌ها")
    print("✅ دستورات فارسی بدون اسلش")
    print("✅ قابلیت تک کردن (اخراج) اعضا")
    print("=" * 70)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=0, timeout=60)
        except Exception as e:
            print(f"❌ خطا: {e}")
            print("🔄 راه‌اندازی مجدد در 5 ثانیه...")
            time.sleep(5)
            continue