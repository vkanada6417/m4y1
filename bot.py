from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
from config import *

bot = TeleBot(API_TOKEN)

def gen_markup(prize_id):
    markup = InlineKeyboardMarkup()
    markup.row_width = 1
    markup.add(InlineKeyboardButton("Get it!", callback_data=prize_id))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    prize_id = call.data
    user_id = call.from_user.id

    # Check if prize is already claimed by 3 users
    if manager.get_prize_claim_count(prize_id) >= 3:
        bot.answer_callback_query(call.id, "❌ Prize already claimed by 3 users!")
        return

    # Attempt to claim the prize
    if manager.claim_prize(prize_id, user_id):
        img = manager.get_prize_img(prize_id)
        try:
            with open(f'img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo)
                bot.answer_callback_query(call.id, "🎉 Congratulations! You got the prize!")
        except FileNotFoundError:
            bot.answer_callback_query(call.id, "⚠️ Error: Image not found.")
    else:
        bot.answer_callback_query(call.id, "❌ Failed to claim. Try again!")

@bot.message_handler(commands=['start'])
def handle_start(message):
    user_id = message.chat.id
    if manager.user_exists(user_id):
        bot.reply_to(message, "ℹ️ You are already registered!")
    else:
        manager.add_user(user_id, message.from_user.username)
        bot.reply_to(message, """👋 Welcome! You've been registered successfully!

🕒 Every hour, you'll receive hidden images.
🏃 Be the first 3 to click 'Get it!' to unlock them!

/rating - Check the leaderboard""", parse_mode='Markdown')

@bot.message_handler(commands=['rating'])
def handle_rating(message):
    users = manager.get_users_rating()
    if not users:
        bot.reply_to(message, "📭 The leaderboard is empty.")
        return

    # Format leaderboard table
    table = "🏆 **Leaderboard** 🏆\n\n"
    table += "| Rank | Username       | Points |\n"
    table += "|------|----------------|--------|\n"
    for idx, (username, points) in enumerate(users[:10], 1):  # Top 10
        table += f"| {idx}    | {username or 'Anonymous'} | {points}    |\n"
    
    bot.reply_to(message, table, parse_mode='Markdown')

def send_message():
    prize = manager.get_available_prize()
    if not prize:
        return
    
    prize_id, img = prize
    manager.reset_prize_claims(prize_id)
    hide_img(img)  # Assume this function moves/encrypts the image
    
    for user_id in manager.get_active_users():
        try:
            with open(f'hidden_img/{img}', 'rb') as photo:
                bot.send_photo(user_id, photo, 
                             caption="🔍 New hidden image available!",
                             reply_markup=gen_markup(prize_id))
        except Exception as e:
            print(f"Error sending image: {e}")

def schedule_thread():
    schedule.every().hour.at(":00").do(send_message)  # Send every hour
    while True:
        schedule.run_pending()
        time.sleep(1)

def polling_thread():
    bot.infinity_polling()

if __name__ == '__main__':
    manager = DatabaseManager(DATABASE)
    manager.create_tables()  # Правильное имя метода

    # Start threads
    threading.Thread(target=polling_thread, daemon=True).start()
    threading.Thread(target=schedule_thread, daemon=True).start()

    # Keep main thread alive
    while True:
        time.sleep(3600)
  
