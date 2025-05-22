
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils import executor
import aiohttp
import config

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(bot)

user_states = {}
user_alerts = {}

class Alert:
    def __init__(self, exchange, symbol, price):
        self.exchange = exchange
        self.symbol = symbol
        self.price = price

@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    chat_id = message.chat.id
    user_states[chat_id] = {'step': 'exchange'}
    markup = InlineKeyboardMarkup(row_width=2)
    markup.add(
        InlineKeyboardButton("Binance", callback_data="exchange_binance"),
        InlineKeyboardButton("MEXC", callback_data="exchange_mexc")
    )
    await message.answer("👋 Оберіть біржу:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith("exchange_"))
async def handle_exchange(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    exchange = callback.data.split("_")[1]
    user_states[chat_id] = {'step': 'symbol', 'exchange': exchange}
    await bot.edit_message_text(
        "✏️ Введіть пару токенів (наприклад BTCUSDT):",
        chat_id=chat_id,
        message_id=callback.message.message_id
    )

@dp.message_handler()
async def handle_input(message: types.Message):
    chat_id = message.chat.id
    state = user_states.get(chat_id, {})

    if state.get('step') == 'symbol':
        user_states[chat_id]['symbol'] = message.text.strip().upper()
        user_states[chat_id]['step'] = 'price'
        await message.answer("💰 Введіть цільову ціну:")
    elif state.get('step') == 'price':
        try:
            price = float(message.text.replace(',', '.'))
            alert = Alert(
                user_states[chat_id]['exchange'],
                user_states[chat_id]['symbol'],
                price
            )
            user_alerts.setdefault(chat_id, []).append(alert)
            user_states[chat_id] = {'step': 'done'}
            await message.answer(f"✅ Алерт створено на {alert.symbol} при {alert.price} ({alert.exchange})")
        except ValueError:
            await message.answer("❌ Введіть коректне число.")

@dp.message_handler(commands=['alerts'])
async def list_alerts(message: types.Message):
    chat_id = message.chat.id
    alerts = user_alerts.get(chat_id, [])
    if not alerts:
        await message.answer("⛔ У вас немає активних алертів.")
        return

    text = "📋 Ваші алерти:"
    for idx, alert in enumerate(alerts, 1):
        text += f"{idx}. {alert.symbol} ≥ {alert.price} ({alert.exchange})\n"
    await message.answer(text)

@dp.message_handler(commands=['menu'])
async def back_to_menu(message: types.Message):
    await start_handler(message)

async def check_prices():
    while True:
        for chat_id, alerts in user_alerts.items():
            for alert in alerts:
                current = await fetch_price(alert.exchange, alert.symbol)
                if current != -1 and current >= alert.price:
                    await bot.send_message(chat_id, f"🚨 {alert.symbol} досяг {current} на {alert.exchange}")
                    alerts.remove(alert)
        await asyncio.sleep(1)

async def fetch_price(exchange, symbol):
    try:
        url = f"https://api.binance.com/api/v3/ticker/price?symbol={symbol}" if exchange == "binance" \
              else f"https://www.mexc.com/open/api/v2/market/ticker?symbol={symbol}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as resp:
                data = await resp.json()
                if exchange == "binance":
                    return float(data["price"])
                else:
                    return float(data["data"][0]["last"])
    except:
        return -1

async def on_startup(dp):
    asyncio.create_task(check_prices())

if __name__ == '__main__':
    from aiogram import executor
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
