#!/usr/bin/env python3
# -*- coding: utf-8 -*-
# Telegram Group Verification Bot - Complete Version
# File: verifier.py

import sqlite3
import requests
import random
import re
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple, List
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ChatMember
from telegram.ext import (
    Application, CommandHandler, MessageHandler, 
    CallbackQueryHandler, filters, ContextTypes
)
from telegram.constants import ChatMemberStatus

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
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
                  (telegram_id, full_name, username, chat_id))
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

# ============= এসএমএস ফাংশন =============
def send_sms(phone: str, otp: str) -> Tuple[bool, str]:
    """এসএমএস পাঠানো"""
    url = f"https://sendmysms.net/api.php?user={SMS_API_USER}&key={SMS_API_KEY}&to={phone}&msg=Your verification code is: {otp}"
    
    try:
        response = requests.get(url, timeout=15)
        data = response.json()
        
        if data.get('status') == 'OK':
            return True, "SMS পাঠানো সফল"
        else:
            return False, f"API error: {data}"
    except Exception as e:
        return False, str(e)

# ============= টেলিগ্রাম হ্যান্ডলার =============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/start কমান্ড হ্যান্ডলার"""
    user = update.effective_user
    chat = update.effective_chat
    
    # ইউজার যোগ করা
    add_user(user.id, user.full_name, user.username, chat.id)
    
    # ব্যান চেক
    if is_banned(user.id):
        await update.message.reply_text(
            "❌ *আপনি ব্যান করা হয়েছেন!*\n\nকারণ: ২ দিনের মধ্যে ভেরিফাই করেননি।",
            parse_mode='Markdown'
        )
        return
    
    # ইতিমধ্যে ভেরিফাইড কিনা
    if is_verified(user.id):
        await update.message.reply_text(
            f"✅ *স্বাগতম {user.first_name}!*\n\nআপনি ইতিমধ্যে ভেরিফাইড।\nআপনি এখন গ্রুপে মেসেজ করতে পারবেন।",
            parse_mode='Markdown'
        )
        return
    
    # কন্টাক্ট শেয়ার বাটন
    keyboard = [[InlineKeyboardButton("📱 ফোন নাম্বার শেয়ার করুন", request_contact=True)]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        f"👋 *হ্যালো {user.first_name}!*\n\n"
        f"গ্রুপে স্প্যাম প্রতিরোধ করতে আপনার ফোন নাম্বার ভেরিফাই করা আবশ্যক।\n\n"
        f"📌 *নিচের ধাপগুলো অনুসরণ করুন:*\n"
        f"1️⃣ 'ফোন নাম্বার শেয়ার করুন' বাটনে ক্লিক করুন\n"
        f"2️⃣ আপনার ফোনে পাঠানো OTP টি দিন\n"
        f"3️⃣ গ্রুপে মেসেজ করা শুরু করুন!\n\n"
        f"⚠️ *সতর্কতা:* ২ দিনের মধ্যে ভেরিফাই না করলে আপনার অ্যাকাউন্ট ব্যান হয়ে যাবে।",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def handle_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """কন্টাক্ট হ্যান্ডলার"""
    contact = update.message.contact
    user = update.effective_user
    
    # নিজের কন্টাক্ট কিনা চেক
    if contact.user_id != user.id:
        await update.message.reply_text("❌ অনুগ্রহ করে আপনার নিজের ফোন নাম্বার শেয়ার করুন!")
        return
    
    phone = contact.phone_number
    
    # বাংলাদেশী নাম্বার ভ্যালিডেশন
    if not re.match(r"^01[3-9]\d{8}$", phone):
        await update.message.reply_text(
            "❌ *ভুল ফোন নাম্বার!*\n\n"
            "দয়া করে একটি সঠিক বাংলাদেশী নাম্বার দিন (যেমন: 017XXXXXXXX)",
            parse_mode='Markdown'
        )
        return
    
    # ফোন নাম্বার আপডেট
    update_user_phone(user.id, phone)
    
    # OTP জেনারেট
    otp = str(random.randint(100000, 999999))
    save_otp(user.id, otp)
    
    # SMS পাঠান
    success, msg = send_sms(phone, otp)
    
    if success:
        await update.message.reply_text(
            f"✅ *OTP পাঠানো হয়েছে!*\n\n"
            f"📱 নাম্বার: `{phone}`\n"
            f"🔑 OTP: `{otp}`\n\n"
            f"⚠️ OTP ৫ মিনিটের মধ্যে মেয়াদ শেষ হবে।\n\n"
            f"এখন নিচে আপনার ৬ ডিজিটের OTP টি লিখুন:",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            f"❌ *SMS পাঠানো ব্যর্থ!*\n\n"
            f"ত্রুটি: {msg}\n\n"
            f"আপনার OTP: `{otp}`\n"
            f"এই কোডটি লিখে ভেরিফাই করুন।",
            parse_mode='Markdown'
        )

async def handle_otp(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """OTP হ্যান্ডলার"""
    user = update.effective_user
    otp = update.message.text.strip()
    
    # শুধু সংখ্যা চেক
    if not otp.isdigit() or len(otp) != 6:
        await update.message.reply_text("❌ দয়া করে সঠিক ৬ ডিজিটের OTP দিন!")
        return
    
    # OTP ভেরিফাই
    if verify_user_with_otp(user.id, otp):
        await update.message.reply_text(
            "✅ *ভেরিফিকেশন সফল!*\n\n"
            "আপনি এখন গ্রুপে মেসেজ করতে পারবেন।\n"
            "ধন্যবাদ! 🎉",
            parse_mode='Markdown'
        )
    else:
        await update.message.reply_text(
            "❌ *ভুল বা মেয়াদ উত্তীর্ণ OTP!*\n\n"
            "আবার চেষ্টা করতে /start দিন।",
            parse_mode='Markdown'
        )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin কমান্ড - শুধু এডমিনের জন্য"""
    user_id = update.effective_user.id
    
    if user_id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    keyboard = [
        [InlineKeyboardButton("📊 পরিসংখ্যান", callback_data="stats")],
        [InlineKeyboardButton("👥 ভেরিফাইড ইউজার", callback_data="users")],
        [InlineKeyboardButton("🚫 ইউজার ব্যান", callback_data="ban")],
        [InlineKeyboardButton("🔓 ইউজার আনব্যান", callback_data="unban")],
        [InlineKeyboardButton("📢 ব্রডকাস্ট", callback_data="broadcast")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🔐 *এডমিন প্যানেল*\n\nএকটি অপশন নির্বাচন করুন:",
        parse_mode='Markdown',
        reply_markup=reply_markup
    )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """এডমিন কলব্যাক হ্যান্ডলার"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    
    if user_id != ADMIN_ID:
        await query.edit_message_text("❌ আপনি এডমিন নন!")
        return
    
    if query.data == "stats":
        stats = get_stats()
        text = (
            f"📊 *বট পরিসংখ্যান*\n\n"
            f"👥 মোট ইউজার: {stats['total']}\n"
            f"✅ ভেরিফাইড: {stats['verified']}\n"
            f"⏳ অপেক্ষমাণ: {stats['pending']}\n"
            f"🚫 ব্যানড: {stats['banned']}\n"
            f"👥 গ্রুপ: {stats['groups']}"
        )
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == "users":
        users = get_all_verified_users()
        
        if not users:
            await query.edit_message_text("কোনো ভেরিফাইড ইউজার নেই!")
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
        
        await query.edit_message_text(text, parse_mode='Markdown')
    
    elif query.data == "ban":
        await query.edit_message_text(
            "🚫 *ইউজার ব্যান*\n\n"
            "ইউজার ব্যান করতে এই ফরম্যাটে দিন:\n"
            "`/ban 123456789`\n\n"
            "নম্বরটি হবে ইউজারের টেলিগ্রাম আইডি।",
            parse_mode='Markdown'
        )
    
    elif query.data == "unban":
        await query.edit_message_text(
            "🔓 *ইউজার আনব্যান*\n\n"
            "ইউজার আনব্যান করতে এই ফরম্যাটে দিন:\n"
            "`/unban 123456789`",
            parse_mode='Markdown'
        )
    
    elif query.data == "broadcast":
        await query.edit_message_text(
            "📢 *ব্রডকাস্ট মেসেজ*\n\n"
            "সব ইউজারকে মেসেজ পাঠাতে এই ফরম্যাটে দিন:\n"
            "`/broadcast আপনার মেসেজ এখানে`",
            parse_mode='Markdown'
        )

async def ban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/ban কমান্ড"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("📝 ব্যবহার: /ban <টেলিগ্রাম_আইডি>")
        return
    
    try:
        target_id = int(context.args[0])
        ban_user(target_id)
        await update.message.reply_text(f"✅ ইউজার `{target_id}` ব্যান করা হয়েছে!", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।")

async def unban_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/unban কমান্ড"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("📝 ব্যবহার: /unban <টেলিগ্রাম_আইডি>")
        return
    
    try:
        target_id = int(context.args[0])
        unban_user(target_id)
        await update.message.reply_text(f"✅ ইউজার `{target_id}` আনব্যান করা হয়েছে!", parse_mode='Markdown')
    except ValueError:
        await update.message.reply_text("❌ ভুল আইডি! সংখ্যা দিন।")

async def broadcast_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/broadcast কমান্ড"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ আপনি এডমিন নন!")
        return
    
    if not context.args:
        await update.message.reply_text("📝 ব্যবহার: /broadcast <মেসেজ>")
        return
    
    message = " ".join(context.args)
    
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('SELECT telegram_id FROM users WHERE verified = 1 AND banned = 0')
    users = c.fetchall()
    conn.close()
    
    success = 0
    failed = 0
    
    await update.message.reply_text(f"📢 ব্রডকাস্ট শুরু... {len(users)} জন ইউজার পাবেন।")
    
    for (tg_id,) in users:
        try:
            await context.bot.send_message(tg_id, f"📢 *ব্রডকাস্ট মেসেজ*\n\n{message}", parse_mode='Markdown')
            success += 1
        except:
            failed += 1
        await asyncio.sleep(0.05)
    
    await update.message.reply_text(f"✅ ব্রডকাস্ট শেষ!\n\nপাঠানো হয়েছে: {success}\nব্যর্থ: {failed}")

async def group_message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """গ্রুপ মেসেজ হ্যান্ডলার - অনভেরিফাইড ইউজারদের মেসেজ ডিলিট করে"""
    message = update.effective_message
    chat = update.effective_chat
    user = update.effective_user
    
    # বট নিজে বা গ্রুপ না হলে ইগনোর
    if not user or user.id == context.bot.id:
        return
    
    # শুধু গ্রুপে কাজ করবে
    if chat.type not in ['group', 'supergroup']:
        return
    
    # এডমিন চেক
    try:
        member = await chat.get_member(user.id)
        if member.status in [ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
            return  # এডমিনরা মেসেজ করতে পারবে
    except:
        pass
    
    # ভেরিফাইড কিনা চেক
    if not is_verified(user.id):
        try:
            await message.delete()
            warn = await message.reply_text(
                f"⚠️ *{user.first_name}*, আপনি ভেরিফাইড নন!\n\n"
                f"ভেরিফাই করতে বটে মেসেজ করুন: @{context.bot.username}\n\n"
                f"২ দিনের মধ্যে ভেরিফাই না করলে আপনি ব্যান হয়ে যাবেন।",
                parse_mode='Markdown'
            )
            await asyncio.sleep(10)
            try:
                await warn.delete()
            except:
                pass
        except Exception as e:
            logger.error(f"মেসেজ ডিলিট করতে ব্যর্থ: {e}")

async def bot_added_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """বট গ্রুপে এড করা হলে"""
    chat = update.effective_chat
    new_members = update.message.new_chat_members
    
    for member in new_members:
        if member.id == context.bot.id:
            add_group(chat.id, chat.title)
            await update.message.reply_text(
                "✅ *বট সফলভাবে এড হয়েছে!*\n\n"
                "আমি এই গ্রুপে ভেরিফিকেশন এনফোর্স করব।\n\n"
                "📌 *নিয়ম:*\n"
                "• সবাইকে বটে গিয়ে ফোন নাম্বার ভেরিফাই করতে হবে\n"
                "• অনভেরিফাইড ইউজারদের মেসেজ ডিলিট হবে\n"
                "• ২ দিনের মধ্যে ভেরিফাই না করলে ব্যান\n\n"
                f"ভেরিফাই করতে: @{context.bot.username}",
                parse_mode='Markdown'
            )
            break

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """এরর হ্যান্ডলার"""
    logger.error(f"আপডেট {update} এরর হয়েছে {context.error}")

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
    
    # অটো ব্যান টাস্ক (ব্যাকগ্রাউন্ডে)
    async def auto_ban_loop():
        while True:
            await asyncio.sleep(3600)  # প্রতি ঘণ্টায়
            banned = auto_ban_unverified()
            if banned > 0:
                logger.info(f"অটো ব্যান: {banned} জন ইউজার ব্যান হয়েছে")
    
    # অ্যাপ্লিকেশন তৈরি
    application = Application.builder().token(BOT_TOKEN).build()
    
    # কমান্ড হ্যান্ডলার
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("ban", ban_command))
    application.add_handler(CommandHandler("unban", unban_command))
    application.add_handler(CommandHandler("broadcast", broadcast_command))
    
    # মেসেজ হ্যান্ডলার
    application.add_handler(MessageHandler(filters.CONTACT, handle_contact))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_otp))
    application.add_handler(MessageHandler(filters.TEXT & filters.ChatType.GROUPS, group_message_handler))
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, bot_added_handler))
    
    # কলব্যাক হ্যান্ডলার
    application.add_handler(CallbackQueryHandler(admin_callback))
    
    # এরর হ্যান্ডলার
    application.add_error_handler(error_handler)
    
    # বট চালানো
    print("✅ বট চালু আছে! (Ctrl+C বন্ধ করার জন্য)")
    print("=" * 50)
    
    # অটো ব্যান লুপ শুরু
    loop = asyncio.get_event_loop()
    loop.create_task(auto_ban_loop())
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
