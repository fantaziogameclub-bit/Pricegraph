import os
import logging
import psycopg2
from datetime import datetime
import jdatetime
import requests
from bs4 import BeautifulSoup
from telegram import ReplyKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext
from urllib.parse import urlparse


# -------------------- Logging --------------------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO)
logger = logging.getLogger(__name__)

# -------------------- Environment Variables --------------------
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
DATABASE_URL = os.getenv("DATABASE_URL")

if not BOT_TOKEN or not ADMIN_ID or not DATABASE_URL:
    logger.error("FATAL: Missing essential environment variables.")
    exit(1)

ADMIN_ID = int(ADMIN_ID)

# -------------------- TGJU Item IDs --------------------
ITEM_IDS = {
    "طلا ۱۸ عیار": 137121,
    "طلا ۲۴ عیار": 137122,
    # "تمام سکه امامی": 656113,
    # "تمام سکه آزادی": 656114,
    # "نیم  سکه": 656115,
    # "ربع  سکه": 656116,
    "دلار آمریکا": 137203,
    "یورو": 137205,
    "پارسیان 100 سوت": 656113,
    "پارسیان 200 سوت": 656115,
    "پارسیان 500 سوت": 656121,
    "سکه گرمی": 137141,
    "تمام سکه امامی": 137138,
    "تمام سکه آزادی": 137137,
    "نیم  سکه": 137139,
    "ربع  سکه": 137140,
    "سکه امامی 86": 137142,
    "نیم   سکه 86": 137143,
    "ربع   سکه 86": 137144,
    "ارزش واقعی سکه": 137158,
    # ref: https://www.tgju.org/widget/get/ticker#ids=137119

}


# -------------------- Database Functions --------------------
def get_connection():
    try:
        result = urlparse(DATABASE_URL)
        return psycopg2.connect(
            dbname=result.path[1:],    
            user=result.username,
            password=result.password,
            host=result.hostname,
            port=result.port
        )
    except psycopg2.OperationalError as e:
        logger.error(f"Database connection error: {e}")
        return None

def setup_database():
    conn = get_connection()
    if not conn:
        return
    with conn.cursor() as cursor:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                telegram_id BIGINT UNIQUE NOT NULL,
                first_name TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        conn.commit()
    conn.close()

def add_user(user: dict):
    conn = get_connection()
    if not conn:
        logger.error("Database connection is not available.")
        return     
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO users (telegram_id, first_name) VALUES (%s, %s) ON CONFLICT (telegram_id) DO NOTHING",
        (user['id'], user['first_name'])
    )
    conn.commit()
    conn.close()


def get_all_users():
    conn = get_connection()
    if not conn:
        return []
    cursor = conn.cursor()
    cursor.execute("SELECT telegram_id, first_name FROM users ORDER BY id DESC")
    users = cursor.fetchall()
    conn.close()
    return users        

# -------------------- Date (Jalali) --------------------
def get_jalali_datetime():
    now = datetime.now()
    jalali_date_day = jdatetime.datetime.fromgregorian(datetime=now).strftime("%A")
    jalali_date = jdatetime.datetime.fromgregorian(datetime=now).strftime("%d %B %Y")
    time_str = now.strftime("Time %H:%M")
    return f"🗓️ {jalali_date_day}\n🗓️ {jalali_date}\n🕰️ {time_str}\n\n"

# -------------------- TGJU API: Numeric ID --------------------
def format_price(price_str: str) -> str:
    """تبدیل قیمت به عدد و جدا کردن سه رقمی با کاما (یا جداکننده فارسی)"""
    try:
        clean = ''.join(ch for ch in price_str if ch.isdigit())
        if not clean:
            return price_str
        
        # تبدیل ریال به تومان (تقسیم بر 10)
        toman_value = int(clean) // 10

        return "{:,}".format(toman_value)  # اگر جداکننده فارسی خواستی: .replace(",", "٬")
    except ValueError:
        return price_str


def get_price_by_id(item_id: int):
    """دریافت قیمت از API TGJU با ID عددی و پاکسازی HTML"""
    # try:
    url = f"https://api.tgju.org/v1/widget/tmp?keys={item_id}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                        "(KHTML, like Gecko) Chrome/118.0 Safari/537.36",
        "Accept": "application/json"
    }
    resp = requests.get(url, headers=headers, timeout=10)
    resp.raise_for_status()

    data = resp.json()
    indicators = data["response"]["indicators"]
    if not indicators:
        return "یافت نشد"

    raw_html = indicators[0]["p"]  # یا "prices" بسته به خروجی
    clean_prices = BeautifulSoup(raw_html, "html.parser").get_text()

    # اعمال فرمت سه رقمی جداکننده
    return format_price(clean_prices)


