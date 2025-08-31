from dotenv import load_dotenv
import os
import logging
from typing import List, Dict
from datetime import datetime

from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, ConversationHandler,
    ContextTypes, filters, CallbackQueryHandler
)
from telegram.error import TelegramError

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

PRIMARY_ADMINS_STR = os.getenv("PRIMARY_ADMINS", "")
PRIMARY_ADMINS: List[str] = [a.strip() for a in PRIMARY_ADMINS_STR.split(",") if a.strip()]

SECONDARY_ADMINS_STR = os.getenv("SECONDARY_ADMINS", "")
SECONDARY_ADMINS: List[str] = [a.strip() for a in SECONDARY_ADMINS_STR.split(",") if a.strip()]

SUPER_ADMIN = os.getenv("SUPER_ADMIN")

ADMIN_NAMES = {
    "251634096": "آرمان",
    "393746429": "محمد",
    "5066267255": "زهرا/نسترن",
    "108039886": "غلامی"
}

if not PRIMARY_ADMINS:
    logger.warning("No PRIMARY_ADMINS configured. Messages won't be forwarded.")

GET_MESSAGE = 1

main_buttons = [
    ["📊 فارکس", "💎 کریپتو"],
    ["🏦 طلا/ارز", "📈 آپشن"],
    ["📚 آموزشی"]
]
action_buttons = [
    ["📤 ارسال پیام"],
    ["🔚 اتمام مکالمه"],
    ["↩️ بازگشت", "🏠 خانه"]
]

keyboard = ReplyKeyboardMarkup(main_buttons, resize_keyboard=True)
action_keyboard = ReplyKeyboardMarkup(action_buttons, resize_keyboard=True)

def get_admin_name(admin_id: str) -> str:
    """Get admin display name"""
    return ADMIN_NAMES.get(admin_id, f"ادمین {admin_id}")

def create_delegation_keyboard(message_id: str) -> InlineKeyboardMarkup:
    """Create inline keyboard for delegating to secondary admins"""
    buttons = []
    for admin_id in SECONDARY_ADMINS:
        admin_name = get_admin_name(admin_id)
        buttons.append([InlineKeyboardButton(f"ارسال به {admin_name}", 
                                           callback_data=f"delegate_{admin_id}_{message_id}")])
    return InlineKeyboardMarkup(buttons)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.message.from_user.id)
    
    if user_id in PRIMARY_ADMINS:
        await update.message.reply_text("👑 سلام ادمین اصلی عزیز! به پنل مدیریت ربات وصل شدید ✅")
    elif user_id in SECONDARY_ADMINS:
        admin_name = get_admin_name(user_id)
        await update.message.reply_text(
            f"🔧 سلام {admin_name} عزیز! به پنل پشتیبانی وصل شدید ✅\n\n"
            f"📝 *نحوه پاسخ‌دهی:*\n"
            f"برای پاسخ به کاربری، پیام خود را به این شکل بنویسید:\n"
            f"`شناسه_کاربر: متن پاسخ`\n\n"
            f"مثال: `123456789: سلام، پاسخ شما...`",
            parse_mode="Markdown"
        )
    else:
        await update.message.reply_text(
            "👋 سلام!\n"
            "به ربات پشتیبانی *کلاب مالی آرکاکوین* خوش آمدید ✨\n\n"
            "لطفا یکی از بخش‌های زیر را انتخاب کنید:",
            reply_markup=keyboard,
            parse_mode="Markdown"
        )

