# bot.py - LeGusta Casino Bot
# Versão completa com todos os sistemas
# Python 3.11.9 | discord.py 2.x

import os
import asyncio
import random
import string
import datetime
import json
from typing import Optional, Dict, List
from datetime import timedelta

import discord
from discord import app_commands, ui
from discord.ext import commands, tasks
from discord.ui import View, Button, Select

# ═══════════════════════════════════════════════════════════════
# CONFIGURAÇÕES E CONSTANTES
# ═══════════════════════════════════════════════════════════════

TOKEN = os.getenv("TOKEN")
if not TOKEN:
    raise ValueError("Token não encontrado! Defina a variável de ambiente TOKEN.")

# IDs dos Donos (Proteção máxima)
OWNER_IDS = [1327679436128129159, 487773622291791883]  # Spokeas e Gusteds
GUSTEDS_ID = 487773622291791883
SPOKEAS_ID = 1327679436128129159

# IDs de cargos protegidos (não podem ser atribuídos por ninguém além dos donos)
PROTECTED_ROLE_NAMES = ["🃏 Gusteds", "🃁 Spokeas"]

# Configurações de canais e categorias
GUILD_CONFIGS = {}  # Cache de configurações por servidor

# Banco de dados simples (em memória com persistência opcional)
class Database:
    def __init__(self):
        self.bug_reports = {}  # {user_id: count}
        self.suggestions = {}  # {message_id: data}
        self.tickets = {}  # {channel_id: data}
        self.reports = {}  # {report_id: data}
        self.staff_stats = {}  # {user_id: {tickets: 0, bugs: 0}}
        self.blocked_channels = set()  # Canais bloqueados para invites
        self.user_data = {}  # Dados de usuários
        
    def save(self):
        # Persistência simples em JSON
        data = {
            'bug_reports': self.bug_reports,
            'suggestions': {k: v for k, v in self.suggestions.items()},
            'staff_stats': self.staff_stats,
            'blocked_channels': list(self.blocked_channels),
            'user_data': self.user_data
        }
        try:
            with open('database.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except:
            pass
    
    def load(self):
        try:
            with open('database.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.bug_reports = data.get('bug_reports', {})
                self.staff_stats = data.get('staff_stats', {})
                self.blocked_channels = set(data.get('blocked_channels', []))
                self.user_data = data.get('user_data', {})
        except:
            pass

db = Database()
db.load()

# ═══════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════

def generate_ticket_id():
    """Gera ID único para tickets"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

def generate_report_id():
    """Gera ID único para denúncias"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_timestamp():
    """Retorna timestamp formatado"""
    now = datetime.datetime.now()
    return f"<t:{int(now.timestamp())}:F>"

def create_embed(title: str, description: str = "", color: discord.Color = discord.Color.gold(), 
                 author: discord.Member = None, thumbnail: str = None, image: str = None):
    """Cria embed estilo cassino"""
    embed = discord.Embed(
        title=f"🎰 {title}",
        description=description,
        color=color,
        timestamp=datetime.datetime.now()
    )
    
    if author:
        embed.set_author(name=str(author), icon_url=author.display_avatar.url)
    if thumbnail:
        embed.set_thumbnail(url=thumbnail)
    if image:
        embed.set_image(url=image)
        
    embed.set_footer(text="LeGusta Casino © 2024", icon_url="https://i.imgur.com/1NA8dQR.png")
    return embed

def is_owner(user_id: int) -> bool:
    """Verifica se é dono"""
    return user_id in OWNER_IDS

def is_protected_role(role_name: str) -> bool:
    """Verifica se é cargo protegido"""
    return role_name in PROTECTED_ROLE_NAMES

# ═══════════════════════════════════════════════════════════════
# BOT E EVENTOS
# ═══════════════════════════════════════════════════════════════

intents = discord.Intents.all()
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

@bot.event
async def on_ready():
    """Evento quando o bot inicia"""
    print(f"🎰 LeGusta Casino Bot Online!")
    print(f"Bot: {bot.user.name}")
    print(f"ID: {bot.user.id}")
    print(f"Python: 3.11.9")
    print(f"Discord.py: {discord.__version__}")
    
    # Sincroniza comandos slash
    try:
        synced = await bot.tree.sync()
        print(f"Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"Erro ao sincronizar: {e}")
    
    # Inicia tarefas agendadas
    check_old_tickets.start()
    process_suggestions.start()
    reset_monthly_leaderboard.start()
    db.save()

@bot.event
async def on_guild_join(guild):
    """Quando entra em um servidor"""
    print(f"Entrou no servidor: {guild.name}")

@bot.event
async def on_member_join(member):
    """Mensagem de boas-vindas"""
    guild = member.guild
    
    # Canal de boas-vindas (chat-geral)
    welcome_channel = discord.utils.get(guild.channels, name="chat-geral")
    if welcome_channel:
        embed = create_embed(
            "NOVO JOGADOR NA ÁREA!",
            f"🎉 Bem-vindo ao **LeGusta Casino**, {member.mention}!\n\n"
            f"🃏 Leia as regras em <#regras>\n"
            f"💰 Dúvidas? Use o canal <#ajuda>\n"
            f"🎰 Bom jogo e boa sorte! 🍀",
            discord.Color.green(),
            member
        )
        await welcome_channel.send(embed=embed)
    
    # Atribui cargo Membro automaticamente
    membro_role = discord.utils.get(guild.roles, name="👤 Membro")
    if membro_role:
        try:
            await member.add_roles(membro_role)
        except:
            pass
    
    # Log de entrada
    await log_user_event(guild, "Entrada", member, "Novo membro entrou no servidor")

@bot.event
async def on_member_remove(member):
    """Quando membro sai"""
    await log_user_event(member.guild, "Saída", member, "Membro saiu do servidor")

@bot.event
async def on_member_update(before, after):
    """Log de alterações em membros"""
    if before.display_name != after.display_name:
        await log_user_event(after.guild, "Nome Alterado", after, 
                           f"De: `{before.display_name}`\nPara: `{after.display_name}`")
    
    if before.display_avatar.url != after.display_avatar.url:
        await log_user_event(after.guild, "Avatar Alterado", after, 
                           "Usuário alterou a foto de perfil")

@bot.event
async def on_message_delete(message):
    """Log de mensagens deletadas"""
    if message.author.bot:
        return
    
    await log_message_event(message.guild, "Mensagem Deletada", message)

@bot.event
async def on_message_edit(before, after):
    """Log de mensagens editadas"""
    if before.author.bot or before.content == after.content:
        return
    
    await log_message_event(before.guild, "Mensagem Editada", before, after)

@bot.event
async def on_message(message):
    """Processamento de mensagens"""
    if message.author.bot:
        return
    
    # Sistema Anti-Spam
    await check_spam(message)
    
    # Bloqueador de Invites
    if await check_invite_block(message):
        return
    
    # Processa comandos
    await bot.process_commands(message)
    
    # Sistema de Sugestões
    if message.channel.name == "sugestões-pro-bot":
        await process_suggestion_message(message)
    
    # Sistema de Reporte de Bugs
    if message.channel.name == "reportar-bugs-minigames":
        await process_bug_report(message, "minigame")
    elif message.channel.name == "reportar-bugs-bot":
        await process_bug_report(message, "bot")

async def check_spam(message):
    """Verifica mensagens suspeitas de spam"""
    content = message.content
    
    # Spam: mensagens muito longas (500+ caracteres)
    if len(content) >= 500:
        # Verifica se tem muitas repetições
        if len(set(content)) < len(content) * 0.3:  # Muitos caracteres repetidos
            await handle_suspected_spam(message)
            return
    
    # Spam: mensagens com 100+ caracteres e muitas quebras de linha
    if len(content) >= 100 and content.count('\n') > 10:
        await handle_suspected_spam(message)

async def handle_suspected_spam(message):
    """Lida com mensagem suspeita de spam"""
    embed = create_embed(
        "⚠️ SUSPEITA DE SPAM DETECTADA",
        f"**`Autor:`** {message.author.mention}\n"
        f"**`Canal:`** {message.channel.mention}\n"
        f"**`Tamanho:`** {len(message.content)} caracteres\n"
        f"**`Horário:`** {get_timestamp()}\n\n"
        f"**`Conteúdo:`**\n```\n{message.content[:500]}...\n```",
        discord.Color.orange()
    )
    
    # Envia para logs de mensagens
    log_channel = discord.utils.get(message.guild.channels, name="logs-mensagens")
    if log_channel:
        view = SpamActionView(message.author)
        await log_channel.send(embed=embed, view=view)

class SpamActionView(View):
    def __init__(self, target):
        super().__init__(timeout=None)
        self.target = target
    
    @discord.ui.button(label="🔇 Mutar Usuário", style=discord.ButtonStyle.danger)
    async def mute_button(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("Apenas donos podem usar!", ephemeral=True)
            return
        
        # Aplica timeout de 1 hora
        try:
            await self.target.timeout(timedelta(hours=1), reason="Spam detectado")
            await interaction.response.send_message(f"✅ {self.target.mention} mutado por 1 hora!", ephemeral=True)
        except:
            await interaction.response.send_message("Erro ao aplicar mute!", ephemeral=True)
    
    @discord.ui.button(label="❌ Ignorar", style=discord.ButtonStyle.secondary)
    async def ignore_button(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("Apenas donos podem usar!", ephemeral=True)
            return
        await interaction.response.send_message("Ignorado.", ephemeral=True)
        self.stop()

async def check_invite_block(message):
    """Verifica e bloqueia invites em canais bloqueados"""
    if "discord.gg/" in message.content.lower() or "discord.com/invite/" in message.content.lower():
        if message.channel.id in db.blocked_channels:
            try:
                await message.delete()
                embed = create_embed(
                    "⛔ CONVITE BLOQUEADO",
                    f"{message.author.mention}, convites Discord não são permitidos neste canal!",
                    discord.Color.red()
                )
                await message.channel.send(embed=embed, delete_after=5)
                return True
            except:
                pass
    return False

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE LOGS
# ═══════════════════════════════════════════════════════════════

async def log_user_event(guild, event_type, member, details):
    """Log de eventos de usuário"""
    channel = discord.utils.get(guild.channels, name="logs-de-usuário")
    if not channel:
        return
    
    account_age = (datetime.datetime.now() - member.created_at).days
    
    embed = create_embed(
        f"👤 {event_type}",
        f"**`Usuário:`** {member.mention}\n"
        f"**`ID:`** `{member.id}`\n"
        f"**`Tag:`** `{member}`\n"
        f"**`Conta Criada:`** <t:{int(member.created_at.timestamp())}:R>\n"
        f"**`Idade da Conta:`** `{account_age} dias`\n"
        f"**`Detalhes:`** {details}",
        discord.Color.blue(),
        member
    )
    
    # Apenas donos podem ver estes logs
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True)
    }
    
    for owner_id in OWNER_IDS:
        owner = guild.get_member(owner_id)
        if owner:
            overwrites[owner] = discord.PermissionOverwrite(read_messages=True)
    
    await channel.send(embed=embed)

async def log_message_event(guild, event_type, message, after=None):
    """Log de eventos de mensagem"""
    channel = discord.utils.get(guild.channels, name="logs-mensagens")
    if not channel:
        return
    
    content = message.content[:1000] if message.content else "*Sem conteúdo*"
    
    desc = (f"**`Autor:`** {message.author.mention}\n"
            f"**`Canal:`** {message.channel.mention}\n"
            f"**`Mensagem:`** {message.jump_url if message.id else 'N/A'}\n")
    
    if after:
        desc += f"**`Antes:`**\n```\n{content}\n```\n"
        desc += f"**`Depois:`**\n```\n{after.content[:1000]}\n```"
    else:
        desc += f"**`Conteúdo:`**\n```\n{content}\n```"
    
    embed = create_embed(
        f"📝 {event_type}",
        desc,
        discord.Color.orange(),
        message.author
    )
    
    await channel.send(embed=embed)

async def log_ticket_event(guild, action, ticket_id, user, staff=None):
    """Log de eventos de ticket"""
    channel = discord.utils.get(guild.channels, name="logs-de-tickets")
    if not channel:
        return
    
    desc = (f"**`Ação:`** {action}\n"
            f"**`Ticket ID:`** `{ticket_id}`\n"
            f"**`Usuário:`** {user.mention}\n")
    
    if staff:
        desc += f"**`Staff:`** {staff.mention}"
    
    embed = create_embed(
        "🎫 LOG DE TICKET",
        desc,
        discord.Color.purple()
    )
    
    await channel.send(embed=embed)

async def log_punishment(guild, punishment_type, target, moderator, reason):
    """Log de punições"""
    channel = discord.utils.get(guild.channels, name="logs-de-punições")
    if not channel:
        return
    
    account_age = (datetime.datetime.now() - target.created_at).days
    
    colors = {
        "Ban": discord.Color.red(),
        "Kick": discord.Color.orange(),
        "Warn": discord.Color.yellow(),
        "Mute": discord.Color.dark_orange()
    }
    
    embed = create_embed(
        f"🔨 {punishment_type}",
        f"**`Usuário:`** {target.mention}\n"
        f"**`ID:`** `{target.id}`\n"
        f"**`Conta Criada:`** <t:{int(target.created_at.timestamp())}:F>\n"
        f"**`Idade da Conta:`** `{account_age} dias`\n"
        f"**`Moderador:`** {moderator.mention}\n"
        f"**`Motivo:`** `{reason}`\n"
        f"**`Horário:`** {get_timestamp()}",
        colors.get(punishment_type, discord.Color.red()),
        target
    )
    
    await channel.send(embed=embed)

async def log_report(guild, report_id, reporter, reported, reason, status, anonymous=True):
    """Log de denúncias (visível apenas para donos)"""
    channel = discord.utils.get(guild.channels, name="logs-de-denúncias")
    if not channel:
        return
    
    reporter_name = "||Anônimo||" if anonymous else reporter.mention
    
    embed = create_embed(
        "🚨 LOG DE DENÚNCIA",
        f"**`ID da Denúncia:`** `{report_id}`\n"
        f"**`Denunciado:`** {reported.mention}\n"
        f"**`ID do Denunciado:`** `{reported.id}`\n"
        f"**`Denunciado por:`** {reporter_name}\n"
        f"**`Motivo:`** `{reason}`\n"
        f"**`Status:`** `{status}`\n"
        f"**`Horário:`** {get_timestamp()}",
        discord.Color.dark_red(),
        reported
    )
    
    await channel.send(embed=embed)

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE TICKET AVANÇADO
# ═══════════════════════════════════════════════════════════════

class TicketView(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.select(
        placeholder="🎫 Selecione o tipo de ticket...",
        options=[
            discord.SelectOption(label="Dúvidas", emoji="❓", description="Tire suas dúvidas sobre o servidor"),
            discord.SelectOption(label="Sobre o Cassino", emoji="🎰", description="Questões sobre o cassino"),
            discord.SelectOption(label="Denúncias", emoji="🚨", description="Denunciar comportamento inadequado"),
            discord.SelectOption(label="Falar com Gerência", emoji="👑", description="Apenas para assuntos com gerentes")
        ],
        custom_id="ticket_select"
    )
    async def ticket_select(self, interaction: discord.Interaction, select: Select):
        ticket_type = select.values[0]
        await create_ticket(interaction, ticket_type)

class TicketPanel(View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label="🎫 Abrir Ticket", style=discord.ButtonStyle.primary, custom_id="open_ticket")
    async def open_ticket(self, interaction: discord.Interaction, button: Button):
        # Mostra dropdown para selecionar tipo
        view = TicketView()
        await interaction.response.send_message("Selecione o tipo de ticket:", view=view, ephemeral=True)

async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    """Cria um canal de ticket"""
    guild = interaction.guild
    user = interaction.user
    
    # Verifica se já tem ticket aberto
    existing = discord.utils.get(guild.channels, name=f"ticket-{user.name.lower()}")
    if existing:
        await interaction.response.send_message(
            "Você já tem um ticket aberto!", ephemeral=True
        )
        return
    
    # Busca categoria
    category = discord.utils.get(guild.categories, name="🎟️ SUPORTE")
    if not category:
        category = await guild.create_category("🎟️ SUPORTE")
    
    ticket_id = generate_ticket_id()
    
    # Busca cargos staff
    staff_roles = []
    for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador", ".☘︎ ݁˖Gerente Cassino", "💰 Ajudante Cassino"]:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            staff_roles.append(role)
    
    # Permissões do canal
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
    }
    
    for role in staff_roles:
        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    
    # Cria canal
    channel = await guild.create_text_channel(
        f"ticket-{user.name}",
        category=category,
        overwrites=overwrites,
        topic=f"Ticket {ticket_id} | {ticket_type} | {user.id}"
    )
    
    # Salva dados do ticket
    db.tickets[channel.id] = {
        "id": ticket_id,
        "user_id": user.id,
        "type": ticket_type,
        "created_at": datetime.datetime.now().isoformat(),
        "staff_id": None,
        "status": "Aberto"
    }
    
    # Embed do ticket
    embed = create_embed(
        f"🎫 TICKET #{ticket_id}",
        f"**`Tipo:`** {ticket_type}\n"
        f"**`Usuário:`** {user.mention}\n"
        f"**`ID do Ticket:`** `{ticket_id}`\n"
        f"**`Staff Responsável:`** `Nenhum`\n"
        f"**`Aberto em:`** {get_timestamp()}\n\n"
        f"Aguarde, um staff será atendê-lo em breve!\n\n"
        f"||{' '.join([r.mention for r in staff_roles])}||",
        discord.Color.gold()
    )
    
    view = TicketControlView(ticket_id, user.id)
    
    await channel.send(f"{user.mention}", embed=embed, view=view)
    await interaction.response.send_message(
        f"✅ Ticket criado: {channel.mention}", ephemeral=True
    )
    
    # Log
    await log_ticket_event(guild, "Ticket Criado", ticket_id, user)

class TicketControlView(View):
    def __init__(self, ticket_id, user_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user_id = user_id
    
    @discord.ui.button(label="🔒 Assumir Ticket", style=discord.ButtonStyle.success, custom_id="claim_ticket")
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        # Verifica se é staff
        staff_roles = ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador", ".☘︎ ݁˖Gerente Cassino", "💰 Ajudante Cassino"]
        is_staff = any(discord.utils.get(interaction.user.roles, name=r) for r in staff_roles)
        
        if not is_staff:
            await interaction.response.send_message("Apenas staff!", ephemeral=True)
            return
        
        # Atualiza embed
        channel = interaction.channel
        async for message in channel.history(limit=10):
            if message.embeds and "TICKET #" in message.embeds[0].title:
                embed = message.embeds[0]
                new_desc = embed.description.replace("**`Staff Responsável:`** `Nenhum`", 
                                                   f"**`Staff Responsável:`** {interaction.user.mention}")
                new_embed = discord.Embed.from_dict(embed.to_dict())
                new_embed.description = new_desc
                await message.edit(embed=new_embed)
                break
        
        # Atualiza dados
        if channel.id in db.tickets:
            db.tickets[channel.id]["staff_id"] = interaction.user.id
        
        # Atualiza estatísticas
        if interaction.user.id not in db.staff_stats:
            db.staff_stats[interaction.user.id] = {"tickets": 0, "bugs": 0}
        db.staff_stats[interaction.user.id]["tickets"] += 1
        
        await interaction.response.send_message(
            f"✅ Ticket assumido por {interaction.user.mention}", ephemeral=True
        )
        
        # Desabilita botão
        self.claim_ticket.disabled = True
        await interaction.message.edit(view=self)
    
    @discord.ui.button(label="🔒 Fechar Ticket", style=discord.ButtonStyle.danger, custom_id="close_ticket")
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        view = ConfirmCloseView(self.ticket_id, self.user_id)
        await interaction.response.send_message(
            "Deseja realmente fechar este ticket?", view=view, ephemeral=True
        )

class ConfirmCloseView(View):
    def __init__(self, ticket_id, user_id):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.user_id = user_id
    
    @discord.ui.button(label="✅ Sim", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel
        
        # Move para lixeira em vez de deletar
        trash_category = discord.utils.get(interaction.guild.categories, name="🗑️ LIXEIRA")
        if not trash_category:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            # Donos têm acesso
            for owner_id in OWNER_IDS:
                owner = interaction.guild.get_member(owner_id)
                if owner:
                    overwrites[owner] = discord.PermissionOverwrite(read_messages=True)
            
            # Staff pode ver
            for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True)
            
            trash_category = await interaction.guild.create_category("🗑️ LIXEIRA", overwrites=overwrites)
        
        # Renomeia e move
        new_name = f"arquivado-{channel.name}"
        await channel.edit(name=new_name, category=trash_category)
        
        # Remove permissões do usuário
        user = interaction.guild.get_member(self.user_id)
        if user:
            await channel.set_permissions(user, overwrite=None)
        
        # Log
        await log_ticket_event(
            interaction.guild, "Ticket Fechado", self.ticket_id, user, interaction.user
        )
        
        await interaction.response.send_message("🔒 Ticket fechado e arquivado!")
        self.stop()
    
    @discord.ui.button(label="❌ Não", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("Cancelado.", ephemeral=True)
        self.stop()

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE DENÚNCIAS ANÔNIMAS
# ═══════════════════════════════════════════════════════════════

class ReportModal(ui.Modal, title="🚨 Nova Denúncia"):
    motivo = ui.TextInput(
        label="Motivo da denúncia",
        style=discord.TextStyle.paragraph,
        placeholder="Descreva detalhadamente o ocorrido...",
        required=True,
        max_length=1000
    )
    
    provas = ui.TextInput(
        label="Provas (opcional)",
        style=discord.TextStyle.paragraph,
        placeholder="Links de imagens, vídeos, etc...",
        required=False,
        max_length=500
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Obtém o usuário denunciado do contexto
        # Precisamos passar isso de outra forma, vamos usar um view intermediário
        pass

class ReportView(View):
    def __init__(self, reported_user):
        super().__init__(timeout=None)
        self.reported_user = reported_user
    
    @discord.ui.button(label="🚨 Fazer Denúncia", style=discord.ButtonStyle.danger)
    async def report_button(self, interaction: discord.Interaction, button: Button):
        modal = ReportModal()
        modal.reported_user = self.reported_user
        modal.interaction = interaction
        await interaction.response.send_modal(modal)

class ReportSystem:
    @staticmethod
    async def create_report(interaction: discord.Interaction, reported: discord.Member, motivo: str):
        guild = interaction.guild
        report_id = generate_report_id()
        
        # Cria tópico privado
        category = discord.utils.get(guild.categories, name="🔒 STAFF")
        if not category:
            category = await guild.create_category("🔒 STAFF")
        
        # Apenas donos podem ver
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        for owner_id in OWNER_IDS:
            owner = guild.get_member(owner_id)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(read_messages=True)
        
        channel = await guild.create_text_channel(
            f"denuncia-{report_id}",
            category=category,
            overwrites=overwrites
        )
        
        # Salva dados
        db.reports[report_id] = {
            "channel_id": channel.id,
            "reporter_id": interaction.user.id,
            "reported_id": reported.id,
            "motivo": motivo,
            "status": "Não resolvida",
            "created_at": datetime.datetime.now().isoformat()
        }
        
        # Embed da denúncia
        account_age = (datetime.datetime.now() - reported.created_at).days
        
        embed = create_embed(
            f"🚨 DENÚNCIA #{report_id}",
            f"**`Denunciado:`** {reported.mention}\n"
            f"**`ID do Denunciado:`** `{reported.id}`\n"
            f"**`Denunciado por:`** ||Anônimo||\n"
            f"**`Motivo:`** `{motivo}`\n"
            f"**`Conta Criada:`** <t:{int(reported.created_at.timestamp())}:F>\n"
            f"**`Idade da Conta:`** `{account_age} dias`\n"
            f"**`Status:`** `🔴 Não resolvida`\n"
            f"**`Data:`** {get_timestamp()}",
            discord.Color.red(),
            reported
        )
        
        view = ReportAdminView(report_id, reported, interaction.user)
        
        await channel.send(embed=embed, view=view)
        
        # Log interno (mostra quem denunciou)
        await log_report(guild, report_id, interaction.user, reported, motivo, "Não resolvida", False)
        
        await interaction.response.send_message(
            "✅ Sua denúncia foi enviada anonimamente para análise!", ephemeral=True
        )

class ReportAdminView(View):
    def __init__(self, report_id, reported, reporter):
        super().__init__(timeout=None)
        self.report_id = report_id
        self.reported = reported
        self.reporter = reporter
    
    @discord.ui.button(label="✅ Aceitar Denúncia", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("Apenas donos!", ephemeral=True)
            return
        
        # Atualiza status
        if self.report_id in db.reports:
            db.reports[self.report_id]["status"] = "Resolvida"
        
        # Envia para canal público de denúncias
        public_channel = discord.utils.get(interaction.guild.channels, name="denúncias")
        if not public_channel:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(send_messages=True)
            }
            public_channel = await interaction.guild.create_text_channel(
                "denúncias", overwrites=overwrites
            )
        
        embed = create_embed(
            f"🚨 DENÚNCIA ACEITA #{self.report_id}",
            f"**`Denunciado:`** {self.reported.mention}\n"
            f"**`Motivo:`** `{db.reports[self.report_id]['motivo']}`\n"
            f"**`Status:`** `✅ Resolvida`\n"
            f"**`Resolvida por:`** {interaction.user.mention}\n"
            f"**`Data:`** {get_timestamp()}",
            discord.Color.green(),
            self.reported
        )
        
        await public_channel.send(embed=embed)
        
        # Atualiza mensagem original
        await interaction.response.send_message("✅ Denúncia aceita e publicada!")
        self.stop()
        
        # Remove tópico após 5 minutos
        await asyncio.sleep(300)
        await interaction.channel.delete()
    
    @discord.ui.button(label="❌ Recusar Denúncia", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("Apenas donos!", ephemeral=True)
            return
        
        # Remove usuário do tópico e deleta
        await interaction.response.send_message("❌ Denúncia recusada.")
        
        await asyncio.sleep(2)
        await interaction.channel.delete()
    
    @discord.ui.button(label="🔍 Sob Revisão", style=discord.ButtonStyle.primary)
    async def review(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("Apenas donos!", ephemeral=True)
            return
        
        # Atualiza embed
        async for message in interaction.channel.history(limit=10):
            if message.embeds:
                embed = message.embeds[0]
                new_desc = embed.description.replace("**`Status:`** `🔴 Não resolvida`", 
                                                   "**`Status:`** `🟡 Sob Revisão`")
                new_embed = discord.Embed.from_dict(embed.to_dict())
                new_embed.description = new_desc
                await message.edit(embed=new_embed)
                break
        
        await interaction.response.send_message("🔍 Status atualizado para 'Sob Revisão'")

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE MODERAÇÃO
# ═══════════════════════════════════════════════════════════════

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Não especificado"):
        """Bane um usuário"""
        if member.top_role >= ctx.author.top_role and ctx.author.id not in OWNER_IDS:
            await ctx.send("Você não pode banir este usuário!")
            return
        
        await member.ban(reason=reason)
        
        embed = create_embed(
            "🔨 USUÁRIO BANIDO",
            f"**`Usuário:`** {member.mention}\n"
            f"**`ID:`** `{member.id}`\n"
            f"**`Moderador:`** {ctx.author.mention}\n"
            f"**`Motivo:`** `{reason}`\n"
            f"**`Data:`** {get_timestamp()}",
            discord.Color.red(),
            member
        )
        
        await ctx.send(embed=embed)
        await log_punishment(ctx.guild, "Ban", member, ctx.author, reason)
    
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Não especificado"):
        """Expulsa um usuário"""
        if member.top_role >= ctx.author.top_role and ctx.author.id not in OWNER_IDS:
            await ctx.send("Você não pode expulsar este usuário!")
            return
        
        await member.kick(reason=reason)
        
        embed = create_embed(
            "👢 USUÁRIO EXPULSO",
            f"**`Usuário:`** {member.mention}\n"
            f"**`ID:`** `{member.id}`\n"
            f"**`Moderador:`** {ctx.author.mention}\n"
            f"**`Motivo:`** `{reason}`\n"
            f"**`Data:`** {get_timestamp()}",
            discord.Color.orange(),
            member
        )
        
        await ctx.send(embed=embed)
        await log_punishment(ctx.guild, "Kick", member, ctx.author, reason)
    
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, tempo: str, *, reason: str = "Não especificado"):
        """Mute temporário (ex: 1h, 30m, 1d)"""
        if member.top_role >= ctx.author.top_role and ctx.author.id not in OWNER_IDS:
            await ctx.send("Você não pode mutar este usuário!")
            return
        
        # Parse tempo
        multiplicador = 1
        if tempo.endswith('h'):
            multiplicador = 1
            tempo = tempo[:-1]
        elif tempo.endswith('m'):
            multiplicador = 1/60
            tempo = tempo[:-1]
        elif tempo.endswith('d'):
            multiplicador = 24
            tempo = tempo[:-1]
        
        try:
            horas = float(tempo) * multiplicador
            await member.timeout(timedelta(hours=horas), reason=reason)
            
            embed = create_embed(
                "🔇 USUÁRIO MUTADO",
                f"**`Usuário:`** {member.mention}\n"
                f"**`ID:`** `{member.id}`\n"
                f"**`Moderador:`** {ctx.author.mention}\n"
                f"**`Duração:`** `{tempo}`\n"
                f"**`Motivo:`** `{reason}`\n"
                f"**`Data:`** {get_timestamp()}",
                discord.Color.dark_orange(),
                member
            )
            
            await ctx.send(embed=embed)
            await log_punishment(ctx.guild, "Mute", member, ctx.author, reason)
        except:
            await ctx.send("Formato de tempo inválido! Use: `!mute @user 1h motivo`")
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        """Aplica um aviso"""
        embed = create_embed(
            "⚠️ AVISO APLICADO",
            f"**`Usuário:`** {member.mention}\n"
            f"**`ID:`** `{member.id}`\n"
            f"**`Moderador:`** {ctx.author.mention}\n"
            f"**`Motivo:`** `{reason}`\n"
            f"**`Data:`** {get_timestamp()}",
            discord.Color.yellow(),
            member
        )
        
        await ctx.send(embed=embed)
        await member.send(f"⚠️ Você recebeu um aviso em {ctx.guild.name}: {reason}")
        await log_punishment(ctx.guild, "Warn", member, ctx.author, reason)

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE SUGESTÕES
# ═══════════════════════════════════════════════════════════════

async def process_suggestion_message(message):
    """Processa mensagem de sugestão"""
    # Cria tópico
    thread = await message.create_thread(name=f"Sugestão de {message.author.name}")
    
    # Embed
    embed = create_embed(
        "💡 NOVA SUGESTÃO",
        f"**`Autor:`** {message.author.mention}\n"
        f"**`Sugestão:`**\n{message.content}\n\n"
        f"Vote com ✅ ou ❌",
        discord.Color.blue(),
        message.author
    )
    
    msg = await thread.send(embed=embed)
    await msg.add_reaction("✅")
    await msg.add_reaction("❌")
    
    # Salva para processamento posterior
    db.suggestions[msg.id] = {
        "author_id": message.author.id,
        "content": message.content,
        "message_id": msg.id,
        "channel_id": thread.id,
        "created_at": datetime.datetime.now().isoformat()
    }

@tasks.loop(hours=24)
async def process_suggestions():
    """Processa sugestões a cada 7 dias"""
    # Implementação simplificada - verifica idade das sugestões
    now = datetime.datetime.now()
    for msg_id, data in list(db.suggestions.items()):
        created = datetime.datetime.fromisoformat(data["created_at"])
        if (now - created).days >= 7:
            # Processa votação
            # Na prática, precisaríamos buscar a mensagem e contar reações
            pass

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE BUGS E LEADERBOARD
# ═══════════════════════════════════════════════════════════════

async def process_bug_report(message, bug_type):
    """Processa reporte de bug"""
    user = message.author
    
    # Atualiza contador
    if user.id not in db.bug_reports:
        db.bug_reports[user.id] = 0
    db.bug_reports[user.id] += 1
    
    # Atualiza stats staff se for staff
    staff_roles = ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador", ".☘︎ ݁˖Gerente Cassino", "💰 Ajudante Cassino"]
    is_staff = any(discord.utils.get(user.roles, name=r) for r in staff_roles)
    
    if is_staff:
        if user.id not in db.staff_stats:
            db.staff_stats[user.id] = {"tickets": 0, "bugs": 0}
        db.staff_stats[user.id]["bugs"] += 1
    
    # Pergunta se quer pingar staff
    view = BugPingView(bug_type)
    await message.reply(
        "🐛 Bug reportado! Deseja notificar a equipe?", view=view, ephemeral=True
    )

class BugPingView(View):
    def __init__(self, bug_type):
        super().__init__(timeout=60)
        self.bug_type = bug_type
    
    @discord.ui.button(label="📢 Sim, notificar", style=discord.ButtonStyle.primary)
    async def yes_ping(self, interaction: discord.Interaction, button: Button):
        # Seleciona cargo aleatório da staff
        staff_roles = ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]
        available_roles = []
        
        for role_name in staff_roles:
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if role:
                available_roles.append(role)
        
        if available_roles:
            selected = random.choice(available_roles)
            await interaction.channel.send(f"{selected.mention} 🚨 Novo bug reportado!")
        
        await interaction.response.send_message(
            "✅ Um staff foi avisado! Aguarde o mesmo te atender!", ephemeral=True
        )
    
    @discord.ui.button(label="❌ Não", style=discord.ButtonStyle.secondary)
    async def no_ping(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("✅ Entendido. Obrigado pelo report!", ephemeral=True)

@tasks.loop(hours=720)  # A cada 30 dias aproximadamente
async def reset_monthly_leaderboard():
    """Reseta leaderboard mensal"""
    # Envia leaderboard final
    if db.bug_reports:
        sorted_bugs = sorted(db.bug_reports.items(), key=lambda x: x[1], reverse=True)[:10]
        
        desc = ""
        for i, (user_id, count) in enumerate(sorted_bugs, 1):
            user = bot.get_user(user_id)
            name = user.name if user else f"Usuário {user_id}"
            desc += f"{i}. `{name}` - {count} bugs\n"
        
        embed = create_embed(
            "🏆 LEADERBOARD DE BUGS - MÊS FINAL",
            desc if desc else "Nenhum bug reportado este mês.",
            discord.Color.gold()
        )
        
        # Envia para canal apropriado
        for guild in bot.guilds:
            channel = discord.utils.get(guild.channels, name="leaderboard-bugs")
            if channel:
                await channel.send(embed=embed)
    
    # Reseta
    db.bug_reports = {}
    db.save()

# ═══════════════════════════════════════════════════════════════
# COMANDOS SLASH
# ═══════════════════════════════════════════════════════════════

@bot.tree.command(name="denunciar", description="🚨 Denunciar um usuário anonimamente")
@app_commands.describe(usuario="Usuário a ser denunciado", motivo="Motivo da denúncia")
async def slash_denunciar(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    await ReportSystem.create_report(interaction, usuario, motivo)

@bot.tree.command(name="block", description="⛔ Bloquear invites em um canal")
@app_commands.describe(canal="Canal para bloquear invites")
@commands.has_permissions(administrator=True)
async def slash_block(interaction: discord.Interaction, canal: discord.TextChannel):
    db.blocked_channels.add(canal.id)
    db.save()
    await interaction.response.send_message(
        f"✅ Invites bloqueados em {canal.mention}!", ephemeral=True
    )

@bot.tree.command(name="ajuda", description="❓ Mostra o painel de ajuda do cassino")
async def slash_ajuda(interaction: discord.Interaction):
    if interaction.channel.name != "comandos":
        await interaction.response.send_message(
            "Use este comando apenas no canal <#comandos>!", ephemeral=True
        )
        return
    
    embed = discord.Embed(
        title="🎰 BEM-VINDO AO PAINEL DE AJUDA - LeGusta Casino! 🎰",
        description="""💰 **1. FICHAS - COMO FUNCIONA?**
Para apostar em qualquer máquina, você precisa adquirir fichas:
• Fichas de 5k ou 10k
• Algumas máquinas aceitam apenas fichas de 10k
• Outras aceitam apenas fichas de 5k
⚠️ Escolha a máquina de acordo com sua ficha!

🛒 **2. ONDE COMPRO FICHAS?**
Ao chegar na LeGusta, caminhe em direção ao cassino:
• Barris da FRENTE = VENDER fichas ✅
• Barris do FUNDO = COMPRAR fichas ✅
Perdido? Chame um staff online:
• *Spokeas | *Mateus | *Gusteds

🎮 **3. MINIGAMES DISPONÍVEIS**
Contamos com 3 minigames incríveis:
• 🏰 Lucky Tower
• 🎰 Caça Níqueis
• 🎡 Roleta

📋 **4. COMO JOGAR EM CADA MINIGAME?**

• Lucky Tower → Fichas de 10k ✅
• Roleta → Fichas de 10k ✅
• Caça Níqueis → Fichas de 5k ✅
⚠️ Lucky Tower e Roleta NÃO aceitam fichas de 5k!

⚖️ **5. REGRAS IMPORTANTES DO CASSINO**
✓ Respeite a fila nos minigames
✓ Não roube prêmios de outros jogadores
✓ Seja respeitoso com staff e players
✓ Sem brigas ou badernices
❌ Denúncias? Abra um ticket ou use o canal de denúncias
😔 Quebra de regras = BAN da GO e/ou do servidor!

Se tiver dúvidas, chame um staff! Boa sorte nos minigames! 🍀""",
        color=discord.Color.gold()
    )
    embed.set_image(url="https://i.imgur.com/1NA8dQR.png")
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sorteio", description="🎉 Inicia um sorteio")
@commands.has_permissions(administrator=True)
async def slash_sorteio(interaction: discord.Interaction, premio: str, duracao: int):
    """Inicia um sorteio (duração em minutos)"""
    embed = create_embed(
        "🎉 SORTEIO INICIADO!",
        f"**`Prêmio:`** {premio}\n"
        f"**`Duração:`** {duracao} minutos\n"
        f"**`Host:`** {interaction.user.mention}\n\n"
        f"Reaja com 🎉 para participar!",
        discord.Color.green()
    )
    
    msg = await interaction.channel.send(embed=embed)
    await msg.add_reaction("🎉")
    
    await interaction.response.send_message("Sorteio iniciado!", ephemeral=True)
    
    # Aguarda e sorteia
    await asyncio.sleep(duracao * 60)
    
    # Pega participantes
    msg = await interaction.channel.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    
    if reaction:
        users = [user async for user in reaction.users() if not user.bot]
        if users:
            winner = random.choice(users)
            await interaction.channel.send(
                f"🎉 Parabéns {winner.mention}! Você ganhou: **{premio}**!"
            )

# ═══════════════════════════════════════════════════════════════
# COMANDOS DE TEXTO
# ═══════════════════════════════════════════════════════════════

@bot.command()
@commands.is_owner()
async def setup(ctx):
    """Configura todo o servidor automaticamente"""
    guild = ctx.guild
    
    # Mensagem de início
    msg = await ctx.send("🎰 Iniciando configuração do LeGusta Casino...")
    
    # ═══════════════════════════════════════════════════════════
    # CRIAÇÃO DE CARGOS
    # ═══════════════════════════════════════════════════════════
    
    await msg.edit(content="🎰 Criando cargos...")
    
    roles_config = {
        "🃏 Gusteds": {"color": discord.Color.dark_purple(), "hoist": True, "protected": True},
        "🃁 Spokeas": {"color": discord.Color.dark_blue(), "hoist": True, "protected": True},
        "🜲 Dono": {"color": discord.Color.gold(), "hoist": True},
        "💸ADMIN💸": {"color": discord.Color.red(), "hoist": True},
        "⛨ Moderador": {"color": discord.Color.green(), "hoist": True},
        ".☘︎ ݁˖Gerente Cassino": {"color": discord.Color.dark_gold(), "hoist": True},
        "💰 Ajudante Cassino": {"color": discord.Color.blue(), "hoist": True},
        "🎲 Gastador": {"color": discord.Color.purple()},
        "⚜ Magnata": {"color": discord.Color.orange()},
        "👤 Membro": {"color": discord.Color.light_grey()},
        "🚫 Punido": {"color": discord.Color.dark_grey()}
    }
    
    created_roles = {}
    for name, config in roles_config.items():
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(
                name=name,
                color=config["color"],
                hoist=config.get("hoist", False),
                mentionable=True
            )
        created_roles[name] = role
    
    # Atribui cargos protegidos aos donos
    gusteds_role = created_roles.get("🃏 Gusteds")
    spokeas_role = created_roles.get("🃁 Spokeas")
    
    if gusteds_role:
        gusteds = guild.get_member(GUSTEDS_ID)
        if gusteds and gusteds_role not in gusteds.roles:
            await gusteds.add_roles(gusteds_role)
    
    if spokeas_role:
        spokeas = guild.get_member(SPOKEAS_ID)
        if spokeas and spokeas_role not in spokeas.roles:
            await spokeas.add_roles(spokeas_role)
    
    # ═══════════════════════════════════════════════════════════
    # CRIAÇÃO DE CATEGORIAS E CANAIS
    # ═══════════════════════════════════════════════════════════
    
    await msg.edit(content="🎰 Criando categorias e canais...")
    
    # Permissões base
    default_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    staff_overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    # Adiciona donos aos overwrites de staff
    for owner_id in OWNER_IDS:
        owner = guild.get_member(owner_id)
        if owner:
            staff_overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    
    # Adiciona cargos staff
    for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]:
        role = created_roles.get(role_name)
        if role:
            staff_overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    
    categories_data = {
        "📢 INFORMAÇÕES": {
            "channels": [
                ("📋regras", "text"),
                ("❓faq", "text"),
                ("📢anúncios", "text"),
                ("🎰sobre-o-cassino", "text")
            ],
            "overwrites": default_overwrites
        },
        "💬 COMUNIDADE": {
            "channels": [
                ("💬chat-geral", "text"),
                ("📸mídia", "text"),
                ("🤖comandos", "text")
            ],
            "overwrites": None
        },
        "🎟️ SUPORTE": {
            "channels": [
                ("🎫criar-ticket", "text"),
                ("🚨denúncias", "text"),
                ("❓ajuda", "text")
            ],
            "overwrites": None
        },
        "🎉 EVENTOS": {
            "channels": [
                ("🎁sorteios", "text"),
                ("🎊eventos", "text"),
                ("🏆resultados", "text")
            ],
            "overwrites": None
        },
        "💡 SUGESTÕES": {
            "channels": [
                ("💭sugestões-pro-bot", "text"),
                ("✅sugestões-aceitas", "text")
            ],
            "overwrites": None
        },
        "🐛 BUGS": {
            "channels": [
                ("🎮reportar-bugs-minigames", "text"),
                ("🤖reportar-bugs-bot", "text"),
                ("🏆leaderboard-bugs", "text")
            ],
            "overwrites": None
        },
        "🔒 STAFF": {
            "channels": [
                ("💬staff-chat", "text"),
                ("⚙️configurações", "text")
            ],
            "overwrites": staff_overwrites
        },
        "📊 LOGS": {
            "channels": [
                ("👤logs-de-usuário", "text"),
                ("📝logs-mensagens", "text"),
                ("🎫logs-de-tickets", "text"),
                ("🔨logs-de-punições", "text"),
                ("🚨logs-de-denúncias", "text")
            ],
            "overwrites": staff_overwrites  # Apenas donos
        },
        "🗑️ LIXEIRA": {
            "channels": [],
            "overwrites": staff_overwrites
        }
    }
    
    for cat_name, cat_data in categories_data.items():
        # Cria categoria
        category = discord.utils.get(guild.categories, name=cat_name)
        if not category:
            if cat_data["overwrites"]:
                category = await guild.create_category(cat_name, overwrites=cat_data["overwrites"])
            else:
                category = await guild.create_category(cat_name)
        
        # Cria canais
        for channel_name, channel_type in cat_data["channels"]:
            existing = discord.utils.get(guild.channels, name=channel_name.replace("📋", "").replace("❓", "").replace("📢", "").replace("🎰", "").replace("💬", "").replace("📸", "").replace("🤖", "").replace("🎫", "").replace("🚨", "").replace("🎁", "").replace("🎊", "").replace("🏆", "").replace("💭", "").replace("✅", "").replace("🎮", "").replace("💬", "").replace("⚙️", "").replace("👤", "").replace("📝", "").replace("🎫", "").replace("🔨", "").strip("-"))
            
            if not existing:
                if channel_type == "text":
                    overwrites = cat_data["overwrites"] if cat_data["overwrites"] else {}
                    await guild.create_text_channel(channel_name, category=category, overwrites=overwrites)
    
    # Configura canal de ajuda
    ajuda_channel = discord.utils.get(guild.channels, name="ajuda")
    if ajuda_channel:
        ajuda_embed = discord.Embed(
            title="🎰 BEM-VINDO AO PAINEL DE AJUDA - LeGusta Casino! 🎰",
            description="""💰 **1. FICHAS - COMO FUNCIONA?**
Para apostar em qualquer máquina, você precisa adquirir fichas:
• Fichas de 5k ou 10k
• Algumas máquinas aceitam apenas fichas de 10k
• Outras aceitam apenas fichas de 5k
⚠️ Escolha a máquina de acordo com sua ficha!

🛒 **2. ONDE COMPRO FICHAS?**
Ao chegar na LeGusta, caminhe em direção ao cassino:
• Barris da FRENTE = VENDER fichas ✅
• Barris do FUNDO = COMPRAR fichas ✅
Perdido? Chame um staff online:
• *Spokeas | *Mateus | *Gusteds

🎮 **3. MINIGAMES DISPONÍVEIS**
Contamos com 3 minigames incríveis:
• 🏰 Lucky Tower
• 🎰 Caça Níqueis
• 🎡 Roleta

📋 **4. COMO JOGAR EM CADA MINIGAME?**

• Lucky Tower → Fichas de 10k ✅
• Roleta → Fichas de 10k ✅
• Caça Níqueis → Fichas de 5k ✅
⚠️ Lucky Tower e Roleta NÃO aceitam fichas de 5k!

⚖️ **5. REGRAS IMPORTANTES DO CASSINO**
✓ Respeite a fila nos minigames
✓ Não roube prêmios de outros jogadores
✓ Seja respeitoso com staff e players
✓ Sem brigas ou badernices
❌ Denúncias? Abra um ticket ou use o canal de denúncias
😔 Quebra de regras = BAN da GO e/ou do servidor!

Se tiver dúvidas, chame um staff! Boa sorte nos minigames! 🍀""",
            color=discord.Color.gold()
        )
        await ajuda_channel.send(embed=ajuda_embed)
    
    # Configura painel de ticket
    ticket_channel = discord.utils.get(guild.channels, name="criar-ticket")
    if ticket_channel:
        ticket_embed = create_embed(
            "🎫 CENTRAL DE TICKETS",
            "Bem-vindo à central de atendimento!\n\n"
            "Selecione uma opção abaixo para abrir um ticket:\n\n"
            "❓ **Dúvidas** - Tire suas dúvidas\n"
            "🎰 **Sobre o Cassino** - Questões sobre jogos\n"
            "🚨 **Denúncias** - Reportar comportamento\n"
            "👑 **Falar com Gerência** - Assuntos urgentes",
            discord.Color.blue()
        )
        view = TicketPanel()
        await ticket_channel.send(embed=ticket_embed, view=view)
    
    await msg.edit(content="✅ Configuração concluída! LeGusta Casino está pronto! 🎰")

@bot.command()
@commands.is_owner()
async def resetup(ctx):
    """Recria toda a estrutura do servidor"""
    await ctx.send("🔄 Reiniciando configuração...")
    await setup(ctx)

@bot.command()
async def ping(ctx):
    """Verifica a latência do bot"""
    latency = round(bot.latency * 1000)
    embed = create_embed(
        "🏓 PONG!",
        f"**`Latência:`** `{latency}ms`\n**`Status:`** 🟢 Online",
        discord.Color.green()
    )
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════
# PROTEÇÃO DE CARGOS
# ═══════════════════════════════════════════════════════════════

@bot.event
async def on_member_update(before, after):
    """Protege cargos especiais"""
    # Verifica se alguém tentou adicionar cargos protegidos
    if len(before.roles) < len(after.roles):
        new_roles = [r for r in after.roles if r not in before.roles]
        
        for role in new_roles:
            if is_protected_role(role.name):
                # Verifica quem fez a alteração
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id:
                        # Se não for dono, reverte
                        if entry.user.id not in OWNER_IDS:
                            await after.remove_roles(role)
                            
                            # Log
                            log_channel = discord.utils.get(after.guild.channels, name="logs-de-punições")
                            if log_channel:
                                embed = create_embed(
                                    "⛔ TENTATIVA DE ATRIBUIÇÃO DE CARGO PROTEGIDO",
                                    f"**`Usuário:`** {after.mention}\n"
                                    f"**`Tentativa por:`** {entry.user.mention}\n"
                                    f"**`Cargo:`** {role.mention}\n"
                                    f"**`Ação:`** Revertida automaticamente",
                                    discord.Color.dark_red()
                                )
                                await log_channel.send(embed=embed)
                            
                            # Avisa o tentador
                            try:
                                await entry.user.send(f"⛔ Você não tem permissão para atribuir o cargo {role.name}!")
                            except:
                                pass
                        break

# ═══════════════════════════════════════════════════════════════
# VERIFICAÇÃO DE TICKETS ANTIGOS
# ═══════════════════════════════════════════════════════════════

@tasks.loop(hours=24)
async def check_old_tickets():
    """Verifica tickets abertos há mais de 30 dias"""
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name.startswith("ticket-"):
                # Verifica idade
                async for message in channel.history(limit=1, oldest_first=True):
                    age = datetime.datetime.now() - message.created_at
                    if age.days >= 30:
                        # Envia aviso
                        view = OldTicketView()
                        await channel.send(
                            "⚠️ Este ticket está aberto há mais de 30 dias. Deseja fechá-lo?",
                            view=view
                        )
                    break

class OldTicketView(View):
    def __init__(self):
        super().__init__(timeout=86400)  # 24 horas
    
    @discord.ui.button(label="✅ Sim, fechar", style=discord.ButtonStyle.success)
    async def close(self, interaction: discord.Interaction, button: Button):
        # Move para lixeira
        trash = discord.utils.get(interaction.guild.categories, name="🗑️ LIXEIRA")
        if trash:
            await interaction.channel.edit(category=trash, name=f"arquivado-{interaction.channel.name}")
            await interaction.response.send_message("🔒 Ticket arquivado!")
    
    @discord.ui.button(label="❌ Manter aberto", style=discord.ButtonStyle.secondary)
    async def keep(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("✅ Ticket mantido aberto.", ephemeral=True)

# ═══════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════

async def main():
    async with bot:
        await bot.add_cog(Moderation(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
