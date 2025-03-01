from fastapi import FastAPI, HTTPException
import asyncio
from telethon import TelegramClient, events, Button
import re
import requests
from typing import Dict

# Dados da API do Telegram
API_ID = 20964711  # Pegue no my.telegram.org
API_HASH = "f9160eb582065e9d0e5a852ff80cd8e9"  # Pegue no my.telegram.org
PHONE_NUMBER = "+5541997271635"  # Seu número do Telegram
BOT_USERNAME = "@EmonNullbot"  # Nome de usuário do bot

# Lista de palavras proibidas
BLOCKED_WORDS = ["palavra1", "palavra2", "palavra3", "10822784912", "06636336994"]  # Adicione palavras e informações sensíveis para bloquear

app = FastAPI()

# Criando o cliente Telethon
client = TelegramClient("session_name", API_ID, API_HASH)

TELEGRAPH_API_URL = "https://api.telegra.ph/createPage"

# Dicionário para armazenar sessões de usuários
user_sessions: Dict[str, str] = {}  # {session_id: last_message_id}

@app.on_event("startup")
async def startup():
    await client.start(PHONE_NUMBER)
    print("Telegram Client iniciado!")

@app.on_event("shutdown")
async def shutdown():
    await client.disconnect()

def process_message(message):
    """ Remove informações indesejadas da mensagem do bot e captura botões. """
    text = message.message or ""
    text = re.sub(r"👤 USUÁRIO: .*", "", text)
    text = re.sub(r"🤖 BOT: @EmonNullbot", "", text)
    text = re.sub(r"Nasci", "", text)  # Remove o nome de usuário "Nasci"
    text = re.sub(r"Por Ｇｏｎｚａｌｅｓ\(bot\) • .*", "", text)  # Remove a menção ao bot com qualquer data
    text = re.sub(r"👤 USUÁRIO: \[.*?\]\(tg://user\?id=.*?\)", "", text)  # Remove a identificação do usuário
    text = text.strip()
    
    # Captura botões e verifica links do Telegraph
    buttons = []
    if message.buttons:
        for row in message.buttons:
            for button in row:
                if isinstance(button, Button.Url):
                    new_url = modify_telegraph_links(button.url)
                    buttons.append({"text": button.text, "url": new_url})
                elif isinstance(button, Button.Text):
                    buttons.append({"text": button.text, "data": button.data})
    
    return {"text": text, "buttons": buttons}

def modify_telegraph_links(url):
    """ Se for um link do Telegraph, modifica o conteúdo e retorna um novo link. """
    if "telegra.ph" in url:
        try:
            return clean_and_reupload_telegraph(url)
        except Exception as e:
            print(f"Erro ao modificar Telegraph link: {e}")
    return url

def clean_and_reupload_telegraph(url):
    """ Faz o download, limpa e reenvia o conteúdo para o Telegraph. """
    response = requests.get(url)
    if response.status_code != 200:
        raise Exception("Erro ao acessar a página do Telegraph")
    
    content = response.text
    content = re.sub(r"Por Ｇｏｎｚａｌｅｓ\(bot\) • .*", "", content)
    content = re.sub(r"👤 USUÁRIO: \[.*?\]\(tg://user\?id=.*?\)", "", content)
    content = re.sub(r"🤖 BOT: @EmonNullbot", "", content)
    
    # Reenvia para Telegraph
    new_response = requests.post(TELEGRAPH_API_URL, json={
        "access_token": "your_telegraph_access_token",
        "title": "Resultado Modificado",
        "author_name": "Bot",
        "content": [{"tag": "p", "children": [content]}]
    })
    
    if new_response.status_code != 200:
        raise Exception("Erro ao publicar no Telegraph")
    
    return new_response.json().get("result").get("url")

@app.post("/send")
async def send_message(data: dict):
    session_id = data.get("session_id")
    user_message = data.get("message")
    
    if not session_id or not user_message:
        raise HTTPException(status_code=400, detail="Sessão ou mensagem inválida")
    
    if any(word in user_message.lower() for word in BLOCKED_WORDS):
        raise HTTPException(status_code=400, detail="Mensagem contém informações proibidas.")
    
    try:
        # Envia a mensagem para o bot
        sent_message = await client.send_message(BOT_USERNAME, user_message)
        user_sessions[session_id] = sent_message.id  # Armazena o ID da mensagem
        
        return {"status": "Mensagem enviada com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/get_response")
async def get_response(data: dict):
    session_id = data.get("session_id")
    
    if not session_id or session_id not in user_sessions:
        raise HTTPException(status_code=400, detail="Sessão inválida ou inexistente")
    
    try:
        message_id = user_sessions[session_id]
        response = await client.get_messages(BOT_USERNAME, min_id=message_id, limit=1)
        
        if response:
            bot_reply = process_message(response[0])
            return bot_reply
        else:
            return {"text": "Sem resposta do bot.", "buttons": []}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/click_button")
async def click_button(data: dict):
    session_id = data.get("session_id")
    button_data = data.get("data")
    
    if not session_id or not button_data:
        raise HTTPException(status_code=400, detail="Sessão ou botão inválido")
    
    try:
        sent_message = await client.send_message(BOT_USERNAME, button_data)
        user_sessions[session_id] = sent_message.id  # Atualiza a sessão com o novo ID
        
        return {"status": "Botão clicado com sucesso."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
