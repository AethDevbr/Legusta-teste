"""
╔═══════════════════════════════════════════════════════════════╗
║                   LeGusta Casino Discord Bot                  ║
║                    Sistema Completo v1.0                      ║
║                      Made with ❤️ by Bot                      ║
╚═══════════════════════════════════════════════════════════════╝
"""

import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import json
from datetime import datetime, timedelta
import random
from typing import Optional

# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÕES INICIAIS
# ═══════════════════════════════════════════════════════════════

TOKEN = os.getenv("DISCORD_TOKEN")
SPOKEAS_ID = 1327679436128129159  # ID do Spokeas
GUSTEDS_ID = 487773622291791883   # ID do Gusteds

# Intents
intents = discord.Intents.all()
intents.message_content = True

# Bot
bot = commands.Bot(command_prefix="!", intents=intents)

# ═══════════════════════════════════════════════════════════════
# ESTRUTURA DE DADOS
# ═══════════════════════════════════════════════════════════════

# Arquivos JSON para armazenar dados
DATA_FILE = "casino_data.json"
DENUNCIAS_FILE = "denuncias.json"
BUGS_FILE = "bugs.json"
STAFFS_FILE = "staffs.json"
INVITE_BLOCKS = "invite_blocks.json"

def load_data(filename, default=None):
    """Carrega dados de um arquivo JSON"""
    try:
        if os.path.exists(filename):
            with open(filename, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return default or {}

def save_data(filename, data):
    """Salva dados em um arquivo JSON"""
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"Erro ao salvar {filename}: {e}")

# ═══════════════════════════════════════════════════════════════
# CORES E EMOJIS
# ═══════════════════════════════════════════════════════════════

class Cores:
    SUCESSO = discord.Color.from_rgb(0, 255, 127)
    ERRO = discord.Color.from_rgb(255, 50, 50)
    INFO = discord.Color.from_rgb(0, 153, 204)
    CASSINO = discord.Color.from_rgb(255, 215, 0)
    DENUNCIA = discord.Color.from_rgb(138, 43, 226)
    TICKET = discord.Color.from_rgb(72, 209, 204)
    BAN = discord.Color.from_rgb(220, 20, 60)
    LOGS = discord.Color.from_rgb(47, 49, 54)

class Emojis:
    ADMIN = "💸"
    MODS = "⛨"
    GERENTE = ".☘︎ ݁˖"
    AJUDANTE = "💰"
    GASTADOR = "🎲"
    MAGNATA = "⚜"
    MEMBRO = "👤"
    PUNIDO = "🚫"
    DONO = "🜲"
    GUSTEDS = "🃁"
    SPOKEAS = "🃏"

# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

def is_admin_permissions():
    """Verifica se é Spokeas ou Gusteds"""
    async def predicate(ctx):
        return ctx.author.id in [SPOKEAS_ID, GUSTEDS_ID]
    return commands.check(predicate)

def can_manage_gusteds_spokeas():
    """Verifica se pode gerenciar Gusteds e Spokeas"""
    async def predicate(ctx):
        return ctx.author.id in [SPOKEAS_ID, GUSTEDS_ID, 487773622291791883]
    return commands.check(predicate)

def embed_cassino(titulo, descricao="", cor=None):
    """Cria um embed estilo cassino"""
    embed = discord.Embed(
        title=f"🎰 {titulo}",
        description=descricao,
        color=cor or Cores.CASSINO,
        timestamp=datetime.now()
    )
    embed.set_footer(text="LeGusta Casino", icon_url="https://i.imgur.com/1NA8dQR.png")
    return embed

async def criar_logs_embeds(titulo, cor, usuario=None, staff=None, motivo=None, duracao=None):
    """Cria embeds padronizados para logs"""
    embed = discord.Embed(
        title=titulo,
        color=cor,
        timestamp=datetime.now()
    )
    
    if usuario:
        embed.add_field(name="👤 `Usuário`", value=f"`{usuario.mention}`", inline=True)
        embed.add_field(name="🆔 `ID`", value=f"`{usuario.id}`", inline=True)
        embed.set_thumbnail(url=usuario.avatar.url if usuario.avatar else None)
    
    if staff:
        embed.add_field(name="👨‍⚖️ `Staff Responsável`", value=f"`{staff.mention}`", inline=True)
    
    if motivo:
        embed.add_field(name="📝 `Motivo`", value=f"`{motivo}`", inline=False)
    
    if duracao:
        embed.add_field(name="⏱️ `Duração`", value=f"`{duracao}`", inline=True)
    
    embed.set_footer(text="LeGusta Casino", icon_url="https://i.imgur.com/1NA8dQR.png")
    return embed

