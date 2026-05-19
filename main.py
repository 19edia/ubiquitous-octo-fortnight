import logging
import os
import asyncio
import uvicorn
import json
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, CallbackQueryHandler, filters
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

# Configurar o logging para monitorar o comportamento do sistema
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# Carrega variáveis de ambiente de um arquivo .env (útil para testes locais)
load_dotenv()

# --- Configurações do Jogo ---
PLAYERS_FILE = "players.json"
CLASSES = [
    "Guerreiro ⚔️", "Mago 🧙", "Arqueiro 🏹", "Ladino 🗡️",
    "Paladino 🛡️", "Druida 🌿", "Necromante 💀", "Bardo 🪕"
]
GENDERS = ["Masculino ♂️", "Feminino ♀️", "Não-binário ⚧️"]

CLASS_LORE = {
    "Guerreiro ⚔️": "A Magia de Sangue corre em suas veias. Você sente seus músculos pulsarem com uma fúria ancestral, permitindo que você ignore a dor e esmague armaduras com as mãos nuas.",
    "Mago 🧙": "O Arcanismo Puro se manifesta como chamas azuis ao seu redor. O conhecimento de eras passadas invade sua mente, permitindo que você dobre a realidade à sua vontade.",
    "Arqueiro 🏹": "Suas flechas agora carregam o Encantamento do Vento. Você percebe que pode ouvir o sussurro da brisa, guiando seus projéteis para pontos vitais ocultos.",
    "Ladino 🗡️": "As Sombras se tornam suas aliadas. Você aprende a arte de se tornar um com a escuridão, onde o veneno em suas lâminas brilha com uma luz gélida.",
    "Paladino 🛡️": "A Luz Divina emana de sua alma. Você se torna um farol de esperança, capaz de curar feridas graves e punir o mal com o fogo do julgamento.",
    "Druida 🌿": "As Forças da Natureza atendem ao seu comando. Você sente a vida das florestas no corpo, permitindo que você mude de forma e conjure raízes colossais.",
    "Necromante 💀": "As Artes das Trevas não o assustam. Você descobre que a morte é apenas o começo, ganhando o poder de erguer servos leais e drenar a vida inimiga.",
    "Bardo 🪕": "Suas Melodias Místicas alteram o destino. Ao tocar a primeira nota, a música pode curar corações ou despedaçar a mente de exércitos inteiros."
}

# URLs de Banners (Substitua pelos seus links de PNG reais)
BANNER_MENU = "Gemini_Generated_Image_231x1w231x1w231x (1).png"
BANNER_CAP1 = "menu.jpg"

# --- Persistência Simples ---
def load_players():
    if os.path.exists(PLAYERS_FILE):
        try:
            with open(PLAYERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}

def save_player(user_id, data):
    players = load_players()
    players[str(user_id)] = data
    with open(PLAYERS_FILE, "w", encoding="utf-8") as f:
        json.dump(players, f, indent=4, ensure_ascii=False)
# --- Lógica Central do Jogo ---
def get_game_response(text: str, user_name: str) -> str:
    text = text.lower().strip()
    
    if text == "/start":
        return f"⚔️ Bem-vindo ao Reino, {user_name}!"
    elif text == "/ping":
        return "Pong! 🏓 O servidor está rodando perfeitamente."
    elif text == "/help":
        return "📜 <b>Comandos:</b>\n/start - Iniciar\n/help - Ajuda\n/ping - Status"
    return f"Você disse: '{text}'. O mestre da guilda ainda está treinando os comandos de combate!"

