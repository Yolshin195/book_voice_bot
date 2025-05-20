import asyncio
import logging
import os
import sys
from os import getenv

from PIL import Image
from aiogram import Bot, Dispatcher, html, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
import tempfile
from aiogram.types import FSInputFile

from pytesseract import pytesseract
from gtts import gTTS

import cv2
import numpy as np

load_dotenv()

TOKEN = getenv("BOT_TOKEN")

dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    """
    This handler receives messages with `/start` command
    """
    # Most event objects have aliases for API methods that can be called in events' context
    # For example if you want to answer to incoming message you can use `message.answer(...)` alias
    # and the target chat will be passed to :ref:`aiogram.methods.send_message.SendMessage`
    # method automatically or call API method directly via
    # Bot instance: `bot.send_message(chat_id=message.chat.id, ...)`
    await message.answer(f"Hello, {html.bold(message.from_user.full_name)}!")


@dp.message(F.photo)
async def handle_photos(message: Message, bot: Bot) -> None:
    """
    Обработчик для сообщений с фотографиями с распознаванием текста
    """
    # Отправляем сообщение о начале обработки
    await message.answer("Обрабатываю изображение, пожалуйста, подождите...")

    # Получаем информацию о фото (берем последнее, так как оно имеет наилучшее качество)
    photo = message.photo[-1]
    file_id = photo.file_id

    # Получаем информацию о файле через Telegram Bot API
    file_info = await bot.get_file(file_id)
    file_path = file_info.file_path

    file_extension = os.path.splitext(file_path)[1] or '.jpg'

    try:
        # Используем контекстный менеджер для временного файла изображения
        with tempfile.NamedTemporaryFile(suffix=file_extension) as temp_file:
            temp_file_path = temp_file.name

            # Скачиваем файл во временный файл
            await bot.download_file(file_path, destination=temp_file_path)

            # Читаем изображение с помощью OpenCV
            img = cv2.imread(temp_file_path)

            # Предобработка изображения
            # 1. Преобразование в оттенки серого
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            # 2. Масштабирование изображения (увеличение размера)
            scale_factor = 2
            gray = cv2.resize(gray, None, fx=scale_factor, fy=scale_factor, interpolation=cv2.INTER_CUBIC)

            # 3. Применение адаптивного порогового значения
            thresh = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                           cv2.THRESH_BINARY, 11, 2)

            # 4. Удаление шума
            kernel = np.ones((1, 1), np.uint8)
            opening = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel)

            # 5. Увеличение контраста
            result = cv2.GaussianBlur(opening, (3, 3), 0)

            # Распознаем текст с изображения
            result = pytesseract.image_to_string(
                Image.open(temp_file_path),
                lang="eng",
                config='--psm 6 --oem 3 -c tessedit_char_whitelist="ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,!? "',
            )

            if not result.strip():  # Проверяем, что результат не пустой после удаления пробелов
                await message.answer("Не удалось распознать текст на изображении.")
                return

            # Отправляем распознанный текст пользователю
            await message.answer(f"Распознанный текст:\n\n{result}")

            # Используем контекстный менеджер для временного аудио-файла
            with tempfile.NamedTemporaryFile(suffix='.mp3') as audio_file:
                audio_path = audio_file.name

                # Генерируем аудио-файл
                tts = gTTS(text=result, lang='en')
                tts.save(audio_path)
                await bot.send_audio(
                    chat_id=message.chat.id,
                    audio=FSInputFile(audio_path),
                    title="Текст с изображения",
                    performer="Ваш бот"
                )

    except Exception as e:
        logging.error(f"Error during OCR processing: {e}")
        await message.answer(f"Произошла ошибка при распознавании текста: {str(e)}")


@dp.message()
async def handle_text(message: Message, bot: Bot) -> None:
    """
    Обработчик для текстовых сообщений с распознаванием языка и озвучиванием
    английского текста
    """
    try:
        text = message.text

        # Используем контекстный менеджер для временного аудио-файла
        with tempfile.NamedTemporaryFile(suffix='.mp3') as audio_file:
            audio_path = audio_file.name

            # Генерируем аудио-файл
            tts = gTTS(text=text, lang='en')
            tts.save(audio_path)

            # Отправляем аудио пользователю
            await bot.send_audio(
                chat_id=message.chat.id,
                audio=FSInputFile(audio_path),
                title="Озвученный текст",
                performer="Ваш бот"
            )

    except Exception as e:
        logging.error(f"Ошибка при обработке текста: {e}")
        await message.answer(f"Произошла ошибка при обработке текста: {str(e)}")


async def main() -> None:
    # Initialize Bot instance with default bot properties which will be passed to all API calls
    bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

    # And the run events dispatching
    await dp.start_polling(bot)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, stream=sys.stdout)
    asyncio.run(main())