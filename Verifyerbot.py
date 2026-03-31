#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Telegram Group Verification Bot - No External Modules Required
# File: verifier.py

import sqlite3
import json
import urllib.request
import urllib.parse
import random
import re
import threading
import time
import logging
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Optional, Tuple, List, Dict

# ============= কনফিগারেশন (এখানে তোমার তথ্য দাও) =============
BOT_TOKEN = "8691749735:AAEjY95anTeR0v6a4vB9t4HHqajWgrQrElo"  # তোমার বট টোকেন
ADMIN_ID = 7134813314  # তোমার টেলিগ্রাম আইডি
SMS_API_USER = "212313"  # SMS API ইউজার
SMS_API_KEY = "b564b0ffd61fb5ee89a02dae5fe01cae"  # SMS API কী
# ============================================================

# ডাটাবেস ফাইলের নাম
DB_FILE = "verification.db"

# লগিং সেটআপ
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ওয়েটহুক সেটআপ (VPS এর IP দিতে হবে)
WEBHOOK_HOST = "0.0.0.0"  # তোমার VPS এর IP
WEBHOOK_PORT = 8443
WEBHOOK_URL = f"https://{WEBHOOK_HOST}:{WEBHOOK_PORT}"

# ============= ডাটাবেস ফাংশন =============
def init_db():
    """ডাটাবেস টেবিল তৈরি করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # ইউজার টেবিল
    c.execute('''CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        telegram_id INTEGER UNIQUE NOT NULL,
        phone TEXT,
        full_name TEXT,
        username TEXT,
        chat_id INTEGER,
        verified INTEGER DEFAULT 0,
        otp_code TEXT,
        otp_expiry TEXT,
        banned INTEGER DEFAULT 0,
        joined_date TEXT DEFAULT CURRENT_TIMESTAMP,
        verified_date TEXT
    )''')
    
    # গ্রুপ টেবিল
    c.execute('''CREATE TABLE IF NOT EXISTS groups (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER UNIQUE NOT NULL,
        group_title TEXT,
        added_date TEXT DEFAULT CURRENT_TIMESTAMP
    )''')
    
    conn.commit()
    conn.close()
    logger.info("ডাটাবেস সেটআপ সম্পন্ন")

def add_user(telegram_id: int, full_name: str, username: str, chat_id: int):
    """নতুন ইউজার যোগ করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    try:
        c.execute('''INSERT OR IGNORE INTO users (telegram_id, full_name, username, chat_id) 
                     VALUES (?, ?, ?, ?)''', 
                  (telegram_id, full_name, username or "", chat_id))
        conn.commit()
    except Exception as e:
        logger.error(f"ইউজার যোগ করতে ব্যর্থ: {e}")
    finally:
        conn.close()