# -------------------- Price Functions --------------------
def get_gold_prices():
    geram18 = get_price_by_id(ITEM_IDS["طلا ۱۸ عیار"])
    geram24 = get_price_by_id(ITEM_IDS["طلا ۲۴ عیار"])
    return (
        "--<->-- **قیمت طلا** --<->--\n\n"
        f"طلای ۱۸ عیار: {geram18}\n"
        f"طلای ۲۴ عیار: {geram24}"
    )

def get_currency_prices():
    usd = get_price_by_id(ITEM_IDS["دلار آمریکا"])
    eur = get_price_by_id(ITEM_IDS["یورو"])
    return (
        "--<->-- **قیمت ارز (بازار آزاد)** --<->--\n\n"
        f"دلار : {usd}\n"
        f"یورو : {eur}"
    )


def get_parsian_prices():
    message = "--<->-- **قیمت سکه پارسیان** --<->--\n\n"
    for label in ["پارسیان 100 سوت", 
                  "پارسیان 200 سوت", 
                  "پارسیان 500 سوت"
                  ]:
        price = get_price_by_id(ITEM_IDS[label])
        message += f"{label}: {price}\n"
    gerami_price = get_price_by_id(ITEM_IDS["سکه گرمی"])
    message += f"\nسکه گرمی: {gerami_price}"
    return message

def get_coin_prices():
    message = "--<->-- **قیمت سکه** --<->--\n\n"
    for label in ["تمام سکه امامی",
                  "تمام سکه آزادی", 
                  "نیم  سکه", 
                  "ربع  سکه", 
                  "سکه امامی 86", 
                  "نیم   سکه 86",
                  "ربع   سکه 86",
                  "ارزش واقعی سکه"
                  ]:
        price = get_price_by_id(ITEM_IDS[label])
        message += f"{label}: {price}\n"
    return message

# -------------------- Telegram Handlers --------------------
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    add_user(user)
    keyboard = [
        ['طلا', 'سکه'],
        ['ارز', 'سکه پارسیان']
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

    update.message.reply_text(
        f"سلام {user.first_name}!\n"
        "برای دریافت قیمت لحظه‌ای یکی از گزینه‌ها رو بزن\n" \
        "مرجع سایت www.tgju.org\n\n" \
        "(قیمت‌ها به تومان می‌باشد)",
        reply_markup=reply_markup
    )

def handle_message(update: Update, context: CallbackContext):
    user_choice = update.message.text
    chat_id = update.message.chat_id

    # پیام لودینگ
    loading_message = context.bot.send_message(chat_id=chat_id, text="کمی صبر کنید، در حال گرفتن قیمت...")

    if user_choice == 'طلا':
        response_text = get_gold_prices()
    elif user_choice == 'سکه':
        response_text = get_coin_prices()
    elif user_choice == 'ارز':
        response_text = get_currency_prices()
    elif user_choice == 'سکه پارسیان':
        response_text = get_parsian_prices()
    else:
        context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
        update.message.reply_text("لطفاً یکی از گزینه‌های استاندارد را انتخاب کنید.")
        return

    full_message = get_jalali_datetime() + response_text

    context.bot.delete_message(chat_id=chat_id, message_id=loading_message.message_id)
    update.message.reply_text(full_message, parse_mode='Markdown')

def users(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id != ADMIN_ID:
        update.message.reply_text("شما اجازه‌ی دسترسی به این دستور را ندارید.")
        return

    users = get_all_users()
    if not users:
        update.message.reply_text("هنوز هیچ کاربری ثبت نشده است.")
        return

    message = "->-<- **لیست کاربران ربات** ->-<-\n\n"
    for i, (telegram_id, first_name) in enumerate(users, 1):
        message += f"{i}. نام: {first_name} | آیدی: `{telegram_id}`\n"

    update.message.reply_text(message, parse_mode='Markdown')

# -------------------- Main --------------------
def main():
    setup_database()
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    dispatcher.add_handler(CommandHandler("start", start))
    dispatcher.add_handler(CommandHandler("users", users))
    dispatcher.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_message))

    updater.start_polling()
    logger.info("Bot started polling.")
    updater.idle()
    

if __name__ == '__main__':
    main()

