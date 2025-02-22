from telebot import TeleBot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
from logic import *
import schedule
import threading
import time
import cv2
import numpy as np
from config import *
from config import ADMINS, ADMIN_PASSWORD

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

@bot.message_handler(commands=['get_my_score'])
def handle_get_my_score(message):
    try:
        user_id = message.chat.id
        
        # Получаем данные из БД
        winners_info = manager.get_winners_img(user_id)
        if not winners_info:
            bot.send_message(user_id, "You haven't won any prizes yet 😢")
            return
        
        # Формируем пути к изображениям
        all_images = os.listdir('img') + os.listdir('hidden_img')
        image_paths = []
        for img in all_images:
            # Проверяем, получено ли изображение
            is_claimed = any(img == winner[0] for winner in winners_info)
            folder = 'img' if is_claimed else 'hidden_img'
            image_paths.append(f'{folder}/{img}')
        
        # Создаем коллаж
        collage = create_collage(image_paths)
        if collage is None:
            raise ValueError("Failed to create collage")
        
        # Сохраняем временный файл
        temp_file = f"temp_collage_{user_id}.jpg"
        cv2.imwrite(temp_file, collage)
        
        # Отправляем пользователю
        with open(temp_file, 'rb') as photo:
            bot.send_photo(user_id, photo, caption="Your achievements 🏆")
        
        # Удаляем временный файл
        os.remove(temp_file)
        
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")

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

@bot.message_handler(commands=['help'])
def handle_help(message):
    help_text = """
Bot Help

Basic Commands:
/start - Register to start the game.
/rating - View the top 10 players by points.
/get_my_score - See your collected prizes as a collage.

How to Play?
- Every hour, the bot sends a hidden image.
- The first 3 users to click "Get it!" win the prize!

For Admins:
/add_image [password] - Upload a new image.
"""

    bot.reply_to(message, help_text, parse_mode=None)  # Без разметки

@bot.message_handler(commands=['get_my_score'])
def handle_get_my_score(message):
    try:
        user_id = message.chat.id

        # Получаем список полученных изображений
        won_images = manager.get_winners_img(user_id)
        if not won_images:
            bot.send_message(user_id, "🌟 You haven't won any prizes yet!")
            return

        # Формируем пути ко всем изображениям
        all_images = set(os.listdir('img')) | set(os.listdir('hidden_img'))
        collage_paths = []
        for img in all_images:
            if img in won_images:
                collage_paths.append(f'img/{img}')
            else:
                collage_paths.append(f'hidden_img/{img}')

        # Создаем коллаж
        collage = create_collage(collage_paths, tile_size=(300, 300))
        if collage is None:
            raise ValueError("No images to create collage")

        # Сохраняем временный файл
        temp_path = f"temp_{user_id}.jpg"
        cv2.imwrite(temp_path, collage)

        # Отправляем коллаж
        with open(temp_path, 'rb') as photo:
            bot.send_photo(user_id, photo, caption="Your Collection 🎁")

        # Удаляем временный файл
        os.remove(temp_path)

    except Exception as e:
        bot.reply_to(message, f"⚠️ Error: {str(e)}")

@bot.message_handler(commands=['get_my_score'])
def handle_get_my_score(message):
    try:
        user_id = message.chat.id
        
        # Получаем данные из БД
        winners_info = manager.get_winners_img(user_id)
        if not winners_info:
            bot.send_message(user_id, "You haven't won any prizes yet 😢")
            return
        
        # Формируем пути к изображениям
        all_images = set(os.listdir('img')) | set(os.listdir('hidden_img'))
        image_paths = []
        for img in all_images:
            is_claimed = any(img == winner[0] for winner in winners_info)
            folder = 'img' if is_claimed else 'hidden_img'
            image_paths.append(f'{folder}/{img}')
        
        # Создаем коллаж
        collage = create_collage(image_paths)
        if collage is None:
            raise ValueError("Failed to create collage")
        
        # Сохраняем временный файл
        temp_file = f"temp_collage_{user_id}.jpg"
        cv2.imwrite(temp_file, collage)
        
        # Отправляем пользователю
        with open(temp_file, 'rb') as photo:
            bot.send_photo(user_id, photo, caption="Your achievements 🏆")
        
        # Удаляем временный файл
        os.remove(temp_file)
        
    except Exception as e:
        bot.reply_to(message, f"Error: {str(e)}")


@bot.message_handler(commands=['add_image'])
def handle_add_image(message):
    if message.from_user.id not in ADMINS:
        bot.reply_to(message, "🚫 Access denied!")
        return

    bot.reply_to(message, "📤 Send me the image!")
    bot.register_next_step_handler(message, process_image)

def process_image(message):
    if message.photo:
        file_info = bot.get_file(message.photo[-1].file_id)
        downloaded_file = bot.download_file(file_info.file_path)
        img_name = f"img_{time.time()}.jpg"
        with open(f'img/{img_name}', 'wb') as f:
            f.write(downloaded_file)
        manager.add_prize(img_name)
        bot.reply_to(message, "✅ Image added successfully!")

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
