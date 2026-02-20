import telebot
from telebot import types
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import datetime
from flask import Flask, request
import os
import telebot

TOKEN = os.environ.get("TOKEN")
bot = telebot.TeleBot(TOKEN)
app = Flask(__name__)

# ضع كل handlers (add/remove/show items) قبل هذا الجزء
    
# ==============================
# CONFIG
# ==============================
TOKEN = "8022519974:AAFum9LXqTGiy4DDQf32yG5ZukkfYyjyzoI"

cred = credentials.Certificate("inventory_bot/serviceAccountKey.json")
firebase_admin.initialize_app(cred)

db = firestore.client()
bot = telebot.TeleBot(TOKEN)

user_states = {}

# ==============================
# DATABASE FUNCTIONS
# ==============================
def add_item(name, quantity, min_level=5, category="عام"):
    doc_ref = db.collection("items").document(name.lower())
    doc_ref.set({
        "name": name,
        "quantity": quantity,
        "min_level": min_level,
        "category": category
    })

def update_quantity(name, amount):
    doc_ref = db.collection("items").document(name.lower())
    doc = doc_ref.get()
    
    if doc.exists:
        current = doc.to_dict()["quantity"]
        new_quantity = current + amount
        if new_quantity < 0:
            return False, current
        doc_ref.update({"quantity": new_quantity})
        return True, new_quantity
    return None, None

def get_inventory():
    docs = db.collection("items").stream()
    items = [doc.to_dict() for doc in docs]
    return items

def get_low_stock_items():
    return [item for item in get_inventory() if item["quantity"] <= item["min_level"]]

def search_item(name):
    doc_ref = db.collection("items").document(name.lower())
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict()
    return None

# ==============================
# UI
# ==============================
def main_menu():
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True)
    markup.row("📦 عرض المخزون")
    markup.row("➕ إضافة مادة", "➖ إخراج مادة")
    markup.row("⚠️ المواد الناقصة", "🔍 بحث عن مادة")
    return markup

# ==============================
# START
# ==============================
@bot.message_handler(commands=["start"])
def start(message):
    bot.send_message(message.chat.id, "نظام إدارة المخزن المبسط", reply_markup=main_menu())

# ==============================
# SHOW INVENTORY
# ==============================
@bot.message_handler(func=lambda message: message.text == "📦 عرض المخزون")
def show_inventory(message):
    items = get_inventory()
    if not items:
        bot.send_message(message.chat.id, "لا يوجد مواد حالياً")
        return
    text = "📦 المخزون:\n\n"
    categories = {}
    for item in items:
        categories.setdefault(item["category"], []).append(item)
    for cat, cat_items in categories.items():
        text += f"🔹 {cat}:\n"
        for i in cat_items:
            warning = " ⚠️ منخفض" if i["quantity"] <= i["min_level"] else ""
            text += f"  - {i['name']}: {i['quantity']}{warning}\n"
    bot.send_message(message.chat.id, text)

# ==============================
# ADD ITEM
# ==============================
@bot.message_handler(func=lambda message: message.text == "➕ إضافة مادة")
def add_item_start(message):
    user_states[message.chat.id] = {"state": "add_name"}
    bot.send_message(message.chat.id, "اكتب اسم المادة لإضافتها")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict)
                     and user_states[message.chat.id]["state"] == "add_name")
def add_item_name(message):
    user_states[message.chat.id]["name"] = message.text
    user_states[message.chat.id]["state"] = "add_quantity"
    bot.send_message(message.chat.id, "اكتب الكمية")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict)
                     and user_states[message.chat.id]["state"] == "add_quantity")
def add_item_quantity(message):
    try:
        quantity = int(message.text)
        name = user_states[message.chat.id]["name"]
        add_item(name, quantity)
        bot.send_message(message.chat.id, f"تمت إضافة {quantity} من {name}")
        user_states.pop(message.chat.id)
    except:
        bot.send_message(message.chat.id, "ادخل رقم صحيح")

# ==============================
# REMOVE ITEM
# ==============================
@bot.message_handler(func=lambda message: message.text == "➖ إخراج مادة")
def remove_start(message):
    user_states[message.chat.id] = {"state": "remove_name"}
    bot.send_message(message.chat.id, "اكتب اسم المادة للإخراج")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict)
                     and user_states[message.chat.id]["state"] == "remove_name")
def remove_name(message):
    user_states[message.chat.id]["name"] = message.text
    user_states[message.chat.id]["state"] = "remove_quantity"
    bot.send_message(message.chat.id, "اكتب الكمية")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict)
                     and user_states[message.chat.id]["state"] == "remove_quantity")
def remove_quantity(message):
    try:
        quantity = int(message.text)
        name = user_states[message.chat.id]["name"]
        success, new_qty = update_quantity(name, -quantity)
        if success:
            bot.send_message(message.chat.id, f"تم إخراج {quantity} من {name}\nالكمية الجديدة: {new_qty}")
        elif success is False:
            bot.send_message(message.chat.id, "الكمية غير كافية للإخراج")
        else:
            bot.send_message(message.chat.id, "المادة غير موجودة")
        user_states.pop(message.chat.id)
    except:
        bot.send_message(message.chat.id, "ادخل رقم صحيح")

# ==============================
# LOW STOCK ITEMS
# ==============================
@bot.message_handler(func=lambda message: message.text == "⚠️ المواد الناقصة")
def show_low_stock(message):
    low_items = get_low_stock_items()
    if not low_items:
        bot.send_message(message.chat.id, "لا توجد مواد ناقصة حالياً")
        return
    text = "⚠️ المواد الناقصة:\n"
    for item in low_items:
        text += f"- {item['name']}: {item['quantity']}\n"
    bot.send_message(message.chat.id, text)

# ==============================
# SEARCH ITEM
# ==============================
@bot.message_handler(func=lambda message: message.text == "🔍 بحث عن مادة")
def search_start(message):
    user_states[message.chat.id] = {"state": "search_name"}
    bot.send_message(message.chat.id, "اكتب اسم المادة للبحث")

@bot.message_handler(func=lambda message: isinstance(user_states.get(message.chat.id), dict)
                     and user_states[message.chat.id]["state"] == "search_name")
def search_name(message):
    name = message.text
    item = search_item(name)
    if item:
        bot.send_message(message.chat.id, f"{item['name']}: {item['quantity']}")
    else:
        bot.send_message(message.chat.id, "المادة غير موجودة")
    user_states.pop(message.chat.id)


@app.route("/telegram", methods=["POST"])
def telegram_webhook():
    json_str = request.get_data().decode("UTF-8")
    update = telebot.types.Update.de_json(json_str)
    bot.process_new_updates([update])
    return "OK", 200

if __name__ == "__main__":
    bot.remove_webhook()
    # هذا الرابط سيظهر بعد تشغيل المشروع
    bot.set_webhook(url=f"https://{os.environ['REPL_SLUG']}.{os.environ['REPL_OWNER']}.repl.co/telegram")
    app.run(host="0.0.0.0", port=3000)


# ==============================
# RUN BOT
# ==============================
print("BOT STARTED")

bot.infinity_polling()


