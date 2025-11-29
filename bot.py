import asyncio
import json
import logging
from datetime import datetime

import discord
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Настройки
DISCORD_TOKEN = "MTQ0MzUzNDUwMDA5NjI0OTg3Ng.GU-eab.ivcOvP4uIAObMNCyzIzaUIXV96zI6AT09aS1JQ"
CHANNEL_ID = 1443609164382212258  # ID канала Discord (число!)
SPREADSHEET_ID = "1dvoO3EY87Kc8yzUP2QX0Pda4_fWMKeiuTgkt_lHgUqQ"
RANGE = "Склад!A4:B40"  # диапазон данных
CREDENTIALS_FILE = "botfama-7ff5d892f30e.json"  # путь к JSON‑ключу
CHECK_INTERVAL = 60  # секунды между проверками
ROLE_ID = 1443615042720501832  # ID роли для пинга

# Настройка логгирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("DiscordBot")


class GoogleSheetsClient:
    def __init__(self, credentials_file, spreadsheet_id):
        self.spreadsheet_id = spreadsheet_id
        self.credentials = service_account.Credentials.from_service_account_file(
            credentials_file,
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"]
        )
        self.service = build("sheets", "v4", credentials=self.credentials)

    def get_data(self):
        try:
            result = self.service.spreadsheets().values().get(
                spreadsheetId=self.spreadsheet_id,
                range=RANGE
            ).execute()
            return result.get("values", [])
        except Exception as e:
            logger.error(f"Ошибка при чтении таблицы: {e}")
            return []


class DiscordBot:
    def __init__(self, token, channel_id, sheets_client):
        intents = discord.Intents.default()
        self.client = discord.Client(intents=intents)
        self.token = token
        self.channel_id = channel_id
        self.sheets_client = sheets_client
        self.message_id = None  # ID отправленного сообщения

        @self.client.event
        async def on_ready():
            logger.info(f"Бот запущен как {self.client.user}")
            await self.start_monitoring()

    def format_table(self, data):
        """Форматирует данные: строки вида **`A`** - **`B`**."""
        if not data:
            return "Данные отсутствуют"

        lines = []
        for row in data:
            col_a = row[0] if len(row) > 0 and row[0] else "—"
            col_b = row[1] if len(row) > 1 and row[1] else "—"
            lines.append(f"**`{col_a}`** - **`{col_b}`**")
        return "\n".join(lines)

    async def send_or_edit_message(self, data):
        channel = self.client.get_channel(self.channel_id)
        if not channel:
            logger.error("Канал не найден")
            return

        table_content = self.format_table(data)

        content = (
            f"## <@&{ROLE_ID}>\n"
            f"### {table_content}\n"
        )

        # Ограничиваем длину
        if len(content) > 1900:
            content = content[:1900] + "\n... (данные обрезаны)"

        if not self.message_id:
            # Первое сообщение
            try:
                message = await channel.send(content)
                self.message_id = message.id
                logger.info(f"Сообщение отправлено (ID: {self.message_id})")
            except Exception as e:
                logger.error(f"Ошибка отправки: {e}")
        else:
            # Обновление существующего сообщения
            try:
                message = await channel.fetch_message(self.message_id)
                await message.edit(content=content)
                logger.info(f"Сообщение обновлено (ID: {self.message_id})")
            except discord.NotFound:
                logger.warning("Сообщение не найдено, отправим новое")
                self.message_id = None
                await self.send_or_edit_message(data)
            except Exception as e:
                logger.error(f"Ошибка редактирования: {e}")

    async def start_monitoring(self):
        logger.info("Запуск мониторинга таблицы...")
        while True:
            try:
                data = self.sheets_client.get_data()
                await self.send_or_edit_message(data)
            except Exception as e:
                logger.error(f"Неожиданная ошибка: {e}")
            await asyncio.sleep(CHECK_INTERVAL)

    def run(self):
        try:
            self.client.run(self.token)
        except Exception as e:
            logger.critical(f"Ошибка запуска бота: {e}")


if __name__ == "__main__":
    sheets_client = GoogleSheetsClient(CREDENTIALS_FILE, SPREADSHEET_ID)
    bot = DiscordBot(DISCORD_TOKEN, CHANNEL_ID, sheets_client)
    bot.run()
