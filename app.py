import os
import telebot
import sqlite3
import google.generativeai as genai
import requests
from dotenv import load_dotenv
import time
from datetime import datetime
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('car_bot')

# Load environment variables
load_dotenv()

# Initialize Telegram bot
bot = telebot.TeleBot(os.getenv('TELEGRAM_TOKEN'))

# Configure Gemini AI
gemini_key = os.getenv('GOOGLE_API_KEY')
genai.configure(api_key=gemini_key)

# Initialize the model
model = genai.GenerativeModel('gemini-1.5-pro-latest')

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
    
def get_car_info_with_gemini(car_name):
    """Get detailed car information using Gemini AI"""
    try:
        # Create a structured prompt for Gemini
        structured_prompt = f"""
        Create a comprehensive and engaging description of {car_name} in Russian language.
        Format the response as follows:

        🏢 ИСТОРИЯ И ПРОИСХОЖДЕНИЕ
        [Detailed history and origins of the make/model]

        ⭐ КЛЮЧЕВЫЕ ОСОБЕННОСТИ
        [Key features and characteristics that make this car/brand unique]

        📈 ЭВОЛЮЦИЯ И ПОКОЛЕНИЯ
        [Information about different generations or significant models]

        🔧 ТЕХНИЧЕСКИЕ ХАРАКТЕРИСТИКИ
        [Notable technical specifications and innovations]

        🌟 ДОСТИЖЕНИЯ И НАГРАДЫ
        [Major achievements, awards, and recognition]

        🚀 ИНТЕРЕСНЫЕ ФАКТЫ
        [3-4 fascinating facts about the car/brand]

        Please make the response detailed but concise, using emoji for each section.
        Focus on accuracy and interesting details that car enthusiasts would appreciate.
        """

        # Generate content using Gemini
        response = model.generate_content(structured_prompt)
        
        # Format the response
        formatted_response = response.text + "\n\n🔎 Информация предоставлена AI на основе общедоступных данных"
        
        return formatted_response

    except Exception as e:
        return f"Произошла ошибка при получении информации: {str(e)}"
    
@bot.message_handler(commands=['cars'])
def cars_command(message):
    """Handle the /cars command"""
    try:
        car_query = ' '.join(message.text.split()[1:])
        
        if not car_query:
            usage_message = """
            ⚠️ Пожалуйста, укажите марку или модель автомобиля.

            Примеры использования:
            /cars Toyota Camry
            /cars BMW M5
            /cars Mercedes-Benz
            """
            bot.reply_to(message, usage_message)
            return

        logger.info(f"Processing car query: {car_query}")
        
        # Send typing action
        bot.send_chat_action(message.chat.id, 'typing')
        
        # Get car information using Gemini
        car_info = get_car_info_with_gemini(car_query)
        
        # Search for images
        logger.info(f"Searching images for: {car_query}")
        images = search_car_images(car_query)
        
        # Send images first if available
        if images:
            media_group = []
            for idx, image_url in enumerate(images):
                try:
                    caption = f"🚗 {car_query.upper()} - Фото {idx + 1}" if idx == 0 else ""
                    media_group.append(telebot.types.InputMediaPhoto(image_url, caption=caption))
                except Exception as e:
                    logger.error(f"Error adding image to media group: {e}")
                    continue
            
            if media_group:
                try:
                    logger.info("Sending media group")
                    bot.send_media_group(message.chat.id, media_group)
                except Exception as e:
                    logger.error(f"Error sending media group: {e}")
                    logger.info("Attempting to send images individually")
                    for image in images:
                        try:
                            bot.send_photo(message.chat.id, image)
                        except Exception as img_e:
                            logger.error(f"Error sending individual image: {img_e}")
                            continue
        
        # Send text information with markdown support
        intro_message = f"""
🚗 *{car_query.upper()}*
━━━━━━━━━━━━━━━━━━━━━
"""
        full_response = intro_message + car_info
        
        # Экранируем специальные символы markdown
        full_response = full_response.replace('_', '\_').replace('*', '\*').replace('`', '\`').replace('[', '\[')
        
        try:
            bot.reply_to(message, full_response, parse_mode='MarkdownV2')
        except Exception as e:
            logger.error(f"Error sending markdown message: {e}")
            # Fallback: отправка без markdown если возникла ошибка
            bot.reply_to(message, full_response)
        
        # Save to history
        add_to_history(message.from_user.id, f"/cars {car_query}", car_info)
        logger.info(f"Successfully processed car query for: {car_query}")

    except IndexError:
        logger.warning("No car model specified in command")
        bot.reply_to(message, "Пожалуйста, укажите марку или модель автомобиля. Например: /cars Toyota Camry")
    except Exception as e:
        logger.error(f"Error processing car command: {e}")
        error_message = f"😔 Извините, произошла ошибка при обработке запроса: {str(e)}"
        bot.reply_to(message, error_message)

def search_car_images(car_name, num_images=3):
    """Search for car images using Google Custom Search API"""
    try:
        images = []
        formattedname = ""
        # Форматируем запрос, заменяя пробелы на +
        for i in car_name:
            if i == ' ' or i == '+':
                formattedname += '+'
            else:
                formattedname += i
                
        search_query = f"{formattedname}+car+official"
        coolquery = f"https://www.googleapis.com/customsearch/v1?key=AIzaSyDptyzxGJg-aR5IldozvISzjNgF2_TISJo&cx=e1cac863f07bf4f8b&q={search_query}&searchType=image"
        
        imageresponse = requests.get(coolquery).json()
        
        # Получаем несколько изображений
        for i in range(min(num_images, len(imageresponse.get('items', [])))):
            image_url = imageresponse.get('items')[i].get('link')
            logger.warning(f"Found image URL: {image_url}")
            images.append(image_url)
            
        return images
    except Exception as e:
        logger.error(f"Error in image search: {e}")
        return []


def set_menu_commands():
    """Set bot commands for menu"""
    commands = [
        telebot.types.BotCommand("start", "Запустить бота"),
        telebot.types.BotCommand("help", "Показать справку"),
        telebot.types.BotCommand("weather", "Узнать погоду"),
        telebot.types.BotCommand("nasa", "Фото дня от NASA"),
        telebot.types.BotCommand("cars", "История автомобиля 🚗"),
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
    /cars <марка/модель> - получить подробную историю автомобиля 🚗
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
    /cars BMW M5
    
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