# ═══════════════════════════════════════════════════════════════
# SETUP AUTOMÁTICO DO SERVIDOR
# ═══════════════════════════════════════════════════════════════

async def setup_server(guild):
    """Configura completamente o servidor"""
    
    print(f"[SETUP] Iniciando setup do servidor: {guild.name}")
    
    # 1️⃣ CRIAR CARGOS
    print("[SETUP] Criando cargos...")
    
    cargos = {
        "Dono": {"emoji": "🜲", "color": discord.Color.from_rgb(255, 0, 0), "permissions": discord.Permissions.all()},
        "💸ADMIN💸": {"emoji": "💸", "color": discord.Color.from_rgb(255, 215, 0), "permissions": discord.Permissions(administrator=True)},
        "⛨ Moderador": {"emoji": "⛨", "color": discord.Color.from_rgb(0, 128, 255), "permissions": discord.Permissions(kick_members=True, ban_members=True, manage_messages=True)},
        ".☘︎ ݁˖Gerente Cassino": {"emoji": ".☘︎ ݁˖", "color": discord.Color.from_rgb(50, 205, 50), "permissions": discord.Permissions(manage_channels=True, manage_messages=True)},
        "💰 Ajudante Cassino": {"emoji": "💰", "color": discord.Color.from_rgb(184, 134, 11), "permissions": discord.Permissions(manage_messages=True)},
        "🎲 Gastador": {"emoji": "🎲", "color": discord.Color.from_rgb(138, 43, 226), "permissions": discord.Permissions()},
        "⚜ Magnata": {"emoji": "⚜", "color": discord.Color.from_rgb(218, 165, 32), "permissions": discord.Permissions()},
        "👤 Membro": {"emoji": "👤", "color": discord.Color.from_rgb(128, 128, 128), "permissions": discord.Permissions()},
        "🚫 Punido": {"emoji": "🚫", "color": discord.Color.from_rgb(255, 0, 0), "permissions": discord.Permissions()},
    }
    
    # Cargos especiais (só podem ser dados por Spokeas/Gusteds)
    cargos_especiais = {
        "🃏 Spokeas": {"emoji": "🃏", "color": discord.Color.from_rgb(0, 100, 255), "permissions": discord.Permissions(administrator=True)},
        "🃁 Gusteds": {"emoji": "🃁", "color": discord.Color.from_rgb(255, 0, 100), "permissions": discord.Permissions(administrator=True)},
    }
    
    for nome, config in {**cargos, **cargos_especiais}.items():
        try:
            existing_role = discord.utils.get(guild.roles, name=nome)
            if not existing_role:
                role = await guild.create_role(
                    name=nome,
                    color=config["color"],
                    permissions=config["permissions"]
                )
                print(f"✅ Cargo criado: {nome}")
            else:
                print(f"⚠️ Cargo já existe: {nome}")
        except Exception as e:
            print(f"❌ Erro ao criar cargo {nome}: {e}")
    
    # 2️⃣ CRIAR CATEGORIAS E CANAIS
    print("[SETUP] Criando categorias e canais...")
    
    # Obter cargos
    admin_role = discord.utils.get(guild.roles, name="💸ADMIN💸")
    mod_role = discord.utils.get(guild.roles, name="⛨ Moderador")
    membro_role = discord.utils.get(guild.roles, name="👤 Membro")
    punido_role = discord.utils.get(guild.roles, name="🚫 Punido")
    dono_role = discord.utils.get(guild.roles, name="🜲 Dono")
    
    # Permissões para canais
    permissoes_staff_only = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
        admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
        dono_role: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
    }
    
    permissoes_logs = {
        guild.default_role: discord.PermissionOverwrite(view_channel=False),
    }
    
    permissoes_publica = {
        guild.default_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
        punido_role: discord.PermissionOverwrite(send_messages=False),
    }
    
    # Estrutura de canais
    estrutura = {
        "📢 INFORMAÇÕES": {
            "canais": ["📋 regras", "❓ faq", "📣 anúncios", "🎰 sobre-o-cassino", "🆘 ajuda"],
            "privada": False
        },
        "💬 COMUNIDADE": {
            "canais": ["💬 chat-geral", "📸 mídia", "🤖 comandos-bot", "💡 su