async def handle_section(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle section selection and start message collection"""
    context.user_data.clear()
    context.user_data["section"] = update.message.text
    context.user_data["messages"] = []

    await update.message.reply_text(
        "✉️ لطفا پیام خود را بفرستید.\n\n"
        "📤 وقتی تمام شد روی «ارسال پیام» بزنید.",
        reply_markup=action_keyboard
    )
    return GET_MESSAGE

async def handle_navigation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back and home buttons"""
    text = update.message.text
    
    if text == "🏠 خانه":
        context.user_data.clear()
        await update.message.reply_text(
            "🏠 به صفحه اصلی برگشتید.\nلطفا یکی از بخش‌های زیر را انتخاب کنید:",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    
    elif text == "↩️ بازگشت":
        await update.message.reply_text(
            "✉️ لطفا پیام خود را بفرستید:\n\n"
            "📤 وقتی تمام شد روی «ارسال پیام» بزنید.",
            reply_markup=action_keyboard
        )
        return GET_MESSAGE

async def get_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Collect user messages"""
    text = update.message.text or ""
    
    if text in ["🏠 خانه", "↩️ بازگشت"]:
        return await handle_navigation(update, context)
    
    if text == "📤 ارسال پیام":
        await send_to_primary_admins(update, context)
        context.user_data.clear()
        await update.message.reply_text(
            "✅ پیام شما ارسال شد.\nبرای ارسال پیام جدید یکی از بخش‌های زیر را انتخاب کنید:",
            reply_markup=keyboard
        )
        return ConversationHandler.END
    elif text == "🔚 اتمام مکالمه":
        return await handle_conversation_end(update, context)
    
    if update.message.text:
        context.user_data.setdefault("messages", []).append(("متن", update.message.text))
    elif update.message.photo:
        file_id = update.message.photo[-1].file_id
        caption = update.message.caption or ""
        context.user_data.setdefault("messages", []).append(("عکس", file_id, caption))
    elif update.message.voice:
        file_id = update.message.voice.file_id
        context.user_data.setdefault("messages", []).append(("صوت", file_id))
    elif update.message.document:
        file_id = update.message.document.file_id
        filename = update.message.document.file_name or "فایل"
        context.user_data.setdefault("messages", []).append(("فایل", file_id, filename))
    else:
        await update.message.reply_text(
            "❌ لطفا متن، عکس، ویس یا فایل بفرستید یا روی «📤 ارسال پیام» بزنید."
        )
        return GET_MESSAGE

    
    
    await update.message.reply_text(
        "✅ پیام دریافت شد! می‌تونید پیام‌های بیشتری بفرستید یا روی «📤 ارسال پیام» بزنید.",
        reply_markup=action_keyboard
    )
    return GET_MESSAGE

async def send_to_primary_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send user message to primary admins with delegation options"""
    if not PRIMARY_ADMINS:
        return
    
    user = update.message.from_user
    user_id = str(user.id)
    
    section = context.user_data.get("section", "نامشخص")
    messages = context.user_data.get("messages", [])
    date = datetime.now().strftime("%Y-%m-%d %H:%M")
    username = f"@{user.username}" if user.username else "بدون یوزرنیم"
    
    message_id = f"{user_id}_{int(datetime.now().timestamp())}"
    
    if "pending_messages" not in context.bot_data:
        context.bot_data["pending_messages"] = {}
    
    context.bot_data["pending_messages"][message_id] = {
        "user_id": user_id,
        "username": username,
        "section": section,
        "messages": messages,
        "date": date
    }
    
    header = (
        f"📩 *پیام جدید از کاربر*\n\n"
        f"📛 یوزرنیم: {username}\n"
        f"🆔 شناسه: `{user.id}`\n"
        f"🗓️ تاریخ: {date}\n"
        f"📂 بخش: {section}\n"
        f"📊 تعداد پیام‌ها: {len(messages)}\n\n"
    )
    
    delegation_keyboard = create_delegation_keyboard(message_id)
    
    for admin_id in PRIMARY_ADMINS:
        try:
            await context.bot.send_message(admin_id, header, parse_mode="Markdown")
            
            for i, m in enumerate(messages, 1):
                if m[0] == "متن":
                    await context.bot.send_message(admin_id, f"📝 *پیام {i}:*\n{m[1]}", parse_mode="Markdown")
                elif m[0] == "عکس":
                    cap = f"🖼️ *تصویر {i}*" + (f"\n📝 {m[2]}" if len(m) > 2 and m[2] else "")
                    await context.bot.send_photo(admin_id, m[1], caption=cap, parse_mode="Markdown")
                elif m[0] == "صوت":
                    await context.bot.send_voice(admin_id, m[1], caption=f"🎤 *پیام صوتی {i}*", parse_mode="Markdown")
                elif m[0] == "فایل":
                    filename = m[2] if len(m) > 2 else "فایل"
                    await context.bot.send_document(admin_id, m[1], caption=f"📄 *فایل {i}: {filename}*", parse_mode="Markdown")
            
            await context.bot.send_message(
                admin_id, 
                "👥 این پیام را به کدام ادمین ارجاع می‌دهید؟",
                reply_markup=delegation_keyboard
            )
            
        except TelegramError as e:
            logger.error(f"Error sending to primary admin {admin_id}: {e}")

async def handle_delegation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle delegation callback from primary admins"""
    query = update.callback_query
    user_id = str(query.from_user.id)
    
    if user_id not in PRIMARY_ADMINS:
        await query.answer("❌ شما مجاز به انجام این عملیات نیستید.")
        return
    
    await query.answer()
    
    try:
        _, target_admin_id, message_id = query.data.split("_", 2)
    except ValueError:
        await query.edit_message_text("❌ خطا در پردازش درخواست.")
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    if message_id not in pending_messages:
        await query.edit_message_text("❌ پیام مورد نظر یافت نشد.")
        return
    
    message_data = pending_messages[message_id]
    target_admin_name = get_admin_name(target_admin_id)
    delegating_admin_name = get_admin_name(user_id)
    
    message_data["delegated_to"] = target_admin_id
    message_data["delegated_by"] = user_id
    message_data["delegation_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    message_data["conversation_active"] = True 
    
    await query.edit_message_text(f"✅ پیام با موفقیت به {target_admin_name} ارجاع داده شد.")
    
    try:
        header = (
            f"📬 *پیام ارجاعی از {delegating_admin_name}*\n\n"
            f"📛 یوزرنیم کاربر: {message_data['username']}\n"
            f"🆔 شناسه کاربر: `{message_data['user_id']}`\n"
            f"🗓️ تاریخ پیام: {message_data['date']}\n"
            f"📂 بخش: {message_data['section']}\n"
            f"📊 تعداد پیام‌ها: {len(message_data['messages'])}\n"
            f"⏰ زمان ارجاع: {message_data['delegation_time']}\n\n"
            f"📝 *نحوه پاسخ:*\n"
            f"برای پاسخ، پیام خود را به این شکل بنویسید:\n"
            f"`{message_data['user_id']}: متن پاسخ`\n\n"
            f"💡 *نکته:* پس از پاسخ اول، می‌توانید مستقیماً با کاربر صحبت کنید.\n"
            f"برای پایان مکالمه از دستور `/endchat {message_data['user_id']}` استفاده کنید."
        )
        
        await context.bot.send_message(target_admin_id, header, parse_mode="Markdown")
        
        for i, m in enumerate(message_data['messages'], 1):
            if m[0] == "متن":
                await context.bot.send_message(target_admin_id, f"📝 *پیام {i}:*\n{m[1]}", parse_mode="Markdown")
            elif m[0] == "عکس":
                cap = f"🖼️ *تصویر {i}*" + (f"\n📝 {m[2]}" if len(m) > 2 and m[2] else "")
                await context.bot.send_photo(target_admin_id, m[1], caption=cap, parse_mode="Markdown")
            elif m[0] == "صوت":
                await context.bot.send_voice(target_admin_id, m[1], caption=f"🎤 *پیام صوتی {i}*", parse_mode="Markdown")
            elif m[0] == "فایل":
                filename = m[2] if len(m) > 2 else "فایل"
                await context.bot.send_document(target_admin_id, m[1], caption=f"📄 *فایل {i}: {filename}*", parse_mode="Markdown")
        
    except TelegramError as e:
        logger.error(f"Error sending to secondary admin {target_admin_id}: {e}")
        await context.bot.send_message(
            user_id, 
            f"❌ خطا در ارسال پیام به {target_admin_name}. لطفا دوباره تلاش کنید."
        )

async def handle_admin_direct_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct replies from secondary admins in format: user_id: message"""
    user_id = str(update.message.from_user.id)
    text = update.message.text or ""

    if user_id not in SECONDARY_ADMINS:
        return

    if ":" not in text:
        return await handle_direct_admin_message(update, context)
    
    try:
        target_user_id, reply_content = text.split(":", 1)
        target_user_id = target_user_id.strip()
        reply_content = reply_content.strip()
        
        if not target_user_id or not reply_content:
            await update.message.reply_text(
                "❌ فرمت پیام اشتباه است.\n"
                "لطفا به این شکل بنویسید: `شناسه_کاربر: متن پاسخ`",
                parse_mode="Markdown"
            )
            return
        
    except ValueError:
        return await handle_direct_admin_message(update, context)
    
    pending_messages = context.bot_data.get("pending_messages", {})
    user_message_data = None
    message_id = None
    
    for mid, data in pending_messages.items():
        if data["user_id"] == target_user_id and not data.get("completed"):
            user_message_data = data
            message_id = mid
            break
    
    if not user_message_data:
        await update.message.reply_text(
            f"❌ هیچ پیام فعالی برای کاربر `{target_user_id}` یافت نشد.",
            parse_mode="Markdown"
        )
        return
    
    try:
        await context.bot.send_message(
            target_user_id,
            f"💬 *پاسخ تیم پشتیبانی کلاب مالی آرکاکوین*\n\n"
            f"📂 بخش: {user_message_data['section']}\n",
            parse_mode="Markdown"
        )
        
        await context.bot.send_message(target_user_id, reply_content)
        
        user_message_data["conversation_active"] = True
        user_message_data["admin_reply"] = reply_content
        user_message_data["first_reply_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
        
        admin_name = get_admin_name(user_id)
        await update.message.reply_text(
            f"✅ پاسخ ارسال شد و مکالمه با کاربر `{target_user_id}` فعال شد.\n"
            f"اکنون می‌توانید مستقیماً پیام بفرستید.\n"
            f"برای پایان مکالمه از /endchat استفاده کنید.",
            parse_mode="Markdown"
        )
        
    except TelegramError as e:
        logger.error(f"Error sending reply to user {target_user_id}: {e}")
        await update.message.reply_text(
            f"❌ خطا در ارسال پاسخ به کاربر `{target_user_id}`.",
            parse_mode="Markdown"
        )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel current conversation"""
    context.user_data.clear()
    await update.message.reply_text(
        "🚪 گفتگو لغو شد. برای شروع مجدد یکی از بخش‌ها را انتخاب کنید:",
        reply_markup=keyboard
    )
    return ConversationHandler.END

async def list_pending_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List pending messages (Primary admins only)"""
    user_id = str(update.message.from_user.id)
    if user_id not in PRIMARY_ADMINS:
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    if not pending_messages:
        await update.message.reply_text("📭 هیچ پیام در انتظاری وجود ندارد.")
        return
    
    msg = "📋 *پیام‌های در انتظار:*\n\n"
    for msg_id, data in pending_messages.items():
        status = "✅ تکمیل شده" if data.get("completed") else "⏳ در انتظار"
        delegated_to = get_admin_name(data.get("delegated_to", "")) if data.get("delegated_to") else "ارجاع نشده"
        
        msg += (
            f"🆔 `{data['user_id']}`\n"
            f"👤 {data['username']}\n"
            f"📂 {data['section']}\n"
            f"👥 ارجاع به: {delegated_to}\n"
            f"📊 وضعیت: {status}\n"
            f"🗓️ {data['date']}\n\n"
        )
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def list_my_tasks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List tasks assigned to secondary admin"""
    user_id = str(update.message.from_user.id)
    if user_id not in SECONDARY_ADMINS:
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    my_tasks = [data for data in pending_messages.values() 
                if data.get("delegated_to") == user_id and not data.get("completed")]
    
    if not my_tasks:
        await update.message.reply_text("📭 شما هیچ تسک در انتظاری ندارید.")
        return
    
    admin_name = get_admin_name(user_id)
    my_messages = [data for data in pending_messages.values() 
                if data.get("delegated_to") == user_id]
    total = len(my_messages)
    completed = len([m for m in my_messages if m.get("completed")])

    msg = (
        f"📋 *تسک‌های {admin_name}*\n\n"
        f"📊 آمار: {len(my_tasks)} فعال از {total} کل ({completed} تکمیل شده)\n\n"
    )
    
    for data in my_tasks:
        msg += (
            f"🆔 شناسه کاربر: `{data['user_id']}`\n"
            f"👤 {data['username']}\n"
            f"📂 {data['section']}\n"
            f"🗓️ {data['date']}\n"
            f"⏰ ارجاع: {data.get('delegation_time', 'نامشخص')}\n\n"
            f"📝 *برای پاسخ:*\n"
            f"`{data['user_id']}: متن پاسخ شما`\n\n"
            f"{'─' * 30}\n\n"
        )
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def handle_conversation_end(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle conversation end for secondary admins"""
    user_id = str(update.message.from_user.id)
    
    if user_id not in SECONDARY_ADMINS:
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    active_conversation = None
    message_id = None
    
    for mid, data in pending_messages.items():
        if (data.get("delegated_to") == user_id and 
            not data.get("completed") and 
            data.get("conversation_active")):
            active_conversation = data
            message_id = mid
            break
    
    if not active_conversation:
        await update.message.reply_text("❌ هیچ مکالمه فعالی برای اتمام یافت نشد.")
        return
    
    active_conversation["completed"] = True
    active_conversation["completed_by"] = user_id
    active_conversation["completion_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    active_conversation["conversation_active"] = False
    active_conversation["end_reason"] = "admin_ended"
    
    admin_name = get_admin_name(user_id)
    target_user_id = active_conversation["user_id"]
    
    try:
        await context.bot.send_message(
            target_user_id,
            f"✅ مکالمه شما با تیم پشتیبانی به پایان رسید.\n\n"
            f"اگر سوال جدیدی دارید، خوشحال می‌شویم مجدداً کمکتان کنیم!\n\n"
            f"برای ارسال پیام جدید یکی از بخش‌ها را انتخاب کنید:",
            reply_markup=keyboard
        )
    except TelegramError as e:
        logger.error(f"Error notifying user about conversation end: {e}")
    
    completion_message = (
        f"🔚 *مکالمه به پایان رسید*\n\n"
        f"👤 پایان‌دهنده: {admin_name}\n"
        f"📛 یوزرنیم کاربر: {active_conversation['username']}\n"
        f"🆔 شناسه کاربر: `{active_conversation['user_id']}`\n"
        f"📂 بخش: {active_conversation['section']}\n"
        f"⏰ زمان پایان: {active_conversation['completion_time']}\n"
    )
    
    for admin_id in PRIMARY_ADMINS:
        try:
            await context.bot.send_message(admin_id, completion_message, parse_mode="Markdown")
        except TelegramError as e:
            logger.error(f"Error notifying primary admin {admin_id}: {e}")
    
    await update.message.reply_text(f"✅ مکالمه با کاربر `{target_user_id}` به پایان رسید.")

async def handle_direct_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle direct messages from secondary admins to active conversations"""
    user_id = str(update.message.from_user.id)
    
    if user_id not in SECONDARY_ADMINS:
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    active_conversation = None
    
    for data in pending_messages.values():
        if (data.get("delegated_to") == user_id and 
            not data.get("completed") and 
            data.get("conversation_active")):
            active_conversation = data
            break
    
    if not active_conversation:
        return  
    
    target_user_id = active_conversation["user_id"]
    
    try:
        if update.message.text:
            await context.bot.send_message(target_user_id, reply_content) 
        elif update.message.photo:
            await context.bot.send_photo(
                target_user_id, 
                update.message.photo[-1].file_id,
                caption=update.message.caption
            )
        elif update.message.voice:
            await context.bot.send_voice(target_user_id, update.message.voice.file_id)
        elif update.message.document:
            await context.bot.send_document(
                target_user_id, 
                update.message.document.file_id,
                caption=update.message.caption
            )
        
        await update.message.reply_text("✅ پیام ارسال شد.")
        
    except TelegramError as e:
        logger.error(f"Error sending direct message to user {target_user_id}: {e}")
        await update.message.reply_text("❌ خطا در ارسال پیام.")

async def handle_user_active_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle messages from users who have active conversations"""
    user_id = str(update.message.from_user.id)
    
    pending_messages = context.bot_data.get("pending_messages", {})
    active_conversation = None
    assigned_admin = None
    
    for data in pending_messages.values():
        if (data["user_id"] == user_id and 
            not data.get("completed") and 
            data.get("conversation_active")):
            active_conversation = data
            assigned_admin = data.get("delegated_to")
            break
    
    if not active_conversation or not assigned_admin:
        return False  
    
    try:
        admin_name = get_admin_name(assigned_admin)
        username = f"@{update.message.from_user.username}" if update.message.from_user.username else "بدون یوزرنیم"
        
        header = f"💬 *پیام جدید از {username}* (شناسه: `{user_id}`)\n\n"
        await context.bot.send_message(assigned_admin, header, parse_mode="Markdown")
        
        if update.message.text:
            await context.bot.send_message(assigned_admin, update.message.text)
        elif update.message.photo:
            await context.bot.send_photo(
                assigned_admin, 
                update.message.photo[-1].file_id,
                caption=update.message.caption
            )
        elif update.message.voice:
            await context.bot.send_voice(assigned_admin, update.message.voice.file_id)
        elif update.message.document:
            await context.bot.send_document(
                assigned_admin, 
                update.message.document.file_id,
                caption=update.message.caption
            )
        
        await update.message.reply_text("✅ پیام شما به پشتیبان ارسال شد.")
        return True 
        
    except TelegramError as e:
        logger.error(f"Error forwarding to admin {assigned_admin}: {e}")
        return False

async def end_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """End conversation with specific user ID"""
    user_id = str(update.message.from_user.id)
    
    if user_id not in SECONDARY_ADMINS:
        await update.message.reply_text("❌ شما مجاز به استفاده از این دستور نیستید.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 *نحوه استفاده:*\n"
            "`/endchat شناسه_کاربر`\n\n"
            "*مثال:*\n"
            "`/endchat 123456789`",
            parse_mode="Markdown"
        )
        return
    
    target_user_id = context.args[0].strip()
    
    pending_messages = context.bot_data.get("pending_messages", {})
    active_conversation = None
    message_id = None
    
    for mid, data in pending_messages.items():
        if (data["user_id"] == target_user_id and 
            data.get("delegated_to") == user_id and
            not data.get("completed") and 
            data.get("conversation_active")):
            active_conversation = data
            message_id = mid
            break
    
    if not active_conversation:
        await update.message.reply_text(
            f"❌ هیچ مکالمه فعالی با کاربر `{target_user_id}` یافت نشد.",
            parse_mode="Markdown"
        )
        return

    
    active_conversation["completed"] = True
    active_conversation["completed_by"] = user_id
    active_conversation["completion_time"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    active_conversation["conversation_active"] = False
    active_conversation["end_reason"] = "admin_ended"
    
    admin_name = get_admin_name(user_id)
    target_user_id = active_conversation["user_id"]
    
    try:
        await context.bot.send_message(
            target_user_id,
            "✅ مکالمه شما با تیم پشتیبانی به پایان رسید.\n\n"
            "اگر سوال جدیدی دارید، خوشحال می‌شویم مجدداً کمکتان کنیم!\n\n"
            "برای ارسال پیام جدید یکی از بخش‌ها را انتخاب کنید:",
            reply_markup=keyboard
        )
    except TelegramError as e:
        logger.error(f"Error notifying user about conversation end: {e}")
    
    completion_message = (
        f"🔚 *مکالمه به پایان رسید*\n\n"
        f"👤 پایان‌دهنده: {admin_name}\n"
        f"📛 یوزرنیم کاربر: {active_conversation['username']}\n"
        f"🆔 شناسه کاربر: `{active_conversation['user_id']}`\n"
        f"📂 بخش: {active_conversation['section']}\n"
        f"⏰ زمان پایان: {active_conversation['completion_time']}\n"
    )
    
    for admin_id in PRIMARY_ADMINS:
        try:
            await context.bot.send_message(admin_id, completion_message, parse_mode="Markdown")
        except TelegramError as e:
            logger.error(f"Error notifying primary admin {admin_id}: {e}")
    
    await update.message.reply_text(f"✅ مکالمه با کاربر `{target_user_id}` به پایان رسید.", parse_mode="Markdown")

async def full_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show detailed status for admins"""
    user_id = str(update.message.from_user.id)
    
    if user_id not in PRIMARY_ADMINS and user_id not in SECONDARY_ADMINS:
        await update.message.reply_text("❌ شما مجاز به مشاهده این اطلاعات نیستید.")
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    
    if not pending_messages:
        await update.message.reply_text("📭 هیچ پیامی در سیستم وجود ندارد.")
        return
    
    total_messages = len(pending_messages)
    answered_messages = [m for m in pending_messages.values() if m.get("admin_reply")]
    unanswered_messages = [m for m in pending_messages.values() if not m.get("admin_reply")]
    open_conversations = [m for m in pending_messages.values() if m.get("conversation_active")]
    closed_conversations = [m for m in pending_messages.values() if m.get("completed")]
    
    status_msg = (
        f"📊 *گزارش کامل سیستم*\n\n"
        f"📩 کل سوالات: {total_messages}\n"
        f"✅ پاسخ داده شده: {len(answered_messages)}\n"
        f"❌ پاسخ داده نشده: {len(unanswered_messages)}\n"
        f"🔓 مکالمات باز: {len(open_conversations)}\n"
        f"🔒 مکالمات بسته: {len(closed_conversations)}\n\n"
    )
    
    admin_stats = {}
    for data in pending_messages.values():
        if data.get("delegated_to"):
            admin_id = data["delegated_to"]
            admin_name = get_admin_name(admin_id)
            if admin_name not in admin_stats:
                admin_stats[admin_name] = {
                    "total": 0, 
                    "completed": 0, 
                    "active": 0,
                    "answered": 0
                }
            admin_stats[admin_name]["total"] += 1
            if data.get("completed"):
                admin_stats[admin_name]["completed"] += 1
            if data.get("conversation_active"):
                admin_stats[admin_name]["active"] += 1
            if data.get("admin_reply"):
                admin_stats[admin_name]["answered"] += 1
    
    if admin_stats:
        status_msg += "👥 *آمار ادمین‌ها:*\n"
        for admin_name, stats in admin_stats.items():
            admin_id = None
            for aid, name in ADMIN_NAMES.items():
                if name == admin_name:
                    admin_id = aid
                    break
        
            pending_admin = stats["total"] - stats["completed"]
            admin_display = f"{admin_name} (`{admin_id}`)" if admin_id else admin_name
        
        status_msg += (
            f"👤 {admin_display}:\n"
            f"   📊 کل: {stats['total']}\n"
            f"   ✅ تکمیل: {stats['completed']}\n"
            f"   🔓 فعال: {stats['active']}\n"
            f"   💬 پاسخ‌داده: {stats['answered']}\n"
            f"   ⏳ معلق: {pending_admin}\n\n"
        )
    
    await update.message.reply_text(status_msg, parse_mode="Markdown")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show bot statistics (Primary admins only)"""
    user_id = str(update.message.from_user.id)
    if user_id not in PRIMARY_ADMINS:
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    total_messages = len(pending_messages)
    completed_messages = len([m for m in pending_messages.values() if m.get("completed")])
    pending_count = total_messages - completed_messages
    
    admin_stats = {}
    for data in pending_messages.values():
        if data.get("delegated_to"):
            admin_id = data["delegated_to"]
            admin_name = get_admin_name(admin_id)
            if admin_name not in admin_stats:
                admin_stats[admin_name] = {"total": 0, "completed": 0}
            admin_stats[admin_name]["total"] += 1
            if data.get("completed"):
                admin_stats[admin_name]["completed"] += 1
    
    msg = (
        f"📊 *آمار ربات*\n\n"
        f"📩 کل پیام‌ها: {total_messages}\n"
        f"✅ تکمیل شده: {completed_messages}\n"
        f"⏳ در انتظار: {pending_count}\n\n"
    )
    
    if admin_stats:
        msg += "*📊 آمار ادمین‌ها:*\n"
        for admin_name, stats in admin_stats.items():
            pending_admin = stats["total"] - stats["completed"]
            msg += f"👤 {admin_name}: {stats['completed']}/{stats['total']} (در انتظار: {pending_admin})\n"
    
    await update.message.reply_text(msg, parse_mode="Markdown")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show help for admins"""
    user_id = str(update.message.from_user.id)
    
    if user_id == SUPER_ADMIN:
        help_msg = (
            "🚀 *راهنمای مدیر کل سیستم*\n\n"
            "🔧 *دستورات اختصاصی:*\n"
            "`/help` - نمایش این راهنما\n"
            "`/broadcast متن` - ارسال پیام به همه ادمین‌ها\n"
            "`/admins` - لیست تمام ادمین‌ها\n"
            "`/fullstatus` - گزارش کامل سیستم\n"
            "`/adminstatus شناسه` - وضعیت ادمین مشخص\n"
            "`/pending` - لیست پیام‌های در انتظار\n"
            "`/stats` - آمار کلی ربات\n\n"
            "💡 *مثال‌ها:*\n"
            "`/broadcast اطلاعیه مهم برای همه`\n"
            "`/adminstatus 393746429`"
        )
        
    elif user_id in PRIMARY_ADMINS:
        help_msg = (
            "👑 *راهنمای ادمین اصلی*\n\n"
            "🔧 *دستورات موجود:*\n"
            "`/help` - نمایش این راهنما\n"
            "`/fullstatus` - گزارش کامل سیستم\n"
            "`/pending` - لیست پیام‌های در انتظار\n"
            "`/stats` - آمار کلی ربات\n"
            "`/adminstatus شناسه` - وضعیت ادمین مشخص\n\n"
            "⚡ *قابلیت‌ها:*\n"
            "• دریافت تمامی پیام‌های کاربران\n"
            "• ارجاع پیام‌ها به ادمین‌های سطح دو\n"
            "• مشاهده آمار کامل سیستم\n"
            "• نظارت بر عملکرد ادمین‌ها\n\n"
            "📋 *نحوه کار:*\n"
            "1️⃣ پیام کاربر دریافت می‌شود\n"
            "2️⃣ روی دکمه ادمین مورد نظر کلیک کنید\n"
            "3️⃣ پیام به ادمین سطح دو ارجاع می‌شود\n"
            "4️⃣ گزارش تکمیل دریافت می‌کنید\n\n"
            "💡 *مثال:*\n"
            "`/adminstatus 393746429` - وضعیت محمد"
        )
        
    elif user_id in SECONDARY_ADMINS:
        admin_name = get_admin_name(user_id)
        help_msg = (
            f"🔧 *راهنمای {admin_name}*\n\n"
            "🔧 *دستورات موجود:*\n"
            "`/help` - نمایش این راهنما\n"
            "`/mytask` - تسک‌های اختصاص داده شده\n"
            "`/mystatus` - وضعیت و آمار شخصی من\n"
            "`/fullstatus` - گزارش کامل سیستم\n"
            "`/endchat شناسه_کاربر` - پایان مکالمه با کاربر مشخص\n\n"
            "⚡ *قابلیت‌ها:*\n"
            "• دریافت پیام‌های ارجاعی\n"
            "• پاسخ‌گویی به کاربران\n"
            "• مکالمه مستقیم با کاربران\n"
            "• پایان دادن به مکالمات\n\n"
            "📋 *نحوه پاسخ‌گویی:*\n"
            "🔸 **اولین پاسخ:** `شناسه_کاربر: متن پاسخ`\n"
            "   مثال: `123456789: سلام، پاسخ شما...`\n\n"
            "🔸 **پاسخ‌های بعدی:** مستقیماً بنویسید\n"
            "   (نیازی به فرمت خاص نیست)\n\n"
            "🔸 **پایان مکالمه:** `/endchat شناسه_کاربر`\n"
            "   مثال: `/endchat 123456789`\n\n"
            "💡 *نکته:* پس از اولین پاسخ، مکالمه فعال می‌شود و می‌توانید\n"
            "مستقیماً با کاربر صحبت کنید بدون نیاز به فرمت خاص."
        )
        
    else:
        help_msg = (
            "ℹ️ این ربات مخصوص تیم پشتیبانی کلاب مالی آرکاکوین است.\n\n"
            "برای استفاده از خدمات، یکی از بخش‌های زیر را انتخاب کنید:"
        )
        
        await update.message.reply_text(help_msg, reply_markup=keyboard)
        return
    
    await update.message.reply_text(help_msg, parse_mode="Markdown")

async def admin_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show specific admin status by ID (Primary admins only)"""
    user_id = str(update.message.from_user.id)
    
    if user_id not in PRIMARY_ADMINS:
        await update.message.reply_text("❌ شما مجاز به استفاده از این دستور نیستید.")
        return
    
    if not context.args:
        await update.message.reply_text(
            "📝 *نحوه استفاده:*\n"
            "`/adminstatus شناسه_ادمین`\n\n"
            "*ادمین‌های موجود:*\n" + 
            "\n".join([f"• `{aid}` - {name}" for aid, name in ADMIN_NAMES.items()]),
            parse_mode="Markdown"
        )
        return
    
    target_admin_id = context.args[0].strip()
    
    if target_admin_id not in SECONDARY_ADMINS:
        await update.message.reply_text(f"❌ ادمین با شناسه `{target_admin_id}` یافت نشد.")
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    admin_messages = [data for data in pending_messages.values() 
                     if data.get("delegated_to") == target_admin_id]
    
    if not admin_messages:
        admin_name = get_admin_name(target_admin_id)
        await update.message.reply_text(f"📭 {admin_name} هیچ تسکی ندارد.")
        return
    
    total = len(admin_messages)
    completed = len([m for m in admin_messages if m.get("completed")])
    active = len([m for m in admin_messages if m.get("conversation_active")])
    answered = len([m for m in admin_messages if m.get("admin_reply")])
    pending = total - completed
    
    admin_name = get_admin_name(target_admin_id)
    
    status_msg = (
        f"👤 *وضعیت {admin_name}* (`{target_admin_id}`)\n\n"
        f"📊 کل تسک‌ها: {total}\n"
        f"✅ تکمیل شده: {completed}\n"
        f"🔓 مکالمات فعال: {active}\n"
        f"💬 پاسخ داده شده: {answered}\n"
        f"⏳ در انتظار: {pending}\n\n"
    )
    
    active_tasks = [m for m in admin_messages if not m.get("completed")]
    if active_tasks:
        status_msg += "📋 *تسک‌های فعال:*\n"
        for task in active_tasks[:5]:  
            status = "🔓 فعال" if task.get("conversation_active") else "⏳ معلق"
            status_msg += (
                f"• کاربر `{task['user_id']}` - {task['section']}\n"
                f"  📅 {task['date']} - {status}\n"
            )
        if len(active_tasks) > 5:
            status_msg += f"... و {len(active_tasks) - 5} تسک دیگر\n"
    
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def broadcast_to_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Send message to all admins (Super admin only)"""
    user_id = str(update.message.from_user.id)
    
    if user_id != SUPER_ADMIN:
        return  
    
    if not context.args:
        await update.message.reply_text(
            "📢 *نحوه ارسال پیام به همه ادمین‌ها:*\n"
            "`/broadcast متن پیام شما`\n\n"
            "*مثال:*\n"
            "`/broadcast سلام به همه ادمین‌ها`",
            parse_mode="Markdown"
        )
        return
    
    message_text = " ".join(context.args)
    sender_name = "مدیر کل سیستم"
    
    all_admins = set(PRIMARY_ADMINS + SECONDARY_ADMINS)
    
    sent_count = 0
    failed_count = 0
    
    broadcast_message = (
        f"📢 *پیام از {sender_name}*\n"
        f"🕐 {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"{message_text}"
    )
    
    for admin_id in all_admins:
        try:
            await context.bot.send_message(admin_id, broadcast_message, parse_mode="Markdown")
            sent_count += 1
        except TelegramError as e:
            logger.error(f"Error sending broadcast to admin {admin_id}: {e}")
            failed_count += 1
    
    result_msg = (
        f"📊 *گزارش ارسال پیام عمومی*\n\n"
        f"✅ ارسال موفق: {sent_count}\n"
        f"❌ ارسال ناموفق: {failed_count}\n"
        f"📊 کل ادمین‌ها: {len(all_admins)}"
    )
    
    await update.message.reply_text(result_msg, parse_mode="Markdown")

async def list_all_admins(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all admins (Super admin only)"""
    user_id = str(update.message.from_user.id)
    
    if user_id != SUPER_ADMIN:
        return
    
    all_admins = set(PRIMARY_ADMINS + SECONDARY_ADMINS)
    
    admin_list = "👥 *لیست تمامی ادمین‌ها:*\n\n"
    
    if PRIMARY_ADMINS:
        admin_list += "👑 *ادمین‌های اصلی:*\n"
        for admin_id in PRIMARY_ADMINS:
            admin_name = get_admin_name(admin_id)
            admin_list += f"• `{admin_id}` - {admin_name}\n"
        admin_list += "\n"
    
    if SECONDARY_ADMINS:
        admin_list += "🔧 *ادمین‌های سطح دو:*\n"
        for admin_id in SECONDARY_ADMINS:
            admin_name = get_admin_name(admin_id)
            admin_list += f"• `{admin_id}` - {admin_name}\n"
    
    admin_list += f"\n📊 کل ادمین‌ها: {len(all_admins)}"
    
    await update.message.reply_text(admin_list, parse_mode="Markdown")

async def my_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show personal status for secondary admins"""
    user_id = str(update.message.from_user.id)
    
    if user_id not in SECONDARY_ADMINS:
        await update.message.reply_text("❌ این دستور فقط برای ادمین‌های سطح دو است.")
        return
    
    pending_messages = context.bot_data.get("pending_messages", {})
    my_messages = [data for data in pending_messages.values() 
                   if data.get("delegated_to") == user_id]
    
    if not my_messages:
        admin_name = get_admin_name(user_id)
        await update.message.reply_text(f"📭 {admin_name} عزیز، شما هیچ تسکی ندارید.")
        return
    
    total = len(my_messages)
    completed = len([m for m in my_messages if m.get("completed")])
    active = len([m for m in my_messages if m.get("conversation_active")])
    answered = len([m for m in my_messages if m.get("admin_reply")])
    pending = total - completed
    
    admin_name = get_admin_name(user_id)
    
    status_msg = (
        f"👤 *وضعیت شخصی {admin_name}*\n\n"
        f"📊 کل تسک‌ها: {total}\n"
        f"✅ تکمیل شده: {completed}\n"
        f"🔓 مکالمات فعال: {active}\n"
        f"💬 پاسخ داده شده: {answered}\n"
        f"⏳ در انتظار: {pending}\n\n"
    )
    
    active_tasks = [m for m in my_messages if not m.get("completed")]
    if active_tasks:
        status_msg += "📋 *تسک‌های فعال شما:*\n"
        for i, task in enumerate(active_tasks[:3], 1): 
            status = "🔓 مکالمه فعال" if task.get("conversation_active") else "⏳ معلق"
            status_msg += (
                f"{i}. کاربر `{task['user_id']}`\n"
                f"   📂 {task['section']}\n"
                f"   📅 {task['date']}\n"
                f"   📊 {status}\n\n"
            )
        
        if len(active_tasks) > 3:
            status_msg += f"... و {len(active_tasks) - 3} تسک دیگر\n\n"
    
    if active:
        status_msg += "💡 *نکته:* برای مشاهده همه تسک‌ها از `/mytask` استفاده کنید."
    else:
        status_msg += "🎉 *عالی!* فعلاً مکالمه فعالی ندارید."
    
    await update.message.reply_text(status_msg, parse_mode="Markdown")

async def check_active_conversation_first(update, context):
    if await handle_user_active_conversation(update, context):
        return 
    return 

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    all_admins = SECONDARY_ADMINS + PRIMARY_ADMINS
    if SUPER_ADMIN:
        all_admins.append(SUPER_ADMIN)

    all_admin_ids = [int(aid) for aid in all_admins if aid.isdigit()]

    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & ~filters.User(user_id=all_admin_ids),
        lambda update, context: handle_user_active_conversation(update, context)
    ), group=0)

    secondary_admin_ids = [int(aid) for aid in SECONDARY_ADMINS if aid.isdigit()]

    app.add_handler(MessageHandler(
        filters.User(user_id=secondary_admin_ids) & 
        filters.TEXT & 
        filters.Regex(r"^\d+:"),
        handle_admin_direct_reply
    ), group=2)

    app.add_handler(MessageHandler(
        filters.User(user_id=secondary_admin_ids) & 
        filters.ALL & ~filters.COMMAND,
        handle_direct_admin_message
    ), group=3)

    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^(📊 فارکس|💎 کریپتو|🏦 طلا/ارز|📈 آپشن|📚 آموزشی)$"), handle_section)],
        states={
            GET_MESSAGE: [MessageHandler(filters.ALL & ~filters.COMMAND, get_message)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
        allow_reentry=True
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CallbackQueryHandler(handle_delegation, pattern="^delegate_"))
    
    app.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & ~filters.User(user_id=[int(aid) for aid in SECONDARY_ADMINS if aid.isdigit()]),
        lambda update, context: handle_user_active_conversation(update, context)
    ), group=0)
    
    app.add_handler(conv, group=1)
    
    app.add_handler(MessageHandler(
        filters.User(user_id=[int(aid) for aid in SECONDARY_ADMINS if aid.isdigit()]) & 
        filters.TEXT & 
        filters.Regex(r"^\d+:"),
        handle_admin_direct_reply
    ), group=2)
    
    app.add_handler(MessageHandler(
        filters.User(user_id=[int(aid) for aid in SECONDARY_ADMINS if aid.isdigit()]) & 
        filters.ALL & ~filters.COMMAND,
        handle_direct_admin_message
    ), group=3)
    
    app.add_handler(CommandHandler("endchat", end_chat_command))
    app.add_handler(CommandHandler("fullstatus", full_status))
    app.add_handler(CommandHandler("pending", list_pending_messages))
    app.add_handler(CommandHandler("mytask", list_my_tasks))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CommandHandler("adminstatus", admin_status_command))
    app.add_handler(CommandHandler("broadcast", broadcast_to_admins))
    app.add_handler(CommandHandler("admins", list_all_admins))
    app.add_handler(CommandHandler("mystatus", my_status_command))


    
    logger.info("Bot is starting…")
    print("🤖 Bot is running…")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
