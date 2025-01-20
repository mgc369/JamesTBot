import os
import telebot
import sqlite3
import google.generativeai as genai
import requests
from dotenv import load_dotenv
import time
from datetime import datetime

# Load environment variables
load_dotenv()

# Initialize Telegram bot
bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

# Configure Gemini AI
gemini_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=gemini_key)

# Initialize the model
model = genai.GenerativeModel('gemini-pro')

# API configurations
WEATHER_API_KEY = os.getenv('WEATHER_API_KEY')
NASA_API_KEY = os.getenv('NASA_API_KEY')
WEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5/weather"

# Database functions
def init_db():
    """Initialize SQLite database"""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS messages
                    (user_id INTEGER, 
                     message TEXT,
                     response TEXT,
                     timestamp DATETIME)''')
        conn.commit()
        conn.close()
        print("Database initialized successfully")
    except Exception as e:
        print(f"Error initializing database: {e}")

def add_to_history(user_id, message, response):
    """Add message and response to history"""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute('INSERT INTO messages VALUES (?, ?, ?, ?)',
                 (user_id, message, response, datetime.now()))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error adding to history: {e}")

def get_chat_history(user_id, limit=5):
    """Get chat history for user"""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute('''SELECT message, response 
                    FROM messages 
                    WHERE user_id = ? 
                    ORDER BY timestamp DESC LIMIT ?''',
                 (user_id, limit))
        history = c.fetchall()
        conn.close()
        return history[::-1]  # Reverse to get chronological order
    except Exception as e:
        print(f"Error getting chat history: {e}")
        return []

def clear_history(user_id):
    """Clear chat history for specific user"""
    try:
        conn = sqlite3.connect('chat_history.db')
        c = conn.cursor()
        c.execute('DELETE FROM messages WHERE user_id = ?', (user_id,))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"Error clearing history: {e}")

def get_weather(city):
    """Get weather information for a given city"""
    try:
        params = {
            'q': city,
            'appid': WEATHER_API_KEY,
            'units': 'metric'
        }
        response = requests.get(WEATHER_BASE_URL, params=params)
        data = response.json()
        
        if response.status_code == 200:
            weather_desc = data['weather'][0]['description']
            temp = data['main']['temp']
            humidity = data['main']['humidity']
            return f"🌍 Погода в {city}:\n" \
                   f"🌤 {weather_desc.capitalize()}\n" \
                   f"🌡 Температура: {temp:.1f}°C\n" \
                   f"💧 Влажность: {humidity}%"
        else:
            return "Извините, город не найден или произошла ошибка."
    except Exception as e:
        return f"Произошла ошибка при получении погоды: {str(e)}"

def get_nasa_apod():
    """Get NASA's Astronomy Picture of the Day"""
    try:
        url = f"https://api.nasa.gov/planetary/apod?api_key={NASA_API_KEY}"
        response = requests.get(url)
        data = response.json()
        
        if response.status_code == 200:
            title = data['title']
            explanation = data['explanation']
            image_url = data.get('url', '')
            
            message = f"🌌 {title}\n\n{explanation}\n\n🔭 Изображение: {image_url}"
            return message
        else:
            return "Извините, не удалось получить данные от NASA API."
    except Exception as e:
        return f"Произошла ошибка при получении данных NASA: {str(e)}"

def set_menu_commands():
    """Set bot commands for menu"""
    commands = [
        telebot.types.BotCommand("start", "Запустить бота"),
        telebot.types.BotCommand("help", "Показать справку"),
        telebot.types.BotCommand("weather", "Узнать погоду"),
        telebot.types.BotCommand("nasa", "Фото дня от NASA"),
        telebot.types.BotCommand("clear", "Очистить историю")
    ]
    bot.set_my_commands(commands)

# Bot command handlers
@bot.message_handler(commands=['start'])
def send_welcome(message):
    """Handle the /start command"""
    welcome_text = """
    👋 Привет! Я AI чат-бот с функцией погоды и NASA APOD!

    Доступные команды:
    /help - показать список команд
    /weather <город> - узнать погоду в городе
    /nasa - получить астрономическое фото дня
    /clear - очистить историю разговора
    
    Также вы можете задать мне любой вопрос, и я постараюсь помочь!
    """
    bot.reply_to(message, welcome_text)

@bot.message_handler(commands=['help'])
def send_help(message):
    """Handle the /help command"""
    help_text = """
    📚 Список доступных команд:
    
    /start - начать общение с ботом
    /help - показать это сообщение
    /weather <город> - узнать погоду в городе
    /nasa - получить астрономическое фото дня
    /clear - очистить историю разговора
    
    Примеры:
    /weather Алматы
    /weather Moscow
    
    Для общения с AI просто напишите свой вопрос!
    """
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['weather'])
def weather_command(message):
    """Handle the /weather command"""
    try:
        city = message.text.split()[1]
        weather_info = get_weather(city)
        bot.reply_to(message, weather_info)
    except IndexError:
        bot.reply_to(message, "Пожалуйста, укажите город. Например: /weather Алматы")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {str(e)}")

@bot.message_handler(commands=['nasa'])
def nasa_command(message):
    """Handle the /nasa command"""
    try:
        nasa_info = get_nasa_apod()
        bot.reply_to(message, nasa_info)
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка: {str(e)}")

@bot.message_handler(commands=['clear'])
def clear_command(message):
    """Handle the /clear command"""
    try:
        clear_history(message.from_user.id)
        bot.reply_to(message, "История разговора очищена!")
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при очистке истории: {str(e)}")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    """Handle all other messages with AI"""
    try:
        # Get chat history
        history = get_chat_history(message.from_user.id)
        
        # Prepare context from history
        context = "Previous conversation:\n"
        for msg, resp in history:
            context += f"User: {msg}\nAssistant: {resp}\n"
        
        # Add current message to context
        prompt = f"{context}\nUser: {message.text}\nAssistant: "
        
        # Generate response using Gemini
        response = model.generate_content(prompt)
        response_text = response.text
        
        # Save to history
        add_to_history(message.from_user.id, message.text, response_text)
        
        bot.reply_to(message, response_text)
    except Exception as e:
        bot.reply_to(message, f"Извините, произошла ошибка: {str(e)}")

def main():
    """Main function to run the bot"""
    print("Bot started...")
    
    # Initialize database
    init_db()
    
    # Set up menu commands
    set_menu_commands()
    
    while True:
        try:
            print("Starting bot polling...")
            bot.polling(none_stop=True)
        except Exception as e:
            print(f"Error occurred: {e}")
            time.sleep(15)

if __name__ == "__main__":
    main()