# --- Handlers do Telegram ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    players = load_players()
    user_id = str(user.id)

    if user_id in players:
        await show_main_menu(update, context)
    else:
        await update.message.reply_html(
            f"Olá {user.first_name}! Vejo que você é novo por aqui.\n\n"
            "Para começar sua jornada, primeiro me diga: <b>Qual será o nome do seu herói?</b>"
        )
        context.user_data['registering'] = 'waiting_name'

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    p = load_players().get(user_id)
    
    caption = (
        f"🏰 <b>MENU PRINCIPAL</b>\n\n"
        f"👤 <b>Herói:</b> {p['name']}\n"
        f"⚧ <b>Gênero:</b> {p['gender']}\n"
        f"🔰 <b>Classe:</b> {p['class']}\n"
        f"📈 <b>Nível:</b> {p['level']} | 💰 <b>Ouro:</b> {p['gold']}\n\n"
        f"<i>O que deseja fazer agora, {p['name']}?</i>"
    )
    
    keyboard = [
        [InlineKeyboardButton("📖 Começar História", callback_data="start_story")],
        [InlineKeyboardButton("🎒 Inventário", callback_data="inv"), InlineKeyboardButton("🏆 Ranking", callback_data="rank")]
    ]
    
    if update.message:
        await update.message.reply_photo(photo=BANNER_MENU, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await update.callback_query.message.reply_photo(photo=BANNER_MENU, caption=caption, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
        await update.callback_query.message.delete()

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user_id = str(update.effective_user.id)
    state = context.user_data.get('registering')

    if state == 'waiting_name':
        hero_name = update.message.text
        context.user_data['temp_name'] = hero_name
        context.user_data['registering'] = 'choosing_class'

        keyboard = []
        # Cria botões em 2 colunas
        for i in range(0, len(CLASSES), 2):
            row = [
                InlineKeyboardButton(CLASSES[i], callback_data=CLASSES[i]),
                InlineKeyboardButton(CLASSES[i+1], callback_data=CLASSES[i+1])
            ]
            keyboard.append(row)
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            f"Belo nome, {hero_name}! Agora, escolha sua classe:",
            reply_markup=reply_markup
        )
    else:
        # Se não estiver registrando, usa a lógica normal de resposta
        response = get_game_response(update.message.text, update.effective_user.first_name)
        await update.message.reply_html(response)

async def class_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    data = query.data

    if data in CLASSES:
        context.user_data['temp_class'] = data
        context.user_data['registering'] = 'choosing_gender'
        
        keyboard = [[InlineKeyboardButton(g, callback_data=f"gender_{g}") for g in GENDERS]]
        await query.edit_message_text(
            text=f"Ótima escolha! Agora, qual o gênero do seu herói?",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
    
    elif data.startswith("gender_"):
        gender = data.split("_")[1]
        await finish_registration(update, context, gender)

    elif data == "start_story":
        await start_chapter_1(update, context)

    elif data.startswith("magic_"):
        choice = data.split("_")[1]
        await magic_result(update, context, choice == "yes")

async def finish_registration(update: Update, context: ContextTypes.DEFAULT_TYPE, gender: str) -> None:
    query = update.callback_query
    user_id = update.effective_user.id
    hero_name = context.user_data.get('temp_name')
    hero_class = context.user_data.get('temp_class')

    player_data = {
        "name": hero_name,
        "class": hero_class,
        "gender": gender,
        "level": 1,
        "xp": 0,
        "gold": 10,
        "telegram_name": update.effective_user.username
    }
    save_player(user_id, player_data)
    context.user_data['registering'] = None
    await show_main_menu(update, context)

async def start_chapter_1(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user_id = str(update.effective_user.id)
    p = load_players().get(user_id)
    
    text = (
        "🌅 <b>CAPÍTULO 1: O Despertar</b>\n\n"
        "Você acorda sentindo o chão frio de pedra. Sua cabeça lateja. Ao abrir os olhos, percebe que está em uma cela úmida.\n\n"
        "De repente, um homem robusto com uma armadura gasta chuta as grades e grita:\n"
        "<i>— Levanta mano! O rei não paga por prisioneiros dorminhocos!</i>\n\n"
        f"Ele olha para você com desconfiança e continua:\n"
        f"— Você tem um olhar diferente... Me diga, {p['name']}, você quer aprender a despertar a <b>{p['class'].split()[0]} Magia</b> que corre no seu sangue?"
    )
    
    keyboard = [
        [InlineKeyboardButton("✅ Sim", callback_data="magic_yes"), InlineKeyboardButton("❌ Não", callback_data="magic_no")]
    ]
    await query.message.reply_photo(photo=BANNER_CAP1, caption=text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    await query.message.delete()

async def magic_result(update: Update, context: ContextTypes.DEFAULT_TYPE, accepted: bool) -> None:
    query = update.callback_query
    user_id = str(update.effective_user.id)
    p = load_players().get(user_id)
    
    if accepted:
        lore = CLASS_LORE.get(p['class'], "Sua alma brilha com um poder desconhecido.")
        msg = f"✨ <b>O DESPERTAR</b>\n\n{lore}\n\nO homem sorri de canto: <i>— Sabia que você era especial. Prepare-se, nossa jornada começou.</i>"
    else:
        msg = "🌑 <b>A RECUSA</b>\n\nVocê decide ignorar o chamado. O homem dá de ombros e sai batendo a porta: <i>— Que desperdício de potencial... Fique aí então.</i>"

    keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data="back_menu")]]
    await query.message.reply_html(msg, reply_markup=InlineKeyboardMarkup(keyboard))
    await query.message.delete()
    # Nota: No callback_handler, adicione uma lógica para "back_menu" chamar show_main_menu

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = get_game_response("/help", "")
    await update.message.reply_html(response)

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    response = get_game_response("/ping", "")
    await update.message.reply_text(response)

# --- Configuração do Bot e Servidor Web ---
token = os.getenv("TELEGRAM_TOKEN")
if not token:
    logger.error("TELEGRAM_TOKEN não configurado!")
    token = "dummy_token" # Evita quebrar o build do FastAPI antes de configurar o ENV

application = Application.builder().token(token).build()

# Registra os handlers de comando no Telegram
application.add_handler(CommandHandler("start", start))
application.add_handler(CommandHandler("help", help_command))
application.add_handler(CommandHandler("ping", ping))
application.add_handler(CallbackQueryHandler(class_button))
application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if token != "dummy_token":
        await application.initialize()
        await application.start()
        if application.updater:
            await application.updater.start_polling()
        logger.info("Bot Telegram iniciado.")
    else:
        logger.warning("Bot não iniciado: Token ausente.")
        
    yield
    
    if token != "dummy_token":
        if application.updater:
            await application.updater.stop()
        await application.stop()
        await application.shutdown()
        logger.info("Bot Telegram desligado.")

web_app = FastAPI(lifespan=lifespan)

# Rota principal para carregar a interface HTML
@web_app.get("/", response_class=HTMLResponse)
async def get_index():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Arquivo index.html não encontrado!</h1>"

if __name__ == "__main__":
    # O Render define automaticamente a porta através da variável de ambiente PORT
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(web_app, host="0.0.0.0", port=port)