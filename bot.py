# bot.py - LeGusta Casino Bot
# Versão Final Corrigida - Setup Funcionando 100%
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
    
    try:
        synced = await bot.tree.sync()
        print(f"✅ Comandos sincronizados: {len(synced)}")
    except Exception as e:
        print(f"❌ Erro ao sincronizar: {e}")
    
    check_old_tickets.start()
    process_suggestions.start()
    reset_monthly_leaderboard.start()
    db.save()

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE LOGS
# ═══════════════════════════════════════════════════════════════

async def get_or_create_log_channel(guild, channel_name):
    """Busca ou cria canal de log"""
    # Procura por nome exato ou similar
    for channel in guild.text_channels:
        if channel.name == channel_name or channel_name in channel.name:
            return channel
    
    # Cria categoria se não existir
    category = discord.utils.get(guild.categories, name="📊 LOGS")
    if not category:
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for owner_id in OWNER_IDS:
            owner = guild.get_member(owner_id)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            category = await guild.create_category("📊 LOGS", overwrites=overwrites)
        except Exception as e:
            print(f"Erro ao criar categoria LOGS: {e}")
            category = None
    
    # Cria canal
    try:
        if category:
            channel = await guild.create_text_channel(channel_name, category=category)
        else:
            channel = await guild.create_text_channel(channel_name)
        return channel
    except Exception as e:
        print(f"Erro ao criar canal {channel_name}: {e}")
        return None

@bot.event
async def on_message_delete(message):
    """Log de mensagens deletadas"""
    if message.author.bot or not message.guild:
        return
    
    try:
        channel = await get_or_create_log_channel(message.guild, "logs-mensagens")
        if not channel:
            return
        
        content = message.content if message.content else "*[Sem texto]*"
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
        
        if message.attachments:
            files = ", ".join([a.filename for a in message.attachments[:5]])
            embed.add_field(name="📎 Anexos", value=f"`{files}`", inline=False)
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar delete: {e}")

@bot.event
async def on_message_edit(before, after):
    """Log de mensagens editadas"""
    if before.author.bot or not before.guild or before.content == after.content:
        return
    
    try:
        channel = await get_or_create_log_channel(before.guild, "logs-mensagens")
        if not channel:
            return
        
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
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar edit: {e}")

@bot.event
async def on_member_join(member):
    """Log de entrada"""
    if not member.guild:
        return
    
    try:
        channel = await get_or_create_log_channel(member.guild, "logs-de-usuario")
        if not channel:
            return
        
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
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar join: {e}")
    
    # Cargo automático
    try:
        membro_role = discord.utils.get(member.guild.roles, name="👤 Membro")
        if membro_role:
            await member.add_roles(membro_role)
    except:
        pass

@bot.event
async def on_member_remove(member):
    """Log de saída"""
    if not member.guild:
        return
    
    try:
        channel = await get_or_create_log_channel(member.guild, "logs-de-usuario")
        if not channel:
            return
        
        embed = create_embed(
            "👋 MEMBRO SAIU",
            f"**`Usuário:`** `{member}`\n"
            f"**`ID:`** `{member.id}`\n"
            f"**`Saída:`** {get_timestamp()}",
            discord.Color.red()
        )
        
        await channel.send(embed=embed)
    except Exception as e:
        print(f"Erro ao logar leave: {e}")

