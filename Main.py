import requests
from bs4 import BeautifulSoup
from telegram.ext import Updater, CommandHandler

TOKEN = "توکن_ربات_تلگرامت"

def get_gold_price():
    url = "https://www.tgju.org/profile/geram18"
    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')
    
    price_tag = soup.find("span", {"id": "l-price"})
    if price_tag:
        return price_tag.text.strip()
    else:
        return "قیمت پیدا نشد"

def gold(update, context):
    price = get_gold_price()
    update.message.reply_text(f"💰 قیمت طلای ۱۸ عیار: {price} تومان")

updater = Updater(TOKEN, use_context=True)
dp = updater.dispatcher
dp.add_handler(CommandHandler("gold", gold))

updater.start_polling()
updater.idle()