def save_otp(telegram_id: int, otp: str):
    """OTP সেভ করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    expiry = (datetime.now() + timedelta(minutes=5)).isoformat()
    
    c.execute('''UPDATE users SET otp_code = ?, otp_expiry = ? WHERE telegram_id = ?''',
              (otp, expiry, telegram_id))
    conn.commit()
    conn.close()

def verify_user_with_otp(telegram_id: int, otp: str) -> bool:
    """OTP ভেরিফাই করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''SELECT otp_code, otp_expiry FROM users 
                 WHERE telegram_id = ? AND verified = 0''', (telegram_id,))
    row = c.fetchone()
    
    if row:
        stored_otp, expiry = row
        if stored_otp == otp and datetime.now() < datetime.fromisoformat(expiry):
            c.execute('''UPDATE users SET verified = 1, verified_date = CURRENT_TIMESTAMP, 
                         otp_code = NULL, otp_expiry = NULL WHERE telegram_id = ?''', 
                      (telegram_id,))
            conn.commit()
            conn.close()
            return True
    
    conn.close()
    return False

def update_user_phone(telegram_id: int, phone: str):
    """ইউজারের ফোন নাম্বার আপডেট করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE users SET phone = ? WHERE telegram_id = ?', (phone, telegram_id))
    conn.commit()
    conn.close()

def get_user(telegram_id: int) -> Optional[Dict]:
    """ইউজারের তথ্য পাওয়া"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT telegram_id, full_name, username, phone, verified, banned FROM users WHERE telegram_id = ?', 
              (telegram_id,))
    row = c.fetchone()
    conn.close()
    
    if row:
        return {
            'telegram_id': row[0],
            'full_name': row[1],
            'username': row[2],
            'phone': row[3],
            'verified': row[4],
            'banned': row[5]
        }
    return None

def is_verified(telegram_id: int) -> bool:
    """ইউজার ভেরিফাইড কিনা চেক করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT verified, banned FROM users WHERE telegram_id = ?', (telegram_id,))
    row = c.fetchone()
    conn.close()
    
    return row is not None and row[0] == 1 and row[1] == 0

def is_banned(telegram_id: int) -> bool:
    """ইউজার ব্যানড কিনা চেক করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT banned FROM users WHERE telegram_id = ?', (telegram_id,))
    row = c.fetchone()
    conn.close()
    return row is not None and row[0] == 1

def ban_user(telegram_id: int):
    """ইউজারকে ব্যান করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE users SET banned = 1 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

def unban_user(telegram_id: int):
    """ইউজারের ব্যান উঠানো"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('UPDATE users SET banned = 0 WHERE telegram_id = ?', (telegram_id,))
    conn.commit()
    conn.close()

def get_all_verified_users() -> List[Tuple]:
    """সকল ভেরিফাইড ইউজারের তালিকা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('''SELECT telegram_id, full_name, username, phone, verified_date 
                 FROM users WHERE verified = 1 AND banned = 0 
                 ORDER BY verified_date DESC''')
    rows = c.fetchall()
    conn.close()
    return rows

def get_stats() -> dict:
    """পরিসংখ্যান পাওয়া"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    c.execute('SELECT COUNT(*) FROM users')
    total = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE verified = 1')
    verified = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE banned = 1')
    banned = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM users WHERE verified = 0 AND banned = 0')
    pending = c.fetchone()[0]
    
    c.execute('SELECT COUNT(*) FROM groups')
    groups = c.fetchone()[0]
    
    conn.close()
    
    return {
        'total': total,
        'verified': verified,
        'banned': banned,
        'pending': pending,
        'groups': groups
    }

def auto_ban_unverified():
    """২ দিন পর অনভেরিফাইড ইউজারদের ব্যান করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    two_days_ago = (datetime.now() - timedelta(days=2)).isoformat()
    c.execute('''UPDATE users SET banned = 1 
                 WHERE verified = 0 AND joined_date < ?''', (two_days_ago,))
    affected = c.rowcount
    conn.commit()
    conn.close()
    
    if affected > 0:
        logger.info(f"{affected} জন অনভেরিফাইড ইউজার ব্যান করা হয়েছে")
    return affected

def add_group(group_id: int, group_title: str):
    """গ্রুপ যোগ করা"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('INSERT OR IGNORE INTO groups (group_id, group_title) VALUES (?, ?)', 
              (group_id, group_title))
    conn.commit()
    conn.close()

# ============= টেলিগ্রাম API ফাংশন =============
def telegram_api(method: str, params: Dict = None) -> Optional[Dict]:
    """টেলিগ্রাম API কল করা"""
    if params is None:
        params = {}
    
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{method}"
    
    try:
        data = urllib.parse.urlencode(params).encode()
        req = urllib.request.Request(url, data=data, method='POST')
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode())
            return result.get('result')
    except Exception as e:
        logger.error(f"টেলিগ্রাম API কল ব্যর্থ: {e}")
        return None

def send_message(chat_id: int, text: str, reply_markup: Dict = None, parse_mode: str = "Markdown") -> bool:
    """মেসেজ পাঠানো"""
    params = {
        'chat_id': chat_id,
        'text': text,
        'parse_mode': parse_mode
    }
    
    if reply_markup:
        params['reply_markup'] = json.dumps(reply_markup)
    
    result = telegram_api('sendMessage', params)
    return result is not None

def delete_message(chat_id: int, message_id: int) -> bool:
    """মেসেজ ডিলিট করা"""
    result = telegram_api('deleteMessage', {
        'chat_id': chat_id,
        'message_id': message_id
    })
    return result is not None

def get_chat_member(chat_id: int, user_id: int) -> Optional[Dict]:
    """চ্যাট মেম্বারের তথ্য পাওয়া"""
    result = telegram_api('getChatMember', {
        'chat_id': chat_id,
        'user_id': user_id
    })
    return result

def set_webhook(webhook_url: str) -> bool:
    """ওয়েবহুক সেট করা"""
    result = telegram_api('setWebhook', {'url': webhook_url})
    return result is not None

# ============= এসএমএস ফাংশন =============
def send_sms(phone: str, otp: str) -> Tuple[bool, str]:
    """এসএমএস পাঠানো (urllib ব্যবহার করে)"""
    msg = f"Your verification code is: {otp}"
    url = f"https://sendmysms.net/api.php?user={SMS_API_USER}&key={SMS_API_KEY}&to={phone}&msg={urllib.parse.quote(msg)}"
    
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, timeout=15) as response:
            data = json.loads(response.read().decode())
            
            if data.get('status') == 'OK':
                return True, "SMS পাঠানো সফল"
            else:
                return False, f"API error: {data}"
    except Exception as e:
        return False, str(e)

# ============= ইনলাইন কিবোর্ড বানানো =============
def get_contact_keyboard():
    """কন্টাক্ট শেয়ার বাটন"""
    return {
        'inline_keyboard': [
            [{'text': '📱 ফোন নাম্বার শেয়ার করুন', 'request_contact': True}]
        ]
    }

def get_admin_keyboard():
    """এডমিন প্যানেল বাটন"""
    return {
        'inline_keyboard': [
            [{'text': '📊 পরিসংখ্যান', 'callback_data': 'stats'}],
            [{'text': '👥 ভেরিফাইড ইউজার', 'callback_data': 'users'}],
            [{'text': '🚫 ইউজার ব্যান', 'callback_data': 'ban'}],
            [{'text': '🔓 ইউজার আনব্যান', 'callback_data': 'unban'}],
            [{'text': '📢 ব্রডকাস্ট', 'callback_data': 'broadcast'}]
        ]
    }

# ============= মেসেজ প্রসেসিং =============
def process_update(update: Dict):
    """টেলিগ্রাম আপডেট প্রসেস করা"""
    
    # মেসেজ হ্যান্ডলার
    if 'message' in update:
        message = update['message']
        chat = message.get('chat', {})
        chat_id = chat.get('id')
        user = message.get('from', {})
        user_id = user.get('id')
        text = message.get('text', '')
        
        # কমান্ড প্রসেস
        if text and text.startswith('/'):
            process_command(chat_id, user_id, text, message)
            return
        
        # কন্টাক্ট হ্যান্ডলার
        if 'contact' in message:
            process_contact(chat_id, user_id, message)
            return
        
        # টেক্সট মেসেজ (OTP চেক)
        if text and text.isdigit() and len(text) == 6:
            process_otp(chat_id, user_id, text)
            return
        
        # গ্রুপ মেসেজ হ্যান্ডলার
        if chat.get('type') in ['group', 'supergroup']:
            process_group_message(chat_id, user_id, message)
            return
        
        # সাধারণ টেক্সট রেসপন্স
        if chat.get('type') == 'private':
            send_message(chat_id, "👋 হ্যালো! /start দিন শুরু করতে।")
    
    # কলব্যাক কুয়েরি হ্যান্ডলার
    elif 'callback_query' in update:
        callback = update['callback_query']
        user_id = callback['from']['id']
        message = callback['message']
        chat_id = message['chat']['id']
        data = callback['data']
        
        process_callback(chat_id, user_id, message['message_id'], data)
    
    # গ্রুপে বট এড হওয়া
    if 'message' in update and 'new_chat_members' in update['message']:
        for member in update['message']['new_chat_members']:
            if member.get('id') == BOT_TOKEN.split(':')[0]:
                add_group(chat_id, chat.get('title', 'Unknown'))
                send_message(chat_id, 
                    "✅ *বট সফলভাবে এড হয়েছে!*\n\n"
                    "আমি এই গ্রুপে ভেরিফিকেশন এনফোর্স করব।\n\n"
                    "📌 *নিয়ম:*\n"
                    "• সবাইকে বটে গিয়ে ফোন নাম্বার ভেরিফাই করতে হবে\n"
                    "• অনভেরিফাইড ইউজারদের মেসেজ ডিলিট হবে\n"
                    "• ২ দিনের মধ্যে ভেরিফাই না করলে ব্যান\n\n"
                    "ভেরিফাই করতে বটে /start দিন।",
                    parse_mode='Markdown')

def process_command(chat_id: int, user_id: int, text: str, message: Dict):
    """কমান্ড প্রসেস করা"""
    
    if text == '/start':
        # ইউজার যোগ করা
        user = message.get('from', {})
        add_user(user_id, user.get('first_name', '') + ' ' + user.get('last_name', ''), 
                 user.get('username', ''), chat_id)
        
        # ব্যান চেক
        if is_banned(user_id):
            send_message(chat_id, "❌ *আপনি ব্যান করা হয়েছেন!*\n\nকারণ: ২ দিনের মধ্যে ভেরিফাই করেননি।")
            return
        
        # ইতিমধ্যে ভেরিফাইড কিনা
        if is_verified(user_id):
            send_message(chat_id, f"✅ *স্বাগতম!*\n\nআপনি ইতিমধ্যে ভেরিফাইড।\nআপনি এখন গ্রুপে মেসেজ করতে পারবেন।")
            return
        
        # কন্টাক্ট শেয়ার বাটন
        reply_markup = get_contact_keyboard()
        send_message(chat_id, 
            f"👋 *হ্যালো!*\n\n"
            f"গ্রুপে স্প্যাম প্রতিরোধ করতে আপনার ফোন নাম্বার ভেরিফাই করা আবশ্যক।\n\n"
            f"📌 *নিচের ধাপগুলো অনুসরণ করুন:*\n"
            f"1️⃣ 'ফোন নাম্বার শেয়ার করুন' বাটনে ক্লিক করুন\n"
            f"2️⃣ আপনার ফোনে পাঠানো OTP টি দিন\n"
            f"3️⃣ গ্রুপে মেসেজ করা শুরু করুন!\n\n"
            f"⚠️ *সতর্কতা:* ২ দিনের মধ্যে ভেরিফাই না করলে আপনার অ্যাকাউন্ট ব্যান হয়ে যাবে।",
            reply_markup=reply_markup)
    
    elif text == '/admin' and user_id == ADMIN_ID:
        reply_markup = get_admin_keyboard()
        send_message(chat_id, "🔐 *এডমিন প্যানেল*\n\nএকটি অপশন নির্বাচন করুন:", reply_markup=reply_markup)
    
    elif text.startswith('/ban') and user_id == ADMIN_ID:
        parts = text.split()
        if len(parts) > 1:
            try:
                target_id = int(parts[1])
                ban_user(target_id)
                send_message(chat_id, f"✅ ইউজার `{target_id}` ব্যান করা হয়েছে!", parse_mode='Markdown')
            except ValueError:
                send_message(chat_id, "❌ ভুল আইডি! সংখ্যা দিন।")
        else:
            send_message(chat_id, "📝 ব্যবহার: /ban <টেলিগ্রাম_আইডি>")
    
    elif text.startswith('/unban') and user_id == ADMIN_ID:
        parts = text.split()
        if len(parts) > 1:
            try:
                target_id = int(parts[1])
                unban_user(target_id)
                send_message(chat_id, f"✅ ইউজার `{target_id}` আনব্যান করা হয়েছে!", parse_mode='Markdown')
            except ValueError:
                send_message(chat_id, "❌ ভুল আইডি! সংখ্যা দিন。")
        else:
            send_message(chat_id, "📝 ব্যবহার: /unban <টেলিগ্রাম_আইডি>")
    
    elif text.startswith('/broadcast') and user_id == ADMIN_ID:
        msg = text.replace('/broadcast', '', 1).strip()
        if msg:
            conn = sqlite3.connect(DB_FILE)
            c = conn.cursor()
            c.execute('SELECT telegram_id FROM users WHERE verified = 1 AND banned = 0')
            users = c.fetchall()
            conn.close()
            
            success = 0
            for (tg_id,) in users:
                if send_message(tg_id, f"📢 *ব্রডকাস্ট মেসেজ*\n\n{msg}"):
                    success += 1
                time.sleep(0.05)
            
            send_message(chat_id, f"✅ ব্রডকাস্ট শেষ!\n\nপাঠানো হয়েছে: {success}/{len(users)}")
        else:
            send_message(chat_id, "📝 ব্যবহার: /broadcast <মেসেজ>")

def process_contact(chat_id: int, user_id: int, message: Dict):
    """কন্টাক্ট প্রসেস করা"""
    contact = message.get('contact', {})
    
    # নিজের কন্টাক্ট কিনা চেক
    if contact.get('user_id') != user_id:
        send_message(chat_id, "❌ অনুগ্রহ করে আপনার নিজের ফোন নাম্বার শেয়ার করুন!")
        return
    
    phone = contact.get('phone_number', '')
    
    # বাংলাদেশী নাম্বার ভ্যালিডেশন
    if not re.match(r"^01[3-9]\d{8}$", phone):
        send_message(chat_id, "❌ *ভুল ফোন নাম্বার!*\n\nদয়া করে একটি সঠিক বাংলাদেশী নাম্বার দিন (যেমন: 017XXXXXXXX)", parse_mode='Markdown')
        return
    
    # ফোন নাম্বার আপডেট
    update_user_phone(user_id, phone)
    
    # OTP জেনারেট
    otp = str(random.randint(100000, 999999))
    save_otp(user_id, otp)
    
    # SMS পাঠান
    success, msg = send_sms(phone, otp)
    
    if success:
        send_message(chat_id, f"✅ *OTP পাঠানো হয়েছে!*\n\n📱 নাম্বার: `{phone}`\n🔑 OTP: `{otp}`\n\n⚠️ OTP ৫ মিনিটের মধ্যে মেয়াদ শেষ হবে।\n\nএখন আপনার ৬ ডিজিটের OTP টি লিখুন:", parse_mode='Markdown')
    else:
        send_message(chat_id, f"❌ *SMS পাঠানো ব্যর্থ!*\n\nত্রুটি: {msg}\n\nআপনার OTP: `{otp}`\nএই কোডটি লিখে ভেরিফাই করুন।", parse_mode='Markdown')

def process_otp(chat_id: int, user_id: int, otp: str):
    """OTP প্রসেস করা"""
    if verify_user_with_otp(user_id, otp):
        send_message(chat_id, "✅ *ভেরিফিকেশন সফল!*\n\nআপনি এখন গ্রুপে মেসেজ করতে পারবেন।\nধন্যবাদ! 🎉", parse_mode='Markdown')
    else:
        send_message(chat_id, "❌ *ভুল বা মেয়াদ উত্তীর্ণ OTP!*\n\nআবার চেষ্টা করতে /start দিন।", parse_mode='Markdown')

def process_group_message(chat_id: int, user_id: int, message: Dict):
    """গ্রুপ মেসেজ প্রসেস করা"""
    
    # বট নিজে ইগনোর
    if str(user_id) == BOT_TOKEN.split(':')[0]:
        return
    
    # এডমিন চেক
    member = get_chat_member(chat_id, user_id)
    if member and member.get('status') in ['administrator', 'creator']:
        return
    
    # ভেরিফাইড কিনা চেক
    if not is_verified(user_id):
        message_id = message.get('message_id')
        if message_id:
            delete_message(chat_id, message_id)
        
        send_message(chat_id, f"⚠️ *আপনি ভেরিফাইড নন!*\n\nভেরিফাই করতে বটে /start দিন।\n\n২ দিনের মধ্যে ভেরিফাই না করলে আপনি ব্যান হয়ে যাবেন।", parse_mode='Markdown')

def process_callback(chat_id: int, user_id: int, message_id: int, data: str):
    """কলব্যাক প্রসেস করা"""
    
    if user_id != ADMIN_ID:
        send_message(chat_id, "❌ আপনি এডমিন নন!")
        return
    
    if data == 'stats':
        stats = get_stats()
        text = (f"📊 *বট পরিসংখ্যান*\n\n"
                f"👥 মোট ইউজার: {stats['total']}\n"
                f"✅ ভেরিফাইড: {stats['verified']}\n"
                f"⏳ অপেক্ষমাণ: {stats['pending']}\n"
                f"🚫 ব্যানড: {stats['banned']}\n"
                f"👥 গ্রুপ: {stats['groups']}")
        send_message(chat_id, text, parse_mode='Markdown')
    
    elif data == 'users':
        users = get_all_verified_users()
        
        if not users:
            send_message(chat_id, "কোনো ভেরিফাইড ইউজার নেই!")
            return
        
        text = "👥 *ভেরিফাইড ইউজার লিস্ট*\n\n"
        for i, (tg_id, name, username, phone, date) in enumerate(users[:30], 1):
            text += f"{i}. *{name}*\n"
            text += f"   🆔 `{tg_id}`\n"
            if phone:
                text += f"   📱 {phone}\n"
            if username:
                text += f"   @{username}\n"
            text += f"   📅 {date[:10]}\n\n"
        
        if len(users) > 30:
            text += f"\n*এবং আরও {len(users) - 30} জন ইউজার...*"
        
        send_message(chat_id, text, parse_mode='Markdown')
    
    elif data == 'ban':
        send_message(chat_id, "🚫 *ইউজার ব্যান*\n\nইউজার ব্যান করতে: `/ban 123456789`", parse_mode='Markdown')
    
    elif data == 'unban':
        send_message(chat_id, "🔓 *ইউজার আনব্যান*\n\nইউজার আনব্যান করতে: `/unban 123456789`", parse_mode='Markdown')
    
    elif data == 'broadcast':
        send_message(chat_id, "📢 *ব্রডকাস্ট*\n\nব্রডকাস্ট করতে: `/broadcast আপনার মেসেজ`", parse_mode='Markdown')

# ============= ওয়েবহুক সার্ভার =============
class WebhookHandler(BaseHTTPRequestHandler):
    """ওয়েবহুক হ্যান্ডলার"""
    
    def do_POST(self):
        """POST রিকোয়েস্ট হ্যান্ডেল করা"""
        content_length = int(self.headers.get('Content-Length', 0))
        post_data = self.rfile.read(content_length)
        
        try:
            update = json.loads(post_data.decode())
            process_update(update)
        except Exception as e:
            logger.error(f"আপডেট প্রসেস করতে ব্যর্থ: {e}")
        
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'OK')
    
    def log_message(self, format, *args):
        """লগ মেসেজ সাপ্রেস করা"""
        pass

def start_webhook_server():
    """ওয়েবহুক সার্ভার চালু করা"""
    server = HTTPServer((WEBHOOK_HOST, WEBHOOK_PORT), WebhookHandler)
    logger.info(f"ওয়েবহুক সার্ভার চালু হয়েছে {WEBHOOK_HOST}:{WEBHOOK_PORT}")
    server.serve_forever()

# ============= পোলিং মোড (সিম্পল) =============
def polling_mode():
    """পোলিং মোডে বট চালানো (সবচেয়ে সহজ)"""
    logger.info("পোলিং মোড চালু হচ্ছে...")
    
    last_update_id = 0
    
    while True:
        try:
            # আপডেট পাওয়া
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates?offset={last_update_id + 1}&timeout=30"
            req = urllib.request.Request(url, method='GET')
            
            with urllib.request.urlopen(req, timeout=35) as response:
                data = json.loads(response.read().decode())
                result = data.get('result', [])
                
                for update in result:
                    process_update(update)
                    last_update_id = update['update_id']
            
            # অটো ব্যান চেক (প্রতি ঘণ্টায়)
            auto_ban_unverified()
            time.sleep(1)
            
        except Exception as e:
            logger.error(f"পোলিং এরর: {e}")
            time.sleep(5)

# ============= অটো ব্যান থ্রেড =============
def auto_ban_thread():
    """অটো ব্যান ব্যাকগ্রাউন্ড থ্রেড"""
    while True:
        time.sleep(3600)  # প্রতি ঘণ্টায়
        banned = auto_ban_unverified()
        if banned > 0:
            logger.info(f"অটো ব্যান: {banned} জন ইউজার ব্যান হয়েছে")

# ============= মেইন ফাংশন =============
def main():
    """বট চালু করার মেইন ফাংশন"""
    
    # ডাটাবেস initialize
    init_db()
    
    print("=" * 50)
    print("🤖 টেলিগ্রাম ভেরিফিকেশন বট")
    print("=" * 50)
    print(f"✅ ডাটাবেস: {DB_FILE}")
    print(f"👤 এডমিন আইডি: {ADMIN_ID}")
    print(f"📱 SMS API: {'সক্রিয়' if SMS_API_USER and SMS_API_KEY else 'নিষ্ক্রিয়'}")
    print("=" * 50)
    print("🔄 বট চালু হচ্ছে...")
    print("✅ বট চালু আছে! (Ctrl+C বন্ধ করার জন্য)")
    print("=" * 50)
    
    # অটো ব্যান থ্রেড চালু
    ban_thread = threading.Thread(target=auto_ban_thread, daemon=True)
    ban_thread.start()
    
    # পোলিং মোড চালু (সবচেয়ে সহজ)
    polling_mode()

if __name__ == "__main__":
    main()
