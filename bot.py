"""
╔═══════════════════════════════════════════════════════════════╗
║                   LeGusta Casino Discord Bot                  ║
║                    Sistema Completo v2.0                      ║
║                      Feito Por Aeth×TMZ™                      ║
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
SPOKEAS_ID = 1327679436128129159
GUSTEDS_ID = 487773622291791883

intents = discord.Intents.all()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

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

# ═══════════════════════════════════════════════════════════════
# FUNÇÕES AUXILIARES
# ═══════════════════════════════════════════════════════════════

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

def is_admin():
    """Verifica se é Spokeas ou Gusteds"""
    async def predicate(ctx):
        return ctx.author.id in [SPOKEAS_ID, GUSTEDS_ID]
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

# ═══════════════════════════════════════════════════════════════
# EVENTO: BOT PRONTO
# ═══════════════════════════════════════════════════════════════

@bot.event
async def on_ready():
    print(f"✅ Bot conectado como {bot.user}")
    try:
        synced = await bot.tree.sync()
        print(f"✅ {len(synced)} comando(s) sincronizado(s)")
    except Exception as e:
        print(f"❌ Erro ao sincronizar comandos: {e}")

# ═══════════════════════════════════════════════════════════════
# COMANDO: PING
# ═══════════════════════════════════════════════════════════════

@bot.command(name="ping")
async def ping(ctx):
    """Mostra a latência do bot"""
    latencia = round(bot.latency * 1000)
    embed = embed_cassino("Pong! 🏓", f"`Latência: {latencia}ms`")
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════
# SETUP AUTOMÁTICO DO SERVIDOR
# ═══════════════════════════════════════════════════════════════

async def criar_cargos(guild):
    """Cria todos os cargos do servidor"""
    cargos_config = {
        "🜲 Dono": discord.Color.from_rgb(255, 0, 0),
        "💸 ADMIN 💸": discord.Color.from_rgb(255, 215, 0),
        "⛨ Moderador": discord.Color.from_rgb(0, 128, 255),
        ".☘︎ ݁˖ Gerente Cassino": discord.Color.from_rgb(50, 205, 50),
        "💰 Ajudante Cassino": discord.Color.from_rgb(184, 134, 11),
        "🎲 Gastador": discord.Color.from_rgb(138, 43, 226),
        "⚜ Magnata": discord.Color.from_rgb(218, 165, 32),
        "👤 Membro": discord.Color.from_rgb(128, 128, 128),
        "🚫 Punido": discord.Color.from_rgb(255, 0, 0),
    }
    
    cargos_especiais = {
        "🃏 Spokeas": discord.Color.from_rgb(0, 100, 255),
        "🃁 Gusteds": discord.Color.from_rgb(255, 0, 100),
    }
    
    for nome, cor in {**cargos_config, **cargos_especiais}.items():
        try:
            if not discord.utils.get(guild.roles, name=nome):
                await guild.create_role(name=nome, color=cor)
                print(f"✅ Cargo criado: {nome}")
        except Exception as e:
            print(f"❌ Erro ao criar cargo {nome}: {e}")

async def criar_categorias_canais(guild):
    """Cria categorias e canais"""
    
    # Obter cargos
    membro_role = discord.utils.get(guild.roles, name="👤 Membro")
    punido_role = discord.utils.get(guild.roles, name="🚫 Punido")
    admin_role = discord.utils.get(guild.roles, name="💸 ADMIN 💸")
    mod_role = discord.utils.get(guild.roles, name="⛨ Moderador")
    dono_role = discord.utils.get(guild.roles, name="🜲 Dono")
    
    # Categorias e canais
    estrutura = {
        "📢 INFORMAÇÕES": [
            ("📋-regras", False),
            ("❓-faq", False),
            ("📣-anúncios", False),
            ("🎰-sobre-o-cassino", False),
            ("🆘-ajuda", False),
        ],
        "💬 COMUNIDADE": [
            ("💬-chat-geral", False),
            ("📸-mídia", False),
            ("🤖-comandos-bot", False),
            ("💡-sugestões-bot", False),
        ],
        "🎟️ SUPORTE": [
            ("🎫-criar-ticket", False),
            ("📢-denúncias", False),
            ("🐛-reportar-bugs-minigame", False),
            ("🔧-reportar-bugs-bot", False),
        ],
        "🎉 EVENTOS": [
            ("🎁-sorteios", False),
            ("🎊-eventos", False),
            ("📊-resultados", False),
        ],
        "🔒 STAFF": [
            ("👥-staff-chat", True),
            ("📋-logs-usuários", True),
            ("💬-logs-mensagens", True),
            ("🎫-logs-tickets", True),
            ("⚠️-logs-moderação", True),
            ("📢-logs-denúncias", True),
        ],
        "🗑️ LIXEIRA": [],
    }
    
    for categoria_nome, canais in estrutura.items():
        try:
            # Verificar se categoria existe
            categoria = discord.utils.get(guild.categories, name=categoria_nome)
            if not categoria:
                if "STAFF" in categoria_nome or "LIXEIRA" in categoria_nome:
                    overwrites = {
                        guild.default_role: discord.PermissionOverwrite(view_channel=False),
                        admin_role: discord.PermissionOverwrite(view_channel=True),
                        mod_role: discord.PermissionOverwrite(view_channel=True),
                        dono_role: discord.PermissionOverwrite(view_channel=True),
                    }
                else:
                    overwrites = {}
                
                categoria = await guild.create_category(categoria_nome, overwrites=overwrites)
                print(f"✅ Categoria criada: {categoria_nome}")
            
            # Criar canais
            for nome_canal, privado in canais:
                if not discord.utils.get(guild.channels, name=nome_canal):
                    if privado and "STAFF" in categoria_nome:
                        overwrites = {
                            guild.default_role: discord.PermissionOverwrite(view_channel=False),
                            admin_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            mod_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                            dono_role: discord.PermissionOverwrite(view_channel=True, send_messages=True),
                        }
                    else:
                        overwrites = {
                            punido_role: discord.PermissionOverwrite(send_messages=False),
                        }
                    
                    await guild.create_text_channel(nome_canal, category=categoria, overwrites=overwrites if overwrites else None)
                    print(f"✅ Canal criado: {nome_canal}")
        
        except Exception as e:
            print(f"❌ Erro ao criar categoria {categoria_nome}: {e}")

@bot.command(name="setup")
@is_admin()
async def setup(ctx):
    """Setup automático do servidor"""
    guild = ctx.guild
    
    embed = embed_cassino("Setup em Progresso... ⏳")
    msg = await ctx.send(embed=embed)
    
    try:
        await criar_cargos(guild)
        await criar_categorias_canais(guild)
        
        embed_sucesso = embed_cassino(
            "Setup Completo! ✅",
            "Seu servidor de cassino foi configurado com sucesso!\n\n"
            "✅ Cargos criados\n"
            "✅ Categorias criadas\n"
            "✅ Canais organizados\n"
            "✅ Permissões configuradas",
            Cores.SUCESSO
        )
        await msg.edit(embed=embed_sucesso)
    except Exception as e:
        embed_erro = embed_cassino(f"Erro no Setup! ❌", f"`{str(e)}`", Cores.ERRO)
        await msg.edit(embed=embed_erro)

@bot.command(name="resetup")
@is_admin()
async def resetup(ctx):
    """Reseta completamente o servidor"""
    guild = ctx.guild
    
    # Confirmação
    embed = embed_cassino("⚠️ Você tem certeza?", "Este comando vai **deletar** todas as categorias, canais e recriá-los!")
    msg = await ctx.send(embed=embed)
    
    try:
        # Deletar canais e categorias existentes
        for channel in guild.channels:
            if channel.name not in ["general"]:
                await channel.delete()
        
        for category in guild.categories:
            await category.delete()
        
        # Recriar
        await criar_categorias_canais(guild)
        
        embed_sucesso = embed_cassino("Reset Completo! ✅", "Servidor resetado com sucesso!", Cores.SUCESSO)
        await msg.edit(embed=embed_sucesso)
    except Exception as e:
        embed_erro = embed_cassino(f"Erro! ❌", f"`{str(e)}`", Cores.ERRO)
        await msg.edit(embed=embed_erro)

# ═══════════════════════════════════════════════════════════════
# COMANDO: RODAR BOT
# ═══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("❌ Erro: Token não encontrado!")
