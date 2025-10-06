import os
# import sqlite3
import logging
from datetime import datetime
import jdatetime
import requests
from bs4 import BeautifulSoup
# from dotenv import load_dotenv
from telegram import ReplyKeyboardMarkup, Update, ReplyKeyboardRemove
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
import psycopg2

# --- تنظیمات اولیه ---
# بارگذاری متغیرهای محیطی از فایل .env
# load_dotenv()

# خواندن متغیرها
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
BASE_URL = os.getenv("BASE_URL", "https://www.tgju.org/profile/")

# پیکربندی لاگ‌ها برای دیباگ بهتر
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- مدیریت دیتابیس ---
def get_connection():
    return psycopg2.connect(
        host=os.getenv("DB_HOST"),
        port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"),
        user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD")
    )

def setup_database():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id SERIAL PRIMARY KEY,
        telegram_id BIGINT UNIQUE NOT NULL,
        first_name TEXT NOT NULL,
        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    conn.commit()
    conn.close()

def add_user(user: dict):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (telegram_id, first_name) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING",
        (user['id'], user['first_name'])
    )
    conn.commit()
    conn.close()

def get_all_users():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, first_name FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    conn.close()
    return users        

# --- توابع اسکریپینگ (Scraping) ---
def get_jalali_datetime():
    """تاریخ و زمان شمسی فعلی را برمی‌گرداند."""
    now = datetime.now()
    jalali_date = jdatetime.datetime.fromgregorian(datetime=now).strftime("%A %d %B %Y")
    time_str = now.strftime("ساعت %H:%M")
    return f"🗓️ {jalali_date}\n🕰️ {time_str}\n\n"

def scrape_price(profile_id: str) -> str:
    """قیمت را از یک پروفایل خاص در TGJU استخراج می‌کند."""
    try:
        url = f"{BASE_URL}{profile_id}"
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, 'html.parser')
        price_tag = soup.find("span", {"data-col": "info-price"})
        return price_tag.text.strip() if price_tag else "یافت نشد"
    except requests.RequestException as e:
        logger.error(f"Error scraping {profile_id}: {e}")
        return "خطا در اتصال"

def get_gold_prices():
    """قیمت طلا ۱۸ و ۲۴ عیار را برمی‌گرداند."""
    geram18 = scrape_price("geram18")
    geram24 = scrape_price("geram24")
    message = "--- **قیمت طلا** ---\n"
    message += f"طلای ۱۸ عیار: {geram18} تومان\n"
    message += f"طلای ۲۴ عیار: {geram24} تومان"
    return message

def get_coin_prices():
    """قیمت انواع سکه را برمی‌گرداند."""
    emami = scrape_price("sekee")
    azadi = scrape_price("seke-azadi")
    nim = scrape_price("seke-nim")
    rob = scrape_price("seke-rob")
    
    emami86 = scrape_price("seke-emami-86")
    nim86 = scrape_price("seke-nim-86")
    rob86 = scrape_price("seke-rob-86")
    
    message = "--- **قیمت سکه** ---\n"
    message += f"سکه امامی: {emami} تومان\n"
    message += f"سکه آزادی: {azadi} تومان\n"
    message += f"نیم سکه: {nim} تومان\n"
    message += f"ربع سکه: {rob} تومان\n\n"
    message += "--- **سکه طرح قدیم (۱۳۸۶)** ---\n"
    message += f"سکه امامی (۸۶): {emami86} تومان\n"
    message += f"نیم سکه (۸۶): {nim86} تومان\n"
    message += f"ربع سکه (۸۶): {rob86} تومان"
    return message
    
def get_currency_prices():
    """قیمت دلار و یورو را برمی‌گرداند."""
    usd = scrape_price("price_dollar_rl")
    eur = scrape_price("price_eur")
    message = "--- **قیمت ارز (بازار آزاد)** ---\n"
    message += f"دلار آمریکا: {usd} تومان\n"
    message += f"یورو: {eur} تومان"
    return message

