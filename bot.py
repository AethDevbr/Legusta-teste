# bot.py - LeGusta Casino Bot
# Versão Final Completa e Funcional
# Python 3.11.9 | discord.py 2.3.2

import os
import asyncio
import random
import string
import datetime
import json
import re
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

# IDs de cargos protegidos
PROTECTED_ROLE_NAMES = ["🃏 Gusteds", "🃁 Spokeas"]

# Banco de dados
class Database:
    def __init__(self):
        self.bug_reports = {}
        self.suggestions = {}
        self.tickets = {}
        self.reports = {}
        self.staff_stats = {}
        self.blocked_channels = set()
        self.user_data = {}
        self.ticket_counter = 0
        
    def save(self):
        data = {
            'bug_reports': self.bug_reports,
            'suggestions': self.suggestions,
            'staff_stats': self.staff_stats,
            'blocked_channels': list(self.blocked_channels),
            'user_data': self.user_data,
            'ticket_counter': self.ticket_counter
        }
        try:
            with open('database.json', 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Erro ao salvar DB: {e}")
    
    def load(self):
        try:
            with open('database.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.bug_reports = data.get('bug_reports', {})
                self.suggestions = data.get('suggestions', {})
                self.staff_stats = data.get('staff_stats', {})
                self.blocked_channels = set(data.get('blocked_channels', []))
                self.user_data = data.get('user_data', {})
                self.ticket_counter = data.get('ticket_counter', 0)
        except:
            pass

db = Database()
db.load()

# ═══════════════════════════════════════════════════════════════
# UTILITÁRIOS
# ═══════════════════════════════════════════════════════════════

def generate_ticket_id():
    """Gera ID único para tickets"""
    db.ticket_counter += 1
    db.save()
    return f"TKT-{db.ticket_counter:04d}"

def generate_report_id():
    """Gera ID único para denúncias"""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

def get_timestamp():
    """Retorna timestamp formatado"""
    now = datetime.datetime.now()
    return f"<t:{int(now.timestamp())}:F>"

def get_time_code():
    """Retorna código de tempo relativo"""
    return f"<t:{int(datetime.datetime.now().timestamp())}:R>"

def create_embed(title: str, description: str = "", color: discord.Color = discord.Color.gold(), 
                 author: discord.Member = None, thumbnail: str = None, image: str = None,
                 footer_text: str = "LeGusta Casino © 2024"):
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
        
    embed.set_footer(text=footer_text, icon_url="https://i.imgur.com/1NA8dQR.png")
    return embed

def is_owner(user_id: int) -> bool:
    """Verifica se é dono"""
    return user_id in OWNER_IDS

def is_staff(member: discord.Member) -> bool:
    """Verifica se é staff"""
    staff_roles = ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador", ".☘︎ ݁˖Gerente Cassino", "💰 Ajudante Cassino"]
    return any(discord.utils.get(member.roles, name=r) for r in staff_roles)

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
    print(f"Bot: {bot.user.name} | ID: {bot.user.id}")
    
    # Sincroniza comandos slash
    try:
        synced = await bot.tree.sync()
        print(f"✅ Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"❌ Erro ao sincronizar: {e}")
    
    # Inicia tarefas
    check_old_tickets.start()
    process_suggestions.start()
    reset_monthly_leaderboard.start()
    db.save()

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE LOGS - CORRIGIDO E FUNCIONAL
# ═══════════════════════════════════════════════════════════════

async def get_or_create_log_channel(guild, channel_name):
    """Busca ou cria canal de log"""
    channel = discord.utils.get(guild.channels, name=channel_name)
    if not channel:
        # Busca categoria de logs
        category = discord.utils.get(guild.categories, name="📊 LOGS")
        if not category:
            # Cria categoria com permissões apenas para donos
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
            }
            for owner_id in OWNER_IDS:
                owner = guild.get_member(owner_id)
                if owner:
                    overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            
            category = await guild.create_category("📊 LOGS", overwrites=overwrites)
        
        # Cria canal
        channel = await guild.create_text_channel(channel_name, category=category)
    
    return channel

@bot.event
async def on_message_delete(message):
    """Log de mensagens deletadas - CORRIGIDO"""
    if message.author.bot:
        return
    
    if not message.guild:
        return
    
    channel = await get_or_create_log_channel(message.guild, "logs-mensagens")
    
    # Conteúdo da mensagem
    content = message.content if message.content else "*[Sem texto - possivelmente embed ou arquivo]*"
    
    # Se for muito longo, trunca
    if len(content) > 1000:
        content = content[:997] + "..."
    
    embed = create_embed(
        "🗑️ MENSAGEM DELETADA",
        f"**`Autor:`** {message.author.mention} (`{message.author.id}`)\n"
        f"**`Canal:`** {message.channel.mention}\n"
        f"**`Horário:`** {get_timestamp()}\n\n"
        f"**`Conteúdo:`**\n```\n{content}\n```",
        discord.Color.red(),
        message.author
    )
    
    # Se tiver anexos
    if message.attachments:
        files = ", ".join([a.filename for a in message.attachments[:5]])
        embed.add_field(name="📎 Anexos", value=f"`{files}`", inline=False)
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar delete: {e}")

@bot.event
async def on_message_edit(before, after):
    """Log de mensagens editadas - CORRIGIDO"""
    if before.author.bot:
        return
    
    if not before.guild:
        return
    
    if before.content == after.content:
        return
    
    channel = await get_or_create_log_channel(before.guild, "logs-mensagens")
    
    before_content = before.content if before.content else "*Sem conteúdo*"
    after_content = after.content if after.content else "*Sem conteúdo*"
    
    if len(before_content) > 500:
        before_content = before_content[:497] + "..."
    if len(after_content) > 500:
        after_content = after_content[:497] + "..."
    
    embed = create_embed(
        "✏️ MENSAGEM EDITADA",
        f"**`Autor:`** {before.author.mention} (`{before.author.id}`)\n"
        f"**`Canal:`** {before.channel.mention}\n"
        f"**`Link:`** [Ir para mensagem]({after.jump_url})\n"
        f"**`Horário:`** {get_timestamp()}\n\n"
        f"**`Antes:`**\n```\n{before_content}\n```\n"
        f"**`Depois:`**\n```\n{after_content}\n```",
        discord.Color.orange(),
        before.author
    )
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar edit: {e}")

@bot.event
async def on_member_join(member):
    """Log de entrada - CORRIGIDO"""
    if not member.guild:
        return
    
    channel = await get_or_create_log_channel(member.guild, "logs-de-usuário")
    
    account_age = (datetime.datetime.now() - member.created_at).days
    
    embed = create_embed(
        "✅ NOVO MEMBRO",
        f"**`Usuário:`** {member.mention}\n"
        f"**`ID:`** `{member.id}`\n"
        f"**`Tag:`** `{member}`\n"
        f"**`Conta Criada:`** <t:{int(member.created_at.timestamp())}:F> ({account_age} dias)\n"
        f"**`Entrada:`** {get_timestamp()}",
        discord.Color.green(),
        member
    )
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar join: {e}")
    
    # Cargo automático
    membro_role = discord.utils.get(member.guild.roles, name="👤 Membro")
    if membro_role:
        try:
            await member.add_roles(membro_role)
        except:
            pass

@bot.event
async def on_member_remove(member):
    """Log de saída - CORRIGIDO"""
    if not member.guild:
        return
    
    channel = await get_or_create_log_channel(member.guild, "logs-de-usuário")
    
    embed = create_embed(
        "👋 MEMBRO SAIU",
        f"**`Usuário:`** `{member}`\n"
        f"**`ID:`** `{member.id}`\n"
        f"**`Saída:`** {get_timestamp()}",
        discord.Color.red()
    )
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar leave: {e}")

@bot.event
async def on_member_update(before, after):
    """Log de atualizações de membro"""
    if not before.guild:
        return
    
    # Nome alterado
    if before.display_name != after.display_name:
        channel = await get_or_create_log_channel(before.guild, "logs-de-usuário")
        embed = create_embed(
            "📝 NOME ALTERADO",
            f"**`Usuário:`** {after.mention}\n"
            f"**`De:`** `{before.display_name}`\n"
            f"**`Para:`** `{after.display_name}`\n"
            f"**`Horário:`** {get_timestamp()}",
            discord.Color.blue(),
            after
        )
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    # Avatar alterado
    if before.display_avatar.url != after.display_avatar.url:
        channel = await get_or_create_log_channel(before.guild, "logs-de-usuário")
        embed = create_embed(
            "🖼️ AVATAR ALTERADO",
            f"**`Usuário:`** {after.mention}\n"
            f"**`Horário:`** {get_timestamp()}",
            discord.Color.blue(),
            after,
            thumbnail=after.display_avatar.url
        )
        try:
            await channel.send(embed=embed)
        except:
            pass
    
    # Proteção de cargos
    if len(before.roles) < len(after.roles):
        new_roles = [r for r in after.roles if r not in before.roles]
        for role in new_roles:
            if is_protected_role(role.name):
                async for entry in after.guild.audit_logs(limit=1, action=discord.AuditLogAction.member_role_update):
                    if entry.target.id == after.id and entry.user.id not in OWNER_IDS:
                        await after.remove_roles(role)
                        log_channel = await get_or_create_log_channel(after.guild, "logs-de-punições")
                        embed = create_embed(
                            "⛔ TENTATIVA DE CARGO PROTEGIDO",
                            f"**`Tentativa por:`** {entry.user.mention}\n"
                            f"**`Tentou dar:`** {role.mention} para {after.mention}\n"
                            f"**`Ação:`** Revertida automaticamente",
                            discord.Color.dark_red()
                        )
                        try:
                            await log_channel.send(embed=embed)
                        except:
                            pass
                        try:
                            await entry.user.send(f"⛔ Você não pode atribuir o cargo {role.name}!")
                        except:
                            pass
                        break

async def log_punishment(guild, punishment_type, target, moderator, reason):
    """Log de punições"""
    channel = await get_or_create_log_channel(guild, "logs-de-punições")
    
    account_age = (datetime.datetime.now() - target.created_at).days
    
    colors = {
        "Ban": discord.Color.dark_red(),
        "Kick": discord.Color.red(),
        "Warn": discord.Color.orange(),
        "Mute": discord.Color.yellow()
    }
    
    embed = create_embed(
        f"🔨 {punishment_type}",
        f"**`Usuário:`** {target.mention}\n"
        f"**`ID:`** `{target.id}`\n"
        f"**`Conta Criada:`** <t:{int(target.created_at.timestamp())}:F> ({account_age} dias)\n"
        f"**`Moderador:`** {moderator.mention}\n"
        f"**`Motivo:`** `{reason}`\n"
        f"**`Horário:`** {get_timestamp()}",
        colors.get(punishment_type, discord.Color.red()),
        target
    )
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar punição: {e}")

async def log_ticket_event(guild, action, ticket_id, user, staff=None):
    """Log de tickets"""
    channel = await get_or_create_log_channel(guild, "logs-de-tickets")
    
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
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar ticket: {e}")

async def log_report(guild, report_id, reporter, reported, reason, status, anonymous=True):
    """Log de denúncias"""
    channel = await get_or_create_log_channel(guild, "logs-de-denúncias")
    
    reporter_name = "||Anônimo||" if anonymous else reporter.mention
    
    embed = create_embed(
        "🚨 LOG DE DENÚNCIA",
        f"**`ID:`** `{report_id}`\n"
        f"**`Denunciado:`** {reported.mention} (`{reported.id}`)\n"
        f"**`Por:`** {reporter_name} (`{reporter.id}`)\n"
        f"**`Motivo:`** `{reason}`\n"
        f"**`Status:`** `{status}`\n"
        f"**`Horário:`** {get_timestamp()}",
        discord.Color.dark_red(),
        reported
    )
    
    try:
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar denúncia: {e}")

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE TICKET - PAINEL COMPLETO
# ═══════════════════════════════════════════════════════════════

class TicketTypeSelect(Select):
    def __init__(self):
        options = [
            discord.SelectOption(
                label="❓ Dúvidas Gerais",
                value="duvidas",
                description="Tire suas dúvidas sobre o servidor",
                emoji="❓"
            ),
            discord.SelectOption(
                label="🎰 Sobre o Cassino",
                value="cassino",
                description="Questões sobre jogos e fichas",
                emoji="🎰"
            ),
            discord.SelectOption(
                label="🚨 Denúncias",
                value="denuncias",
                description="Reportar comportamento inadequado",
                emoji="🚨"
            ),
            discord.SelectOption(
                label="👑 Falar com Gerência",
                value="gerencia",
                description="Apenas para assuntos urgentes",
                emoji="👑"
            ),
            discord.SelectOption(
                label="🔧 Suporte Técnico",
                value="tecnico",
                description="Problemas técnicos no servidor",
                emoji="🔧"
            )
        ]
        super().__init__(
            placeholder="🎫 Clique aqui para abrir um ticket...",
            min_values=1,
            max_values=1,
            options=options,
            custom_id="ticket_type_select"
        )
    
    async def callback(self, interaction: discord.Interaction):
        ticket_type = self.values[0]
        await create_ticket(interaction, ticket_type)

class TicketPanelView(View):
    def __init__(self):
        super().__init__(timeout=None)
        self.add_item(TicketTypeSelect())
    
    @discord.ui.button(
        label="📋 Ver Meus Tickets",
        style=discord.ButtonStyle.secondary,
        custom_id="my_tickets",
        row=1
    )
    async def my_tickets(self, interaction: discord.Interaction, button: Button):
        guild = interaction.guild
        user = interaction.user
        
        user_tickets = []
        for channel in guild.text_channels:
            if channel.topic and f"UserID: {user.id}" in channel.topic:
                user_tickets.append(channel)
        
        if not user_tickets:
            await interaction.response.send_message(
                "❌ Você não tem tickets abertos!", ephemeral=True
            )
            return
        
        embed = create_embed(
            "🎫 SEUS TICKETS ABERTOS",
            "\n".join([f"• {t.mention} - `{t.topic.split('Ticket #')[1].split('|')[0].strip()}`" for t in user_tickets[:5]]) if user_tickets else "Nenhum ticket aberto",
            discord.Color.blue()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)

async def create_ticket(interaction: discord.Interaction, ticket_type: str):
    """Cria um ticket"""
    guild = interaction.guild
    user = interaction.user
    
    type_names = {
        "duvidas": "❓ Dúvidas Gerais",
        "cassino": "🎰 Sobre o Cassino",
        "denuncias": "🚨 Denúncias",
        "gerencia": "👑 Falar com Gerência",
        "tecnico": "🔧 Suporte Técnico"
    }
    
    type_name = type_names.get(ticket_type, "🎫 Suporte")
    
    # Verifica se já tem ticket aberto
    for channel in guild.text_channels:
        if channel.topic and f"UserID: {user.id}" in channel.topic and "Status: Aguardando" in channel.topic:
            await interaction.response.send_message(
                f"❌ Você já tem um ticket aberto: {channel.mention}", 
                ephemeral=True
            )
            return
    
    # Busca categoria
    category = discord.utils.get(guild.categories, name="🎟️ SUPORTE")
    if not category:
        category = await guild.create_category("🎟️ SUPORTE")
    
    ticket_id = generate_ticket_id()
    
    # Busca cargos staff
    staff_roles = []
    ping_roles = []
    for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador", ".☘︎ ݁˖Gerente Cassino", "💰 Ajudante Cassino"]:
        role = discord.utils.get(guild.roles, name=role_name)
        if role:
            staff_roles.append(role)
            if role_name in ["🜲 Dono", ".☘︎ ݁˖Gerente Cassino", "💸ADMIN💸"]:
                ping_roles.append(role)
    
    # Permissões
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        user: discord.PermissionOverwrite(read_messages=True, send_messages=True, attach_files=True, embed_links=True),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True, manage_permissions=True)
    }
    
    for role in staff_roles:
        overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_messages=True, manage_channels=True)
    
    # Cria canal
    channel = await guild.create_text_channel(
        f"🎫┃{user.name}",
        category=category,
        overwrites=overwrites,
        topic=f"Ticket #{ticket_id} | Tipo: {ticket_type} | UserID: {user.id} | Status: Aguardando staff..."
    )
    
    # Salva dados
    db.tickets[channel.id] = {
        "id": ticket_id,
        "user_id": user.id,
        "type": ticket_type,
        "type_name": type_name,
        "created_at": datetime.datetime.now().isoformat(),
        "staff_id": None,
        "staff_name": None,
        "status": "Aguardando staff..."
    }
    db.save()
    
    # MENSAGEM DE ATENDIMENTO BONITA
    welcome_embed = discord.Embed(
        title=f"🎰 BEM-VINDO AO ATENDIMENTO - LeGusta Casino",
        description=(
            f"Olá {user.mention}! Seu ticket foi aberto com sucesso!\n\n"
            f"🎫 **Informações do Ticket:**\n"
            f"**`ID:`** `{ticket_id}`\n"
            f"**`Tipo:`** {type_name}\n"
            f"**`Aberto em:`** {get_timestamp()}\n"
            f"**`Status:`** 🟡 Aguardando staff...\n\n"
            f"👤 **Dados do Usuário:**\n"
            f"**`Nome:`** `{user}`\n"
            f"**`ID:`** `{user.id}`\n\n"
            f"⏰ **Horário de Atendimento:**\n"
            f"• Segunda a Sexta: 14h às 22h\n"
            f"• Sábados e Domingos: 12h às 20h\n\n"
            f"📝 **O que fazer agora?**\n"
            f"1. Descreva seu problema com detalhes\n"
            f"2. Aguarde um staff assumir seu ticket\n"
            f"3. Seja educado e paciente\n\n"
            f"⚠️ **Avisos Importantes:**\n"
            f"• Não marque repetidamente a staff\n"
            f"• Tickets inativos por 30 dias serão fechados automaticamente\n"
            f"• Abuse do sistema resultará em punição\n\n"
            f"🍀 **Boa sorte e obrigado por escolher o LeGusta Casino!**"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now()
    )
    welcome_embed.set_thumbnail(url=user.display_avatar.url)
    welcome_embed.set_image(url="https://i.imgur.com/1NA8dQR.png")
    welcome_embed.set_footer(text="LeGusta Casino © 2024 | Sistema de Tickets", icon_url="https://i.imgur.com/1NA8dQR.png")
    
    # View com botões
    view = TicketControlView(ticket_id, user.id, channel.id)
    
    # Ping em spoiler
    ping_text = " ".join([r.mention for r in ping_roles]) if ping_roles else ""
    
    msg = await channel.send(
        content=f"||{ping_text}||",
        embed=welcome_embed,
        view=view
    )
    
    # Fixa mensagem
    try:
        await msg.pin()
    except:
        pass
    
    # Confirmação para usuário
    confirm_embed = create_embed(
        "✅ TICKET CRIADO COM SUCESSO!",
        f"**`Canal:`** {channel.mention}\n"
        f"**`ID:`** `{ticket_id}`\n"
        f"**`Tipo:`** {type_name}\n\n"
        f"Um staff será atendê-lo em breve! 🍀",
        discord.Color.green()
    )
    
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
    
    # Log
    await log_ticket_event(guild, "Ticket Criado", ticket_id, user)

class TicketControlView(View):
    def __init__(self, ticket_id, user_id, channel_id):
        super().__init__(timeout=None)
        self.ticket_id = ticket_id
        self.user_id = user_id
        self.channel_id = channel_id
    
    @discord.ui.button(
        label="✋ Assumir Ticket",
        style=discord.ButtonStyle.success,
        custom_id="claim_ticket"
    )
    async def claim_ticket(self, interaction: discord.Interaction, button: Button):
        if not is_staff(interaction.user):
            await interaction.response.send_message("⛔ Apenas staff!", ephemeral=True)
            return
        
        if self.channel_id in db.tickets and db.tickets[self.channel_id].get("staff_id"):
            current = db.tickets[self.channel_id]["staff_name"]
            await interaction.response.send_message(f"⚠️ Já assumido por {current}!", ephemeral=True)
            return
        
        # Atualiza dados
        db.tickets[self.channel_id]["staff_id"] = interaction.user.id
        db.tickets[self.channel_id]["staff_name"] = str(interaction.user)
        db.tickets[self.channel_id]["status"] = "Em atendimento"
        db.save()
        
        # Atualiza estatísticas
        if interaction.user.id not in db.staff_stats:
            db.staff_stats[interaction.user.id] = {"tickets": 0, "bugs": 0}
        db.staff_stats[interaction.user.id]["tickets"] += 1
        
        # Atualiza tópico
        channel = interaction.channel
        await channel.edit(topic=f"Ticket #{self.ticket_id} | Status: Em atendimento por {interaction.user.name}")
        
        # Nova mensagem de atendimento
        embed = discord.Embed(
            title="🎰 ATENDIMENTO INICIADO",
            description=(
                f"✅ **Staff Responsável:** {interaction.user.mention}\n"
                f"**`Horário:`** {get_timestamp()}\n\n"
                f"📝 **Próximos passos:**\n"
                f"1. Leia com atenção a solicitação do usuário\n"
                f"2. Responda de forma clara e educada\n"
                f"3. Resolva o problema da melhor forma possível\n"
                f"4. Ao finalizar, clique em **Fechar Ticket**\n\n"
                f"⏱️ **Meta de Resolução:** 24 horas"
            ),
            color=discord.Color.green()
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        await channel.send(embed=embed)
        
        # Atualiza botão
        button.disabled = True
        button.label = f"✅ Assumido por {interaction.user.name}"
        button.style = discord.ButtonStyle.secondary
        await interaction.response.edit_message(view=self)
    
    @discord.ui.button(
        label="🔒 Fechar Ticket",
        style=discord.ButtonStyle.danger,
        custom_id="close_ticket"
    )
    async def close_ticket(self, interaction: discord.Interaction, button: Button):
        is_ticket_owner = interaction.user.id == self.user_id
        
        if not (is_staff(interaction.user) or is_ticket_owner):
            await interaction.response.send_message("⛔ Apenas staff ou o criador!", ephemeral=True)
            return
        
        view = ConfirmCloseView(self.ticket_id, self.user_id, self.channel_id)
        embed = create_embed(
            "🔒 CONFIRMAR FECHAMENTO",
            "Deseja realmente fechar este ticket?\nEle será movido para a Lixeira.",
            discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

class ConfirmCloseView(View):
    def __init__(self, ticket_id, user_id, channel_id):
        super().__init__(timeout=60)
        self.ticket_id = ticket_id
        self.user_id = user_id
        self.channel_id = channel_id
    
    @discord.ui.button(label="✅ Sim, fechar", style=discord.ButtonStyle.success)
    async def confirm(self, interaction: discord.Interaction, button: Button):
        channel = interaction.channel
        
        # Atualiza dados
        if self.channel_id in db.tickets:
            db.tickets[self.channel_id]["status"] = "Fechado"
            db.tickets[self.channel_id]["closed_at"] = datetime.datetime.now().isoformat()
            db.tickets[self.channel_id]["closed_by"] = interaction.user.id
            db.save()
        
        # Move para lixeira
        trash_category = discord.utils.get(interaction.guild.categories, name="🗑️ LIXEIRA")
        if not trash_category:
            overwrites = {
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            for owner_id in OWNER_IDS:
                owner = interaction.guild.get_member(owner_id)
                if owner:
                    overwrites[owner] = discord.PermissionOverwrite(read_messages=True)
            for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]:
                role = discord.utils.get(interaction.guild.roles, name=role_name)
                if role:
                    overwrites[role] = discord.PermissionOverwrite(read_messages=True)
            
            trash_category = await interaction.guild.create_category("🗑️ LIXEIRA", overwrites=overwrites)
        
        # Remove permissões do usuário
        user = interaction.guild.get_member(self.user_id)
        if user:
            await channel.set_permissions(user, overwrite=None)
        
        # Renomeia e move
        await channel.edit(name=f"🔒┃arquivado-{self.ticket_id}", category=trash_category)
        
        # Mensagem final
        embed = create_embed(
            "🔒 TICKET ARQUIVADO",
            f"**`Ticket ID:`** `{self.ticket_id}`\n"
            f"**`Fechado por:`** {interaction.user.mention}\n"
            f"**`Data:`** {get_timestamp()}\n\n"
            f"Este ticket foi arquivado e está disponível apenas para staff.",
            discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)
        
        # Log
        user = interaction.guild.get_member(self.user_id)
        if user:
            await log_ticket_event(interaction.guild, "Ticket Fechado", self.ticket_id, user, interaction.user)
        
        self.stop()
    
    @discord.ui.button(label="❌ Não, manter aberto", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("✅ Ticket mantido aberto.", ephemeral=True)
        self.stop()

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE DENÚNCIAS
# ═══════════════════════════════════════════════════════════════

class ReportSystem:
    @staticmethod
    async def create_report(interaction: discord.Interaction, reported: discord.Member, motivo: str):
        if reported.id in OWNER_IDS:
            await interaction.response.send_message("⛔ Não é possível denunciar donos!", ephemeral=True)
            return
        
        guild = interaction.guild
        report_id = generate_report_id()
        
        # Cria canal privado
        category = discord.utils.get(guild.categories, name="🔒 STAFF")
        if not category:
            category = await guild.create_category("🔒 STAFF")
        
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True)
        }
        
        for owner_id in OWNER_IDS:
            owner = guild.get_member(owner_id)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        channel = await guild.create_text_channel(
            f"🚨┃denuncia-{report_id}",
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
        db.save()
        
        # Embed
        account_age = (datetime.datetime.now() - reported.created_at).days
        
        embed = create_embed(
            f"🚨 DENÚNCIA #{report_id}",
            f"**`Denunciado:`** {reported.mention}\n"
            f"**`ID:`** `{reported.id}`\n"
            f"**`Por:`** ||Anônimo||\n"
            f"**`Motivo:`** `{motivo}`\n"
            f"**`Conta:`** {account_age} dias\n"
            f"**`Status:`** 🔴 Não resolvida\n"
            f"**`Data:`** {get_timestamp()}",
            discord.Color.red(),
            reported
        )
        
        view = ReportAdminView(report_id, reported, interaction.user)
        await channel.send(embed=embed, view=view)
        
        # Log interno
        await log_report(guild, report_id, interaction.user, reported, motivo, "Não resolvida", False)
        
        # Confirmação
        confirm = create_embed(
            "✅ DENÚNCIA ENVIADA",
            f"**`ID:`** `{report_id}`\nAnalisaremos em breve! Obrigado.",
            discord.Color.green()
        )
        await interaction.response.send_message(embed=confirm, ephemeral=True)

class ReportAdminView(View):
    def __init__(self, report_id, reported, reporter):
        super().__init__(timeout=None)
        self.report_id = report_id
        self.reported = reported
        self.reporter = reporter
    
    @discord.ui.button(label="✅ Aceitar", style=discord.ButtonStyle.success)
    async def accept(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("⛔ Apenas donos!", ephemeral=True)
            return
        
        db.reports[self.report_id]["status"] = "Resolvida"
        db.save()
        
        # Publica
        public_channel = discord.utils.get(interaction.guild.channels, name="denúncias")
        if not public_channel:
            overwrites = {interaction.guild.default_role: discord.PermissionOverwrite(send_messages=False)}
            public_channel = await interaction.guild.create_text_channel("denúncias", overwrites=overwrites)
        
        embed = create_embed(
            f"🚨 DENÚNCIA ACEITA #{self.report_id}",
            f"**`Denunciado:`** {self.reported.mention}\n"
            f"**`Motivo:`** `{db.reports[self.report_id]['motivo']}`\n"
            f"**`Resolvida por:`** {interaction.user.mention}",
            discord.Color.green(),
            self.reported
        )
        
        await public_channel.send(embed=embed)
        await interaction.response.send_message("✅ Denúncia aceita!")
        
        await asyncio.sleep(300)
        await interaction.channel.delete()
    
    @discord.ui.button(label="❌ Recusar", style=discord.ButtonStyle.danger)
    async def reject(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("⛔ Apenas donos!", ephemeral=True)
            return
        
        await interaction.response.send_message("❌ Denúncia recusada.")
        await asyncio.sleep(5)
        await interaction.channel.delete()
    
    @discord.ui.button(label="🔍 Sob Revisão", style=discord.ButtonStyle.primary)
    async def review(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("⛔ Apenas donos!", ephemeral=True)
            return
        
        db.reports[self.report_id]["status"] = "Sob Revisão"
        db.save()
        
        async for message in interaction.channel.history(limit=10):
            if message.embeds and "DENÚNCIA #" in message.embeds[0].title:
                old = message.embeds[0]
                new_desc = old.description.replace("🔴 Não resolvida", "🟡 Sob Revisão")
                new = discord.Embed.from_dict(old.to_dict())
                new.description = new_desc
                await message.edit(embed=new)
                break
        
        await interaction.response.send_message("🔍 Status atualizado!")

# ═══════════════════════════════════════════════════════════════
# COMANDOS SLASH
# ═══════════════════════════════════════════════════════════════

@bot.tree.command(name="ticket", description="🎫 Envia o painel de tickets no canal atual")
@commands.has_permissions(administrator=True)
async def slash_ticket(interaction: discord.Interaction):
    """Envia o painel de tickets"""
    
    embed = discord.Embed(
        title="🎰 CENTRAL DE ATENDIMENTO - LeGusta Casino",
        description=(
            "Bem-vindo ao sistema de tickets do LeGusta Casino!\n\n"
            "🎫 **Como funciona:**\n"
            "Selecione uma opção no menu abaixo para abrir um atendimento privado com nossa equipe.\n\n"
            "📋 **Tipos de Atendimento:**\n"
            "❓ **Dúvidas Gerais** - Tire suas dúvidas sobre o servidor\n"
            "🎰 **Sobre o Cassino** - Questões sobre jogos, fichas e máquinas\n"
            "🚨 **Denúncias** - Reportar comportamento inadequado de jogadores\n"
            "👑 **Falar com Gerência** - Assuntos urgentes (apenas gerentes)\n"
            "🔧 **Suporte Técnico** - Problemas técnicos no servidor\n\n"
            "⏰ **Horário de Atendimento:**\n"
            "• Segunda a Sexta: 14h às 22h\n"
            "• Fins de semana: 12h às 20h\n\n"
            "⚠️ **Importante:**\n"
            "• Abuse do sistema resultará em punição\n"
            "• Tickets inativos por 30 dias são fechados automaticamente\n"
            "• Seja claro e objetivo na descrição do problema\n\n"
            "🍀 **Boa sorte e obrigado por escolher o LeGusta Casino!**"
        ),
        color=discord.Color.gold(),
        timestamp=datetime.datetime.now()
    )
    embed.set_thumbnail(url="https://i.imgur.com/1NA8dQR.png")
    embed.set_image(url="https://i.imgur.com/1NA8dQR.png")
    embed.set_footer(text="LeGusta Casino © 2024 | Clique no menu abaixo para abrir um ticket")
    
    view = TicketPanelView()
    
    await interaction.response.send_message("✅ Painel de tickets enviado!", ephemeral=True)
    await interaction.channel.send(embed=embed, view=view)

@bot.tree.command(name="denunciar", description="🚨 Denunciar um usuário anonimamente")
@app_commands.describe(usuario="Usuário a denunciar", motivo="Motivo da denúncia")
async def slash_denunciar(interaction: discord.Interaction, usuario: discord.Member, motivo: str):
    await ReportSystem.create_report(interaction, usuario, motivo)

@bot.tree.command(name="block", description="⛔ Bloquear invites em um canal")
@app_commands.describe(canal="Canal para bloquear")
@commands.has_permissions(administrator=True)
async def slash_block(interaction: discord.Interaction, canal: discord.TextChannel):
    db.blocked_channels.add(canal.id)
    db.save()
    await interaction.response.send_message(f"✅ Invites bloqueados em {canal.mention}!", ephemeral=True)

@bot.tree.command(name="ajuda", description="❓ Painel de ajuda do cassino")
async def slash_ajuda(interaction: discord.Interaction):
    if interaction.channel.name != "comandos":
        await interaction.response.send_message("Use no canal comandos!", ephemeral=True)
        return
    
    embed = discord.Embed(
        title="🎰 PAINEL DE AJUDA - LeGusta Casino",
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
• 🏰 Lucky Tower
• 🎰 Caça Níqueis
• 🎡 Roleta

📋 **4. COMO JOGAR?**
• Lucky Tower → Fichas de 10k ✅
• Roleta → Fichas de 10k ✅
• Caça Níqueis → Fichas de 5k ✅
⚠️ Lucky Tower e Roleta NÃO aceitam fichas de 5k!

⚖️ **5. REGRAS IMPORTANTES**
✓ Respeite a fila nos minigames
✓ Não roube prêmios de outros jogadores
✓ Seja respeitoso com staff e players
❌ Denúncias? Abra um ticket
😔 Quebra de regras = BAN""",
        color=discord.Color.gold()
    )
    embed.set_image(url="https://i.imgur.com/1NA8dQR.png")
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="sorteio", description="🎉 Iniciar um sorteio")
@app_commands.describe(premio="Prêmio do sorteio", duracao="Duração em minutos", canal="Canal do sorteio")
@commands.has_permissions(administrator=True)
async def slash_sorteio(interaction: discord.Interaction, premio: str, duracao: int, canal: discord.TextChannel):
    embed = create_embed(
        "🎉 SORTEIO!",
        f"**`Prêmio:`** {premio}\n**`Duração:`** {duracao}min\n**`Host:`** {interaction.user.mention}\n\nReaja com 🎉!",
        discord.Color.green()
    )
    
    msg = await canal.send(embed=embed)
    await msg.add_reaction("🎉")
    await interaction.response.send_message(f"Sorteio iniciado em {canal.mention}!", ephemeral=True)
    
    await asyncio.sleep(duracao * 60)
    
    msg = await canal.fetch_message(msg.id)
    reaction = discord.utils.get(msg.reactions, emoji="🎉")
    
    if reaction:
        users = [u async for u in reaction.users() if not u.bot]
        if users:
            winner = random.choice(users)
            await canal.send(f"🎉 Parabéns {winner.mention}! Você ganhou: **{premio}**!")

# ═══════════════════════════════════════════════════════════════
# COMANDOS DE TEXTO
# ═══════════════════════════════════════════════════════════════

class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
    
    @commands.command()
    @commands.has_permissions(ban_members=True)
    async def ban(self, ctx, member: discord.Member, *, reason: str = "Não especificado"):
        if member.id in OWNER_IDS:
            await ctx.send("⛔ Não posso banir donos!")
            return
        
        await member.ban(reason=reason)
        embed = create_embed(
            "🔨 BANIDO",
            f"**`Usuário:`** {member.mention}\n**`ID:`** `{member.id}`\n**`Mod:`** {ctx.author.mention}\n**`Motivo:`** `{reason}`",
            discord.Color.red(),
            member
        )
        await ctx.send(embed=embed)
        await log_punishment(ctx.guild, "Ban", member, ctx.author, reason)
    
    @commands.command()
    @commands.has_permissions(kick_members=True)
    async def kick(self, ctx, member: discord.Member, *, reason: str = "Não especificado"):
        if member.id in OWNER_IDS:
            await ctx.send("⛔ Não posso expulsar donos!")
            return
        
        await member.kick(reason=reason)
        embed = create_embed(
            "👢 EXPULSO",
            f"**`Usuário:`** {member.mention}\n**`ID:`** `{member.id}`\n**`Mod:`** {ctx.author.mention}\n**`Motivo:`** `{reason}`",
            discord.Color.orange(),
            member
        )
        await ctx.send(embed=embed)
        await log_punishment(ctx.guild, "Kick", member, ctx.author, reason)
    
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, tempo: str, *, reason: str = "Não especificado"):
        if member.id in OWNER_IDS:
            await ctx.send("⛔ Não posso mutar donos!")
            return
        
        # Parse tempo
        if tempo.endswith('h'):
            horas = float(tempo[:-1])
        elif tempo.endswith('m'):
            horas = float(tempo[:-1]) / 60
        elif tempo.endswith('d'):
            horas = float(tempo[:-1]) * 24
        else:
            horas = float(tempo)
        
        await member.timeout(timedelta(hours=horas), reason=reason)
        embed = create_embed(
            "🔇 MUTADO",
            f"**`Usuário:`** {member.mention}\n**`ID:`** `{member.id}`\n**`Mod:`** {ctx.author.mention}\n**`Tempo:`** `{tempo}`\n**`Motivo:`** `{reason}`",
            discord.Color.yellow(),
            member
        )
        await ctx.send(embed=embed)
        await log_punishment(ctx.guild, "Mute", member, ctx.author, reason)
    
    @commands.command()
    @commands.has_permissions(manage_messages=True)
    async def warn(self, ctx, member: discord.Member, *, reason: str):
        embed = create_embed(
            "⚠️ AVISO",
            f"**`Usuário:`** {member.mention}\n**`ID:`** `{member.id}`\n**`Mod:`** {ctx.author.mention}\n**`Motivo:`** `{reason}`",
            discord.Color.orange(),
            member
        )
        await ctx.send(embed=embed)
        try:
            await member.send(f"⚠️ Aviso em {ctx.guild.name}: {reason}")
        except:
            pass
        await log_punishment(ctx.guild, "Warn", member, ctx.author, reason)

# ═══════════════════════════════════════════════════════════════
# SETUP E OUTROS COMANDOS
# ═══════════════════════════════════════════════════════════════

@bot.command()
@commands.is_owner()
async def setup(ctx):
    """Setup completo do servidor"""
    guild = ctx.guild
    msg = await ctx.send("🎰 Iniciando setup...")
    
    # Cargos
    await msg.edit(content="🎰 Criando cargos...")
    
    roles_data = {
        "🃏 Gusteds": {"color": 0x2C2F33, "hoist": True},
        "🃁 Spokeas": {"color": 0x23272A, "hoist": True},
        "🜲 Dono": {"color": 0xFFD700, "hoist": True},
        "💸ADMIN💸": {"color": 0xFF0000, "hoist": True},
        "⛨ Moderador": {"color": 0x00FF00, "hoist": True},
        ".☘︎ ݁˖Gerente Cassino": {"color": 0xB8860B, "hoist": True},
        "💰 Ajudante Cassino": {"color": 0x0000FF, "hoist": True},
        "🎲 Gastador": {"color": 0x800080},
        "⚜ Magnata": {"color": 0xFFA500},
        "👤 Membro": {"color": 0x808080},
        "🚫 Punido": {"color": 0x333333}
    }
    
    created_roles = {}
    for name, data in roles_data.items():
        role = discord.utils.get(guild.roles, name=name)
        if not role:
            role = await guild.create_role(name=name, color=discord.Color(data["color"]), hoist=data["hoist"])
        created_roles[name] = role
    
    # Atribui cargos protegidos
    gusteds = guild.get_member(GUSTEDS_ID)
    spokeas = guild.get_member(SPOKEAS_ID)
    if gusteds and created_roles["🃏 Gusteds"]:
        await gusteds.add_roles(created_roles["🃏 Gusteds"])
    if spokeas and created_roles["🃁 Spokeas"]:
        await spokeas.add_roles(created_roles["🃁 Spokeas"])
    
    # Categorias e Canais
    await msg.edit(content="🎰 Criando canais...")
    
    # Overwrites
    staff_overwrites = {guild.default_role: discord.PermissionOverwrite(read_messages=False)}
    for owner_id in OWNER_IDS:
        owner = guild.get_member(owner_id)
        if owner:
            staff_overwrites[owner] = discord.PermissionOverwrite(read_messages=True)
    for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]:
        role = created_roles.get(role_name)
        if role:
            staff_overwrites[role] = discord.PermissionOverwrite(read_messages=True)
    
    categories = {
        "📢 INFORMAÇÕES": [("📋regras", None), ("❓faq", None), ("📢anúncios", None), ("🎰sobre-o-cassino", None)],
        "💬 COMUNIDADE": [("💬chat-geral", None), ("📸mídia", None), ("🤖comandos", None)],
        "🎟️ SUPORTE": [("🎫criar-ticket", None), ("🚨denúncias", None), ("❓ajuda", None)],
        "🎉 EVENTOS": [("🎁sorteios", None), ("🎊eventos", None), ("🏆resultados", None)],
        "💡 SUGESTÕES": [("💭sugestões-pro-bot", None), ("✅sugestões-aceitas", None)],
        "🐛 BUGS": [("🎮reportar-bugs-minigames", None), ("🤖reportar-bugs-bot", None), ("🏆leaderboard-bugs", None)],
        "🔒 STAFF": [("💬staff-chat", staff_overwrites), ("⚙️configurações", staff_overwrites)],
        "📊 LOGS": [
            ("👤logs-de-usuário", staff_overwrites),
            ("📝logs-mensagens", staff_overwrites),
            ("🎫logs-de-tickets", staff_overwrites),
            ("🔨logs-de-punições", staff_overwrites),
            ("🚨logs-de-denúncias", staff_overwrites)
        ],
        "🗑️ LIXEIRA": [("arquivados", staff_overwrites)]
    }
    
    for cat_name, channels in categories.items():
        cat = discord.utils.get(guild.categories, name=cat_name)
        if not cat:
            if "LOGS" in cat_name or "STAFF" in cat_name or "LIXEIRA" in cat_name:
                cat = await guild.create_category(cat_name, overwrites=staff_overwrites)
            else:
                cat = await guild.create_category(cat_name)
        
        for ch_name, overwrites in channels:
            clean_name = ''.join(c for c in ch_name if c.isalnum() or c in '-_').lower()
            existing = discord.utils.get(guild.channels, name=clean_name)
            if not existing:
                if overwrites:
                    await guild.create_text_channel(ch_name, category=cat, overwrites=overwrites)
                else:
                    await guild.create_text_channel(ch_name, category=cat)
    
    # Envia painel de ticket
    ticket_ch = discord.utils.get(guild.channels, name="criar-ticket")
    if ticket_ch:
        embed = discord.Embed(
            title="🎰 CENTRAL DE ATENDIMENTO - LeGusta Casino",
            description="Use o menu abaixo para abrir um ticket!",
            color=discord.Color.gold()
        )
        view = TicketPanelView()
        await ticket_ch.send(embed=embed, view=view)
    
    await msg.edit(content="✅ Setup concluído!")

@bot.command()
@commands.is_owner()
async def resetup(ctx):
    await setup(ctx)

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    embed = create_embed("🏓 PONG!", f"**`Latência:`** `{latency}ms`", discord.Color.green())
    await ctx.send(embed=embed)

# ═══════════════════════════════════════════════════════════════
# TAREFAS AGENDADAS
# ═══════════════════════════════════════════════════════════════

@tasks.loop(hours=24)
async def check_old_tickets():
    """Verifica tickets antigos"""
    for guild in bot.guilds:
        for channel in guild.text_channels:
            if channel.name.startswith("🎫┃"):
                try:
                    async for message in channel.history(limit=1, oldest_first=True):
                        age = datetime.datetime.now() - message.created_at
                        if age.days >= 30:
                            view = View()
                            view.add_item(Button(label="🔒 Fechar", style=discord.ButtonStyle.danger, custom_id="close_old"))
                            await channel.send("⚠️ Ticket inativo por 30+ dias. Fechar?", view=view)
                        break
                except:
                    pass

@tasks.loop(hours=24)
async def process_suggestions():
    pass

@tasks.loop(hours=720)
async def reset_monthly_leaderboard():
    pass

# ═══════════════════════════════════════════════════════════════
# ANTI-SPAM E BLOQUEADOR DE INVITES
# ═══════════════════════════════════════════════════════════════

@bot.event
async def on_message(message):
    if message.author.bot:
        return
    
    # Anti-spam
    if len(message.content) > 500:
        repeats = len(message.content) - len(set(message.content))
        if repeats > len(message.content) * 0.7:
            await handle_spam(message)
    
    # Bloqueador de invites
    if "discord.gg/" in message.content.lower() or "discord.com/invite/" in message.content.lower():
        if message.channel.id in db.blocked_channels:
            try:
                await message.delete()
                embed = create_embed("⛔ INVITE BLOQUEADO", "Convites não são permitidos aqui!", discord.Color.red())
                await message.channel.send(embed=embed, delete_after=5)
                return
            except:
                pass
    
    await bot.process_commands(message)

async def handle_spam(message):
    channel = await get_or_create_log_channel(message.guild, "logs-mensagens")
    embed = create_embed(
        "⚠️ SPAM DETECTADO",
        f"**`Autor:`** {message.author.mention}\n**`Canal:`** {message.channel.mention}",
        discord.Color.orange()
    )
    await channel.send(embed=embed)

# ═══════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════

async def main():
    async with bot:
        await bot.add_cog(Moderation(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