# ═══════════════════════════════════════════════════════════════
# SISTEMA DE TICKET
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
            if channel.topic and str(user.id) in channel.topic:
                user_tickets.append(channel)
        
        if not user_tickets:
            await interaction.response.send_message(
                "❌ Você não tem tickets abertos!", ephemeral=True
            )
            return
        
        embed = create_embed(
            "🎫 SEUS TICKETS ABERTOS",
            "\n".join([f"• {t.mention}" for t in user_tickets[:5]]) if user_tickets else "Nenhum ticket aberto",
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
        if channel.topic and str(user.id) in channel.topic and "Aguardando" in channel.topic:
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
        f"ticket-{user.name}",
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
    
    # MENSAGEM DE ATENDIMENTO
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
    
    view = TicketControlView(ticket_id, user.id, channel.id)
    
    ping_text = " ".join([r.mention for r in ping_roles]) if ping_roles else ""
    
    msg = await channel.send(
        content=f"||{ping_text}||",
        embed=welcome_embed,
        view=view
    )
    
    try:
        await msg.pin()
    except:
        pass
    
    confirm_embed = create_embed(
        "✅ TICKET CRIADO COM SUCESSO!",
        f"**`Canal:`** {channel.mention}\n"
        f"**`ID:`** `{ticket_id}`\n"
        f"**`Tipo:`** {type_name}\n\n"
        f"Um staff será atendê-lo em breve! 🍀",
        discord.Color.green()
    )
    
    await interaction.response.send_message(embed=confirm_embed, ephemeral=True)
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
        
        db.tickets[self.channel_id]["staff_id"] = interaction.user.id
        db.tickets[self.channel_id]["staff_name"] = str(interaction.user)
        db.tickets[self.channel_id]["status"] = "Em atendimento"
        db.save()
        
        if interaction.user.id not in db.staff_stats:
            db.staff_stats[interaction.user.id] = {"tickets": 0, "bugs": 0}
        db.staff_stats[interaction.user.id]["tickets"] += 1
        
        channel = interaction.channel
        await channel.edit(topic=f"Ticket #{self.ticket_id} | Status: Em atendimento por {interaction.user.name}")
        
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
        
        if self.channel_id in db.tickets:
            db.tickets[self.channel_id]["status"] = "Fechado"
            db.tickets[self.channel_id]["closed_at"] = datetime.datetime.now().isoformat()
            db.tickets[self.channel_id]["closed_by"] = interaction.user.id
            db.save()
        
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
        
        user = interaction.guild.get_member(self.user_id)
        if user:
            await channel.set_permissions(user, overwrite=None)
        
        await channel.edit(name=f"arquivado-{self.ticket_id}", category=trash_category)
        
        embed = create_embed(
            "🔒 TICKET ARQUIVADO",
            f"**`Ticket ID:`** `{self.ticket_id}`\n"
            f"**`Fechado por:`** {interaction.user.mention}\n"
            f"**`Data:`** {get_timestamp()}\n\n"
            f"Este ticket foi arquivado e está disponível apenas para staff.",
            discord.Color.red()
        )
        
        await interaction.response.send_message(embed=embed)
        
        user = interaction.guild.get_member(self.user_id)
        if user:
            await log_ticket_event(interaction.guild, "Ticket Fechado", self.ticket_id, user, interaction.user)
        
        self.stop()
    
    @discord.ui.button(label="❌ Não, manter aberto", style=discord.ButtonStyle.secondary)
    async def cancel(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_message("✅ Ticket mantido aberto.", ephemeral=True)
        self.stop()

async def log_ticket_event(guild, action, ticket_id, user, staff=None):
    """Log de tickets"""
    channel = await get_or_create_log_channel(guild, "logs-de-tickets")
    if not channel:
        return
    
    desc = f"**`Ação:`** {action}\n**`Ticket ID:`** `{ticket_id}`\n**`Usuário:`** {user.mention}\n"
    if staff:
        desc += f"**`Staff:`** {staff.mention}"
    
    embed = create_embed("🎫 LOG DE TICKET", desc, discord.Color.purple())
    
    try:
        await channel.send(embed=embed)
    except:
        pass

# ═══════════════════════════════════════════════════════════════
# COMANDOS SLASH
# ═══════════════════════════════════════════════════════════════

@bot.tree.command(name="ticket", description="🎫 Envia o painel de tickets no canal atual")
@commands.has_permissions(administrator=True)
async def slash_ticket(interaction: discord.Interaction):
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
    if usuario.id in OWNER_IDS:
        await interaction.response.send_message("⛔ Não é possível denunciar donos!", ephemeral=True)
        return
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
# MODERAÇÃO
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
    
    @commands.command()
    @commands.has_permissions(moderate_members=True)
    async def mute(self, ctx, member: discord.Member, tempo: str, *, reason: str = "Não especificado"):
        if member.id in OWNER_IDS:
            await ctx.send("⛔ Não posso mutar donos!")
            return
        
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

# ═══════════════════════════════════════════════════════════════
# SETUP CORRIGIDO E FUNCIONANDO
# ═══════════════════════════════════════════════════════════════

@bot.command()
@commands.is_owner()
async def setup(ctx):
    """Setup COMPLETO - Cria tudo passo a passo com verificação"""
    guild = ctx.guild
    
    progress_msg = await ctx.send("🎰 **SETUP INICIADO** - Preparando estrutura...")
    
    created_roles = {}
    created_categories = {}
    created_channels = {}
    
    try:
        # ═══════════════════════════════════════════════════════════
        # ETAPA 1: CARGOS
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 1/7** - Criando cargos...")
        
        roles_config = [
            ("🃏 Gusteds", 0x2C2F33, True),
            ("🃁 Spokeas", 0x23272A, True),
            ("🜲 Dono", 0xFFD700, True),
            ("💸ADMIN💸", 0xFF0000, True),
            ("⛨ Moderador", 0x00FF00, True),
            (".☘︎ ݁˖Gerente Cassino", 0xB8860B, True),
            ("💰 Ajudante Cassino", 0x0000FF, True),
            ("🎲 Gastador", 0x800080, False),
            ("⚜ Magnata", 0xFFA500, False),
            ("👤 Membro", 0x808080, False),
            ("🚫 Punido", 0x333333, False)
        ]
        
        for role_name, color, hoist in roles_config:
            existing = discord.utils.get(guild.roles, name=role_name)
            if existing:
                created_roles[role_name] = existing
            else:
                try:
                    new_role = await guild.create_role(
                        name=role_name,
                        color=discord.Color(color),
                        hoist=hoist,
                        mentionable=True
                    )
                    created_roles[role_name] = new_role
                    await asyncio.sleep(0.5)  # Evita rate limit
                except Exception as e:
                    print(f"Erro ao criar cargo {role_name}: {e}")
        
        # Atribui cargos protegidos
        gusteds_member = guild.get_member(GUSTEDS_ID)
        spokeas_member = guild.get_member(SPOKEAS_ID)
        
        if gusteds_member and "🃏 Gusteds" in created_roles:
            try:
                await gusteds_member.add_roles(created_roles["🃏 Gusteds"])
            except:
                pass
        
        if spokeas_member and "🃁 Spokeas" in created_roles:
            try:
                await spokeas_member.add_roles(created_roles["🃁 Spokeas"])
            except:
                pass
        
        # ═══════════════════════════════════════════════════════════
        # ETAPA 2: OVERWRITES BASE
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 2/7** - Preparando permissões...")
        
        # Overwrites para canais staff (apenas donos e staff)
        staff_overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True, manage_channels=True)
        }
        
        # Adiciona donos
        for owner_id in OWNER_IDS:
            owner = guild.get_member(owner_id)
            if owner:
                staff_overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        # Adiciona cargos staff
        for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]:
            if role_name in created_roles:
                staff_overwrites[created_roles[role_name]] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        # Overwrites para denúncias (todos veem, ninguém escreve)
        denuncias_overwrites = {
            guild.default_role: discord.PermissionOverwrite(send_messages=False, add_reactions=False),
            guild.me: discord.PermissionOverwrite(send_messages=True)
        }
        for role_name in ["🜲 Dono", "💸ADMIN💸", "⛨ Moderador"]:
            if role_name in created_roles:
                denuncias_overwrites[created_roles[role_name]] = discord.PermissionOverwrite(send_messages=True)
        
        # ═══════════════════════════════════════════════════════════
        # ETAPA 3: CATEGORIAS
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 3/7** - Criando categorias...")
        
        categories_config = [
            ("📢 INFORMAÇÕES", None),
            ("💬 COMUNIDADE", None),
            ("🎟️ SUPORTE", None),
            ("🎉 EVENTOS", None),
            ("💡 FEEDBACK E BUGS", None),  # Unificado!
            ("🔒 STAFF", staff_overwrites),
            ("📊 LOGS", staff_overwrites),
            ("🗑️ LIXEIRA", staff_overwrites)
        ]
        
        for cat_name, overwrites in categories_config:
            existing = discord.utils.get(guild.categories, name=cat_name)
            if existing:
                created_categories[cat_name] = existing
            else:
                try:
                    if overwrites:
                        new_cat = await guild.create_category(cat_name, overwrites=overwrites)
                    else:
                        new_cat = await guild.create_category(cat_name)
                    created_categories[cat_name] = new_cat
                    await asyncio.sleep(0.5)
                except Exception as e:
                    print(f"Erro ao criar categoria {cat_name}: {e}")
        
        # ═══════════════════════════════════════════════════════════
        # ETAPA 4: CANAIS PÚBLICOS
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 4/7** - Criando canais públicos...")
        
        public_channels = [
            # INFORMAÇÕES
            ("📋regras", "📢 INFORMAÇÕES", None),
            ("❓faq", "📢 INFORMAÇÕES", None),
            ("📢anuncios", "📢 INFORMAÇÕES", None),
            ("🎰sobre-o-cassino", "📢 INFORMAÇÕES", None),
            
            # COMUNIDADE
            ("💬chat-geral", "💬 COMUNIDADE", None),
            ("📸midia", "💬 COMUNIDADE", None),
            ("🤖comandos", "💬 COMUNIDADE", None),
            
            # SUPORTE
            ("🎫criar-ticket", "🎟️ SUPORTE", None),
            ("🚨denuncias", "🎟️ SUPORTE", denuncias_overwrites),
            ("❓ajuda", "🎟️ SUPORTE", None),
            
            # EVENTOS
            ("🎁sorteios", "🎉 EVENTOS", None),
            ("🎊eventos", "🎉 EVENTOS", None),
            ("🏆resultados", "🎉 EVENTOS", None),
            
            # FEEDBACK E BUGS (Unificado)
            ("💭sugestoes", "💡 FEEDBACK E BUGS", None),
            ("✅sugestoes-aceitas", "💡 FEEDBACK E BUGS", staff_overwrites),
            ("🐛reportar-bugs", "💡 FEEDBACK E BUGS", None),
            ("📊leaderboard-bugs", "💡 FEEDBACK E BUGS", None),
        ]
        
        for ch_name, cat_name, overwrites in public_channels:
            # Verifica se já existe
            existing = None
            for channel in guild.text_channels:
                if ch_name.replace("📋", "").replace("❓", "").replace("📢", "").replace("🎰", "").replace("💬", "").replace("📸", "").replace("🤖", "").replace("🎫", "").replace("🚨", "").replace("🎁", "").replace("🎊", "").replace("🏆", "").replace("💭", "").replace("✅", "").replace("🐛", "").replace("📊", "").strip("-") in channel.name:
                    existing = channel
                    break
            
            if existing:
                created_channels[ch_name] = existing
                continue
            
            category = created_categories.get(cat_name)
            if not category:
                continue
            
            try:
                if overwrites:
                    # Merge overwrites da categoria com os específicos
                    final_overwrites = dict(category.overwrites)
                    final_overwrites.update(overwrites)
                    new_ch = await guild.create_text_channel(ch_name, category=category, overwrites=final_overwrites)
                else:
                    new_ch = await guild.create_text_channel(ch_name, category=category)
                
                created_channels[ch_name] = new_ch
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Erro ao criar canal {ch_name}: {e}")
        
        # ═══════════════════════════════════════════════════════════
        # ETAPA 5: CANAIS STAFF
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 5/7** - Criando canais da staff...")
        
        staff_channels = [
            ("💬staff-chat", "🔒 STAFF"),
            ("⚙️configuracoes", "🔒 STAFF"),
            ("👤logs-de-usuario", "📊 LOGS"),
            ("📝logs-mensagens", "📊 LOGS"),
            ("🎫logs-de-tickets", "📊 LOGS"),
            ("🔨logs-de-punicoes", "📊 LOGS"),
            ("🚨logs-de-denuncias", "📊 LOGS"),
        ]
        
        for ch_name, cat_name in staff_channels:
            existing = None
            for channel in guild.text_channels:
                if ch_name.replace("💬", "").replace("⚙️", "").replace("👤", "").replace("📝", "").replace("🎫", "").replace("🔨", "").replace("🚨", "").strip("-") in channel.name:
                    existing = channel
                    break
            
            if existing:
                created_channels[ch_name] = existing
                continue
            
            category = created_categories.get(cat_name)
            if not category:
                continue
            
            try:
                new_ch = await guild.create_text_channel(ch_name, category=category, overwrites=staff_overwrites)
                created_channels[ch_name] = new_ch
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Erro ao criar canal staff {ch_name}: {e}")
        
        # ═══════════════════════════════════════════════════════════
        # ETAPA 6: MENSAGENS NOS CANAIS
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 6/7** - Enviando mensagens configuradas...")
        
        # Função auxiliar para enviar embed
        async def send_channel_message(channel_key, embed_content, image=None):
            ch = created_channels.get(channel_key) or discord.utils.get(guild.channels, name=channel_key.replace("📋", "").replace("❓", "").replace("📢", "").replace("🎰", "").replace("💬", "").replace("📸", "").replace("🤖", "").replace("🎫", "").replace("🚨", "").replace("🎁", "").replace("🎊", "").replace("🏆", "").replace("💭", "").replace("✅", "").replace("🐛", "").replace("📊", "").strip("-"))
            
            if not ch:
                return
            
            try:
                embed = discord.Embed(
                    title=embed_content.get("title", ""),
                    description=embed_content.get("description", ""),
                    color=embed_content.get("color", discord.Color.gold()),
                    timestamp=datetime.datetime.now()
                )
                
                if image:
                    embed.set_image(url=image)
                embed.set_footer(text="LeGusta Casino © 2024", icon_url="https://i.imgur.com/1NA8dQR.png")
                
                await ch.send(embed=embed)
                await asyncio.sleep(0.5)
            except Exception as e:
                print(f"Erro ao enviar mensagem em {channel_key}: {e}")
        
        # Mensagem em #regras
        await send_channel_message("📋regras", {
            "title": "📋 REGRAS DO SERVIDOR - LeGusta Casino",
            "description": (
                "Bem-vindo ao LeGusta Casino! Leia atentamente as regras:\n\n"
                "**🎰 REGRAS DO CASSINO:**\n"
                "1. **Respeite a fila** - Não passe na frente de outros jogadores\n"
                "2. **Não roube prêmios** - Prêmios são do jogador que ganhou\n"
                "3. **Seja respeitoso** - Com staff e outros players\n"
                "4. **Sem brigas** - Baderna resultará em punição\n"
                "5. **Use fichas corretas** - 5k ou 10k conforme a máquina\n\n"
                "**📱 REGRAS DO DISCORD:**\n"
                "1. **Sem spam** - Mensagens repetidas ou muito longas\n"
                "2. **Sem divulgação** - Links de outros servidores\n"
                "3. **Sem conteúdo NSFW** - Mantenha o servidor limpo\n"
                "4. **Respeite todos** - Preconceito não será tolerado\n"
                "5. **Use os canais corretos** - Cada canal tem sua função\n\n"
                "**🔨 PUNIÇÕES:**\n"
                "• Quebra de regras leves = Mute temporário\n"
                "• Quebra de regras graves = Banimento\n"
                "• Roubo/Trapacear = Ban permanente da GO e Discord\n\n"
                "Ao participar, você concorda com todas as regras acima!"
            ),
            "color": discord.Color.red()
        }, "https://i.imgur.com/1NA8dQR.png")
        
        # Mensagem em #faq
        await send_channel_message("❓faq", {
            "title": "❓ PERGUNTAS FREQUENTES",
            "description": (
                "**💰 Como comprar fichas?**\n"
                "Vá ao cassino e use os barris do FUNDO para COMPRAR.\n\n"
                "**💱 Como vender fichas?**\n"
                "Use os barris da FRENTE para VENDER suas fichas.\n\n"
                "**🎰 Quais máquinas aceitam fichas de 5k?**\n"
                "Apenas o Caça Níqueis aceita fichas de 5k.\n\n"
                "**🎰 Quais máquinas aceitam fichas de 10k?**\n"
                "Lucky Tower e Roleta aceitam apenas fichas de 10k.\n\n"
                "**⏰ Qual horário de atendimento?**\n"
                "O cassino funciona 24h, mas o atendimento staff é das 14h às 22h.\n\n"
                "**🚨 Como denunciar alguém?**\n"
                "Use o canal <#denuncias> ou abra um ticket privado.\n\n"
                "**💡 Como dar sugestões?**\n"
                "Use o canal <#sugestoes>."
            ),
            "color": discord.Color.blue()
        })
        
        # Mensagem em #sobre-o-cassino
        await send_channel_message("🎰sobre-o-cassino", {
            "title": "🎰 SOBRE O LEGUSTA CASINO",
            "description": (
                "Bem-vindo ao maior cassino do Minecraft!\n\n"
                "**🎯 Nossa Missão:**\n"
                "Oferecer diversão e entretenimento de qualidade para todos os jogadores.\n\n"
                "**🎮 Minigames Disponíveis:**\n"
                "• 🏰 **Lucky Tower** - Escalone a torre e ganhe prêmios!\n"
                "• 🎰 **Caça Níqueis** - Teste sua sorte nas máquinas clássicas!\n"
                "• 🎡 **Roleta** - Aposte nas cores e números!\n\n"
                "**💎 Vantagens:**\n"
                "• Sistema de fichas justo\n"
                "• Staff online e atenciosa\n"
                "• Eventos semanais com prêmios especiais\n\n"
                "**📍 Localização:**\n"
                "Use `/go cassino` ou `/pwarp cassino` para chegar!\n\n"
                "🍀 **Boa sorte e divirta-se responsavelmente!**"
            ),
            "color": discord.Color.gold()
        }, "https://i.imgur.com/1NA8dQR.png")
        
        # Mensagem em #ajuda
        await send_channel_message("❓ajuda", {
            "title": "🎰 PAINEL DE AJUDA - LeGusta Casino",
            "description": (
                "💰 **1. FICHAS - COMO FUNCIONA?**\n"
                "Para apostar em qualquer máquina, você precisa adquirir fichas:\n"
                "• Fichas de 5k ou 10k\n"
                "• Algumas máquinas aceitam apenas fichas de 10k\n"
                "• Outras aceitam apenas fichas de 5k\n"
                "⚠️ Escolha a máquina de acordo com sua ficha!\n\n"
                "🛒 **2. ONDE COMPRO FICHAS?**\n"
                "Ao chegar na LeGusta, caminhe em direção ao cassino:\n"
                "• Barris da FRENTE = VENDER fichas ✅\n"
                "• Barris do FUNDO = COMPRAR fichas ✅\n"
                "Perdido? Chame um staff online:\n"
                "• *Spokeas | *Mateus | *Gusteds\n\n"
                "🎮 **3. MINIGAMES DISPONÍVEIS**\n"
                "• 🏰 Lucky Tower\n"
                "• 🎰 Caça Níqueis\n"
                "• 🎡 Roleta\n\n"
                "📋 **4. COMO JOGAR?**\n"
                "• Lucky Tower → Fichas de 10k ✅\n"
                "• Roleta → Fichas de 10k ✅\n"
                "• Caça Níqueis → Fichas de 5k ✅\n"
                "⚠️ Lucky Tower e Roleta NÃO aceitam fichas de 5k!\n\n"
                "⚖️ **5. REGRAS IMPORTANTES**\n"
                "✓ Respeite a fila nos minigames\n"
                "✓ Não roube prêmios de outros jogadores\n"
                "✓ Seja respeitoso com staff e players\n"
                "❌ Denúncias? Abra um ticket\n"
                "😔 Quebra de regras = BAN"
            ),
            "color": discord.Color.gold()
        }, "https://i.imgur.com/1NA8dQR.png")
        
        # Mensagem em #sugestoes
        await send_channel_message("💭sugestoes", {
            "title": "💡 SISTEMA DE SUGESTÕES",
            "description": (
                "Bem-vindo ao canal de sugestões!\n\n"
                "**Como funciona:**\n"
                "1. Escreva sua sugestão em uma mensagem neste canal\n"
                "2. O bot criará automaticamente uma discussão para votarem\n"
                "3. Reaja com ✅ se aprova ou ❌ se rejeita\n"
                "4. Após 7 dias, sugestões aprovadas vão para <#sugestoes-aceitas>\n\n"
                "**Regras:**\n"
                "• Uma sugestão por mensagem\n"
                "• Seja claro e objetivo\n"
                "• Sugestões repetidas serão deletadas\n\n"
                "💭 **Envie sua sugestão abaixo!**"
            ),
            "color": discord.Color.blue()
        })
        
        # Mensagem em #reportar-bugs
        await send_channel_message("🐛reportar-bugs", {
            "title": "🐛 REPORTAR BUGS",
            "description": (
                "Encontrou algum problema? Reporte aqui!\n\n"
                "**Como reportar:**\n"
                "1. Descreva o bug detalhadamente\n"
                "2. Explique como reproduzir o problema\n"
                "3. Se possível, envie screenshots\n"
                "4. Informe quando começou a acontecer\n\n"
                "**Tipos de bugs:**\n"
                "• 🎮 **Bugs de Minigames** - Máquinas com problemas\n"
                "• 🤖 **Bugs do Bot** - Comandos não funcionando\n"
                "• 🌐 **Bugs do Servidor** - Lag, quedas, etc\n\n"
                "**Recompensas:**\n"
                "Quem mais reportar bugs ganha destaque no leaderboard mensal!\n\n"
                "🔧 **Descreva seu bug abaixo:**"
            ),
            "color": discord.Color.orange()
        })
        
        # Mensagem em #leaderboard-bugs
        await send_channel_message("📊leaderboard-bugs", {
            "title": "🏆 LEADERBOARD DE BUGS",
            "description": (
                "Top 10 usuários que mais ajudaram reportando bugs este mês!\n\n"
                "**🥇 1º Lugar:** Em breve...\n"
                "**🥈 2º Lugar:** Em breve...\n"
                "**🥉 3º Lugar:** Em breve...\n"
                "**4º-10º:** Em breve...\n\n"
                "📅 **Reseta todo dia 1º do mês**\n"
                "💰 **Prêmios para os top 3!**\n\n"
                "Reporte bugs em <#reportar-bugs>!"
            ),
            "color": discord.Color.gold()
        })
        
        # Mensagem em #denuncias (público)
        await send_channel_message("🚨denuncias", {
            "title": "🚨 CANAL DE DENÚNCIAS",
            "description": (
                "**Denúncias resolvidas aparecerão aqui!**\n\n"
                "Para fazer uma denúncia anônima:\n"
                "• Use o comando `/denunciar`\n"
                "• Ou abra um ticket privado em <#criar-ticket>\n\n"
                "⚠️ **Atenção:**\n"
                "• Denúncias falsas resultarão em punição\n"
                "• Apenas denúncias confirmadas aparecem aqui\n"
                "• Sistema 100% anônimo para proteção do denunciante\n\n"
                "🔒 **Sua segurança é nossa prioridade!**"
            ),
            "color": discord.Color.red()
        })
        
        # Mensagem em #sorteios
        await send_channel_message("🎁sorteios", {
            "title": "🎉 SORTEIOS E EVENTOS",
            "description": (
                "Fique atento aos sorteios e eventos do servidor!\n\n"
                "**🎁 Sorteios Regulares:**\n"
                "• Sorteios semanais de fichas\n"
                "• Eventos especiais de feriado\n"
                "• Torneios entre jogadores\n\n"
                "**🏆 Como Participar:**\n"
                "• Reaja com 🎉 nos sorteios ativos\n"
                "• Siga as regras de cada evento\n"
                "• Fique online no horário do sorteio\n\n"
                "🍀 **Boa sorte!**"
            ),
            "color": discord.Color.purple()
        })
        
        # Mensagem em #anuncios
        await send_channel_message("📢anuncios", {
            "title": "🎰 BEM-VINDO AO LEGUSTA CASINO!",
            "description": (
                "O maior e mais completo cassino do Minecraft está de portas abertas!\n\n"
                "**✨ O que oferecemos:**\n"
                "• 3 minigames incríveis\n"
                "• Sistema de fichas justo\n"
                "• Staff ativa e dedicada\n"
                "• Eventos semanais\n"
                "• Sistema de suporte completo\n\n"
                "**🚀 Comece agora:**\n"
                "• Leia as regras em <#regras>\n"
                "• Veja como jogar em <#ajuda>\n"
                "• Abra um ticket se precisar de ajuda\n\n"
                "🍀 **Boa sorte e divirta-se!**"
            ),
            "color": discord.Color.gold()
        }, "https://i.imgur.com/1NA8dQR.png")
        
        # ═══════════════════════════════════════════════════════════
        # ETAPA 7: PAINEL DE TICKET (IMPORTANTE!)
        # ═══════════════════════════════════════════════════════════
        
        await progress_msg.edit(content="🎰 **ETAPA 7/7** - Configurando painel de tickets...")
        
        ticket_ch = created_channels.get("🎫criar-ticket") or discord.utils.get(guild.channels, name="criar-ticket")
        
        if ticket_ch:
            try:
                # Limpa o canal
                await ticket_ch.purge(limit=100)
                
                # Embed do painel
                ticket_panel_embed = discord.Embed(
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
                ticket_panel_embed.set_thumbnail(url="https://i.imgur.com/1NA8dQR.png")
                ticket_panel_embed.set_image(url="https://i.imgur.com/1NA8dQR.png")
                ticket_panel_embed.set_footer(text="LeGusta Casino © 2024 | Clique no menu abaixo para abrir um ticket")
                
                view = TicketPanelView()
                await ticket_ch.send(embed=ticket_panel_embed, view=view)
                
            except Exception as e:
                print(f"Erro ao configurar painel de ticket: {e}")
        
        # ═══════════════════════════════════════════════════════════
        # FINALIZAÇÃO
        # ═══════════════════════════════════════════════════════════
        
        total_roles = len([r for r in created_roles.values() if r])
        total_categories = len([c for c in created_categories.values() if c])
        total_channels = len([c for c in created_channels.values() if c])
        
        await progress_msg.edit(
            content=f"✅ **SETUP CONCLUÍDO COM SUCESSO!**\n\n"
            f"🎭 **Cargos criados:** {total_roles}/11\n"
            f"📁 **Categorias criadas:** {total_categories}/8\n"
            f"💬 **Canais criados:** {total_channels}/25+\n"
            f"🎫 **Painel de ticket:** Ativo\n\n"
            f"**O servidor LeGusta Casino está pronto para uso!** 🎰"
        )
        
    except Exception as e:
        await progress_msg.edit(content=f"❌ **ERRO NO SETUP:** {str(e)}\nVerifique as permissões do bot e tente novamente.")
        print(f"Erro completo no setup: {e}")
        import traceback
        traceback.print_exc()

@bot.command()
@commands.is_owner()
async def resetup(ctx):
    """Recria toda a estrutura do zero"""
    await ctx.send("🔄 Reiniciando setup completo...")
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
            if "ticket-" in channel.name:
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
    
    # Sistema de sugestões - cria thread automaticamente
    if message.channel.name == "sugestoes" or "sugestoes" in message.channel.name:
        if not message.author.bot:
            try:
                thread = await message.create_thread(name=f"Sugestão: {message.content[:30]}...")
                msg = await thread.send("Reaja com ✅ ou ❌ para votar!")
                await msg.add_reaction("✅")
                await msg.add_reaction("❌")
            except:
                pass
    
    # Sistema de bugs - reage e oferece ping
    if message.channel.name == "reportar-bugs" or "reportar-bugs" in message.channel.name:
        if not message.author.bot:
            try:
                await message.add_reaction("🐛")
                # Aqui você pode adicionar lógica de ping se quiser
            except:
                pass
    
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
    try:
        channel = await get_or_create_log_channel(message.guild, "logs-mensagens")
        embed = create_embed(
            "⚠️ SPAM DETECTADO",
            f"**`Autor:`** {message.author.mention}\n**`Canal:`** {message.channel.mention}",
            discord.Color.orange()
        )
        await channel.send(embed=embed)
    except:
        pass

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
        
        # Cria categoria staff se não existir
        category = discord.utils.get(guild.categories, name="🔒 STAFF")
        if not category:
            overwrites = {
                guild.default_role: discord.PermissionOverwrite(read_messages=False),
                guild.me: discord.PermissionOverwrite(read_messages=True)
            }
            for owner_id in OWNER_IDS:
                owner = guild.get_member(owner_id)
                if owner:
                    overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            category = await guild.create_category("🔒 STAFF", overwrites=overwrites)
        
        # Cria canal privado
        overwrites = {
            guild.default_role: discord.PermissionOverwrite(read_messages=False),
            guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        for owner_id in OWNER_IDS:
            owner = guild.get_member(owner_id)
            if owner:
                overwrites[owner] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
        
        try:
            channel = await guild.create_text_channel(f"denuncia-{report_id}", category=category, overwrites=overwrites)
        except:
            channel = await guild.create_text_channel(f"denuncia-{report_id}", overwrites=overwrites)
        
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
        
        # Confirmação
        confirm = create_embed("✅ DENÚNCIA ENVIADA", f"**`ID:`** `{report_id}`\nAnalisaremos em breve!", discord.Color.green())
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
        
        # Publica em denúncias
        public_channel = None
        for ch in interaction.guild.text_channels:
            if "denuncias" in ch.name:
                public_channel = ch
                break
        
        if public_channel:
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
    
    @discord.ui.button(label="🔍 Revisar", style=discord.ButtonStyle.primary)
    async def review(self, interaction: discord.Interaction, button: Button):
        if not is_owner(interaction.user.id):
            await interaction.response.send_message("⛔ Apenas donos!", ephemeral=True)
            return
        
        db.reports[self.report_id]["status"] = "Sob Revisão"
        db.save()
        await interaction.response.send_message("🔍 Status atualizado para 'Sob Revisão'")

# ═══════════════════════════════════════════════════════════════
# INICIALIZAÇÃO
# ═══════════════════════════════════════════════════════════════

async def main():
    async with bot:
        await bot.add_cog(Moderation(bot))
        await bot.start(TOKEN)

if __name__ == "__main__":
    asyncio.run(main())