def get_tether_price():
    """قیمت تتر را برمی‌گرداند."""
    tether = scrape_price("tether")
    message = "--- **قیمت تتر** ---\n"
    message += f"تتر (USDT): {tether} تومان"
    return message
    
def get_parsian_prices():
    """قیمت سکه‌های پارسیان و گرمی را برمی‌گرداند."""
    parsian_weights = ["100", "150", "200", "250", "300", "400", "500", "1g", "1.5g", "2g"]
    parsian_labels = {
        "100": "۱۰۰ سوت", "150": "۱۵۰ سوت", "200": "۲۰۰ سوت", "250": "۲۵۰ سوت",
        "300": "۳۰۰ سوت", "400": "۴۰۰ سوت", "500": "۵۰۰ سوت",
        "1g": "۱ گرم", "1.5g": "۱.۵ گرم", "2g": "۲ گرم"
    }
    
    message = "--- **قیمت سکه پارسیان** ---\n"
    for weight in parsian_weights:
        price = scrape_price(f"parsian-{weight}")
        label = parsian_labels.get(weight, weight)
        message += f"پارسیان {label}: {price} تومان\n"
        
    gerami_price = scrape_price("seke-gerami")
    message += f"\nسکه گرمی: {gerami_price} تومان"
    return message

# --- توابع ربات تلگرام (Handlers) ---
def start(update: Update, context: CallbackContext):
    """دستور /start را مدیریت می‌کند."""
    user = update.effective_user
    add_user(user)
    
    keyboard = [
        ['طلا 🥇', 'سکه 🪙'],
        ['ارز 💵', 'تتر ₮'],
        ['سکه پارسیان ⚖️']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    update.message.reply_text(
        f"سلام {user.first_name}!\n"
        "برای دریافت قیمت لحظه‌ای، یکی از گزینه‌های زیر را انتخاب کنید:",
        reply_markup=reply_markup
    )

def handle_message(update: Update, context: CallbackContext):
    """پیام‌های ورودی و دکمه‌های کیبورد را مدیریت می‌کند."""
    user_choice = update.message.text
    chat_id = update.message.chat_id
    
    # نمایش پیام "در حال دریافت اطلاعات"
    loading_message = context.bot.send_message(chat_id=chat_id, text="لطفا صبر کنید، در حال دریافت اطلاعات...")
    
    response_text = ""
    if user_choice == 'طلا 🥇':
        response_text = get_gold_prices()
    elif user_choice == 'سکه 🪙':
        response_text = get_coin_prices()
    elif user_choice == 'ارز 💵':
        response_text = get_currency_prices()
    elif user_choice == 'تتر ₮':
        response_text = get_tether_price()
    elif user_choice == 'سکه پارسیان ⚖️':
        response_text = get_parsian_prices()
    else:
        response_text = "لطفاً یکی از گزینه‌های روی کیبورد را انتخاب کنید."
        context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        update.message.reply_text(response_text)
        return

    full_message = get_jalali_datetime() + response_text
    
    # حذف پیام لودینگ و ارسال نتیجه
    context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
    update.message.reply_text(full_message)

def list_users(update: Update, context: CallbackContext):
    """دستور /users را برای ادمین مدیریت می‌کند."""
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("شما اجازه‌ی دسترسی به این دستور را ندارید.")
        return
    
    users = get_all_users()
    if not users:
        update.message.reply_text("هنوز هیچ کاربری ثبت نشده است.")
        return
        
    message = "--- **لیست کاربران ربات** ---\n\n"
    for i, (telegram_id, first_name) in enumerate(users, 1):
        message += f"{i}. نام: {first_name} | آیدی: `{telegram_id}`\n"
        
    update.message.reply_text(message, parse_mode='Markdown')

def main():
    """ربات را اجرا می‌کند."""
    # ابتدا دیتابیس را آماده کن
    setup_database()

    # ساخت Updater و Dispatcher
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # ثبت Handler ها
    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("users", list_users))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    # شروع ربات
    updater.start_polling()
    logger.info("Bot started polling.")
    updater.idle()

if __name__ == '__main__':
    main()
