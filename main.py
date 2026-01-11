import discord
from discord.ext import commands
from discord import app_commands
import datetime
import io
import json
import os
from flask import Flask
from threading import Thread
import asyncio

# ==========================================
# CONFIGURACIÓN BASE
# ==========================================
TOKEN = os.environ.get('TOKEN')
OWNER_ID = 1057435948998217778  # <--- Cambia esto por tu ID de Discord
LICENSES_FILE = "licencias.json"
CONFIG_FILE = "config_servidores.json"
STATS_FILE = "stats.json"

# --- Utilidades de Datos ---
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_data(file, data):
    with open(file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

def get_guild_config(guild_id):
    configs = load_data(CONFIG_FILE)
    gid = str(guild_id)
    default = {
        "panel_title": "TICKET STREAK.XIT",
        "panel_description": "Selecciona una opción abajo para abrir un ticket.",
        "welcome_title": "TICKET ABIERTO",
        "welcome_description": "Bienvenido. El staff te atenderá pronto.",
        "color": 0x5865F2,
        "staff_role": None,
        "logs_channel": None,
        "feedback_channel": None,
        "category_open": None,
        "category_claimed": None,
        "options": [{"label": "Soporte", "description": "Ayuda técnica", "emoji": "🛠️", "value": "soporte"}],
        "btn_claim_txt": "Asumir", "btn_claim_emoji": "🙋‍♂️",
        "btn_hold_txt": "En Espera", "btn_hold_emoji": "⏳",
        "btn_add_txt": "Añadir", "btn_add_emoji": "👤",
        "btn_call_txt": "Llamar Staff", "btn_call_emoji": "🔔",
        "btn_close_txt": "Cerrar", "btn_close_emoji": "🔒"
    }
    if gid not in configs:
        return default
    for k, v in default.items():
        if k not in configs[gid]:
            configs[gid][k] = v
    return configs[gid]

def is_licensed(guild_id):
    lics = load_data(LICENSES_FILE)
    gid = str(guild_id)
    if gid not in lics:
        return False
    try:
        return datetime.datetime.strptime(lics[gid], "%Y-%m-%d") > datetime.datetime.now()
    except:
        return False

async def check_license(it: discord.Interaction):
    if not is_licensed(it.guild_id):
        embed = discord.Embed(
            title="❌ Licencia Expirada",
            description="Este servidor no cuenta con una suscripción activa.",
            color=discord.Color.red()
        )
        if not it.response.is_done():
            await it.response.send_message(embed=embed, ephemeral=True)
        return False
    return True

def add_staff_point(user_id):
    stats = load_data(STATS_FILE)
    uid = str(user_id)
    pts = stats.get(uid, 0)
    stats[uid] = (pts if isinstance(pts, int) else 0) + 1
    save_data(STATS_FILE, stats)

# ==========================================
# GENERADOR DE TRANSCRIPT HTML
# ==========================================

async def generate_html_transcript(channel, guild_name):
    messages = []
    async for m in channel.history(limit=None, oldest_first=True):
        messages.append(m)
    
    html_content = f"""
    <!DOCTYPE html>
    <html lang="es">
    <head>
        <meta charset="UTF-8">
        <style>
            body {{ background-color: #36393f; color: #dcddde; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; padding: 20px; }}
            .header {{ border-bottom: 1px solid #4f545c; padding-bottom: 10px; margin-bottom: 20px; }}
            .message {{ display: flex; margin-bottom: 15px; }}
            .avatar {{ width: 40px; height: 40px; border-radius: 50%; margin-right: 15px; }}
            .content {{ display: flex; flex-direction: column; }}
            .author {{ font-weight: bold; color: #ffffff; margin-bottom: 5px; }}
            .timestamp {{ font-size: 0.75rem; color: #72767d; margin-left: 10px; font-weight: normal; }}
            .text {{ line-height: 1.4; }}
            .embed {{ background-color: #2f3136; border-left: 4px solid #5865f2; padding: 10px; margin-top: 5px; border-radius: 4px; }}
        </style>
        <title>Transcript - {channel.name}</title>
    </head>
    <body>
        <div class="header">
            <h1>Transcript: {channel.name}</h1>
            <p>Servidor: {guild_name} | Fecha: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        </div>
    """
    
    for m in messages:
        avatar_url = m.author.display_avatar.url
        ts = m.created_at.strftime("%d/%m/%Y %H:%M")
        content = m.content.replace("\n", "<br>")
        
        html_content += f"""
        <div class="message">
            <img class="avatar" src="{avatar_url}" alt="avatar">
            <div class="content">
                <div class="author">{m.author.display_name}<span class="timestamp">{ts}</span></div>
                <div class="text">{content}</div>
        """
        
        for embed in m.embeds:
            html_content += f'<div class="embed">'
            if embed.title: html_content += f'<strong>{embed.title}</strong><br>'
            if embed.description: html_content += f'{embed.description}'
            html_content += '</div>'
            
        html_content += "</div></div>"
        
    html_content += "</body></html>"
    return html_content

# ==========================================
# VISTAS Y MODALES
# ==========================================

class AppearanceModal(discord.ui.Modal, title="Editar Apariencia"):
    p_title = discord.ui.TextInput(label="Título Panel Principal")
    p_desc = discord.ui.TextInput(label="Descripción Panel Principal", style=discord.TextStyle.paragraph)
    w_title = discord.ui.TextInput(label="Título Bienvenida Ticket")
    w_desc = discord.ui.TextInput(label="Descripción Bienvenida Ticket", style=discord.TextStyle.paragraph)
    color = discord.ui.TextInput(label="Color Hex (ej: #5865F2)", max_length=7)

    def __init__(self, guild_id):
        super().__init__()
        self.gid = str(guild_id)
        cfg = get_guild_config(guild_id)
        self.p_title.default = cfg["panel_title"]
        self.p_desc.default = cfg["panel_description"]
        self.w_title.default = cfg["welcome_title"]
        self.w_desc.default = cfg["welcome_description"]
        self.color.default = f"#{cfg['color']:06x}"

    async def on_submit(self, it: discord.Interaction):
        cfgs = load_data(CONFIG_FILE)
        c = cfgs.get(self.gid, get_guild_config(self.gid))
        c.update({"panel_title": self.p_title.value, "panel_description": self.p_desc.value, "welcome_title": self.w_title.value, "welcome_description": self.w_desc.value})
        try: c["color"] = int(self.color.value.replace("#", ""), 16)
        except: pass
        cfgs[self.gid] = c
        save_data(CONFIG_FILE, cfgs)
        await it.response.send_message("✅ Apariencia actualizada.", ephemeral=True)

class TechnicalModal(discord.ui.Modal, title="Ajustes Técnicos"):
    staff_role = discord.ui.TextInput(label="ID Rol Staff", required=False)
    logs_chan = discord.ui.TextInput(label="ID Canal Logs", required=False)
    feed_chan = discord.ui.TextInput(label="ID Canal Feedback", required=False)
    cat_open = discord.ui.TextInput(label="ID Categoría Abiertos", required=False)
    cat_claim = discord.ui.TextInput(label="ID Categoría Asumidos", required=False)

    def __init__(self, guild_id):
        super().__init__()
        self.gid = str(guild_id)
        cfg = get_guild_config(guild_id)
        self.staff_role.default = str(cfg["staff_role"]) if cfg["staff_role"] else ""
        self.logs_chan.default = str(cfg["logs_channel"]) if cfg["logs_channel"] else ""
        self.feed_chan.default = str(cfg["feedback_channel"]) if cfg["feedback_channel"] else ""
        self.cat_open.default = str(cfg["category_open"]) if cfg["category_open"] else ""
        self.cat_claim.default = str(cfg["category_claimed"]) if cfg["category_claimed"] else ""

    async def on_submit(self, it: discord.Interaction):
        cfgs = load_data(CONFIG_FILE)
        c = cfgs.get(self.gid, get_guild_config(self.gid))
        c.update({
            "staff_role": self.staff_role.value if self.staff_role.value else None,
            "logs_channel": self.logs_chan.value if self.logs_chan.value else None,
            "feedback_channel": self.feed_chan.value if self.feed_chan.value else None,
            "category_open": self.cat_open.value if self.cat_open.value else None,
            "category_claimed": self.cat_claim.value if self.cat_claim.value else None
        })
        cfgs[self.gid] = c
        save_data(CONFIG_FILE, cfgs)
        await it.response.send_message("✅ Ajustes técnicos actualizados.", ephemeral=True)

class ConfigMainView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        self.gid = guild_id

    @discord.ui.button(label="📝 Apariencia", style=discord.ButtonStyle.primary)
    async def appearance(self, it: discord.Interaction, b: discord.ui.Button):
        await it.response.send_modal(AppearanceModal(self.gid))

    @discord.ui.button(label="⚙️ Ajustes Técnicos", style=discord.ButtonStyle.secondary)
    async def technical(self, it: discord.Interaction, b: discord.ui.Button):
        await it.response.send_modal(TechnicalModal(self.gid))

# ==========================================
# SISTEMA DE TICKETS
# ==========================================

class FeedbackView(discord.ui.View):
    def __init__(self, channel_id):
        super().__init__(timeout=None)
        self.cid = channel_id

    @discord.ui.button(emoji="😍", custom_id="star_5", style=discord.ButtonStyle.gray)
    async def s5(self, it: discord.Interaction, b: discord.ui.Button):
        await it.response.send_message("¡Gracias por tu calificación!", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None)
        cfg = get_guild_config(guild_id)
        self.add_item(discord.ui.Button(label=cfg["btn_claim_txt"], emoji=cfg["btn_claim_emoji"], style=discord.ButtonStyle.success, custom_id="claim_t"))
        self.add_item(discord.ui.Button(label=cfg["btn_hold_txt"], emoji=cfg["btn_hold_emoji"], style=discord.ButtonStyle.secondary, custom_id="hold_t"))
        self.add_item(discord.ui.Button(label=cfg["btn_add_txt"], emoji=cfg["btn_add_emoji"], style=discord.ButtonStyle.primary, custom_id="add_t"))
        self.add_item(discord.ui.Button(label=cfg["btn_call_txt"], emoji=cfg["btn_call_emoji"], style=discord.ButtonStyle.warning, custom_id="call_t"))
        self.add_item(discord.ui.Button(label=cfg["btn_close_txt"], emoji=cfg["btn_close_emoji"], style=discord.ButtonStyle.danger, custom_id="close_t"))

    async def interaction_check(self, it: discord.Interaction) -> bool:
        custom_id = it.data.get('custom_id')
        cfg = get_guild_config(it.guild_id)
        
        if custom_id == "claim_t":
            add_staff_point(it.user.id)
            if cfg["category_claimed"]:
                try:
                    cat = it.guild.get_channel(int(cfg["category_claimed"]))
                    if cat: await it.channel.edit(category=cat)
                except: pass
            await it.response.send_message(f"✅ {it.user.mention} ha asumido el ticket.")
            
        elif custom_id == "hold_t":
            await it.response.send_message(f"⏳ El ticket ha sido puesto **en espera** por {it.user.mention}.")
            
        elif custom_id == "add_t":
            await it.response.send_message("Menciona al usuario que quieres añadir a este ticket.", ephemeral=True)
            
        elif custom_id == "call_t":
            role_mention = f"<@&{cfg['staff_role']}>" if cfg["staff_role"] else "@here"
            await it.response.send_message(f"🚨 {it.user.mention} está solicitando asistencia de staff! {role_mention}")
            
        elif custom_id == "close_t":
            await self.close_ticket(it)
            
        return True

    async def close_ticket(self, it: discord.Interaction):
        cfg = get_guild_config(it.guild_id)
        await it.response.send_message("Generando transcript HTML y cerrando ticket...", ephemeral=True)
        
        # Transcript HTML
        html_data = await generate_html_transcript(it.channel, it.guild.name)
        file = discord.File(io.BytesIO(html_data.encode()), filename=f"transcript-{it.channel.name}.html")
        
        # Enviar a Logs
        if cfg["logs_channel"]:
            try:
                log_chan = it.guild.get_channel(int(cfg["logs_channel"]))
                if log_chan:
                    embed = discord.Embed(title="Ticket Cerrado", color=discord.Color.red())
                    embed.add_field(name="Canal", value=it.channel.name)
                    embed.add_field(name="Cerrado por", value=it.user.mention)
                    await log_chan.send(embed=embed, file=file)
            except: pass
            
        # Enviar Feedback
        if cfg["feedback_channel"]:
            try:
                feed_chan = it.guild.get_channel(int(cfg["feedback_channel"]))
                if feed_chan:
                    await feed_chan.send(f"¿Cómo fue tu atención en el ticket de {it.user.mention}?", view=FeedbackView(it.channel.id))
            except: pass

        await asyncio.sleep(3)
        await it.channel.delete()

class TicketSelect(discord.ui.Select):
    def __init__(self, guild_id):
        cfg = get_guild_config(guild_id)
        options = []
        for opt in cfg["options"]:
            options.append(discord.SelectOption(label=opt["label"], description=opt.get("description"), emoji=opt.get("emoji"), value=opt["value"]))
        super().__init__(placeholder="Selecciona una categoría...", options=options, custom_id="ticket_select")

    async def callback(self, it: discord.Interaction):
        cfg = get_guild_config(it.guild_id)
        overwrites = {
            it.guild.default_role: discord.PermissionOverwrite(read_messages=False),
            it.user: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            it.guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
        }
        if cfg["staff_role"]:
            try:
                role = it.guild.get_role(int(cfg["staff_role"]))
                if role: overwrites[role] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
            except: pass

        category = None
        if cfg["category_open"]:
            try: category = it.guild.get_channel(int(cfg["category_open"]))
            except: pass

        chan = await it.guild.create_text_channel(f"ticket-{it.user.name}", category=category, overwrites=overwrites)
        await it.response.send_message(f"Ticket creado: {chan.mention}", ephemeral=True)
        
        embed = discord.Embed(title=cfg["welcome_title"], description=cfg["welcome_description"], color=cfg["color"])
        await chan.send(content=f"{it.user.mention} Bienvenido.", embed=embed, view=TicketControlView(it.guild_id))

# ==========================================
# CLASE DEL BOT
# ==========================================

class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.members = True
        super().__init__(command_prefix="+", intents=intents)

    async def setup_hook(self):
        self.add_view(TicketControlView(0)) 
        print("Sincronizando comandos slash...")
        await self.tree.sync()

bot = TicketBot()

@bot.event
async def on_ready():
    print(f"Bot conectado como {bot.user}")
    print("TICKET STREAK.XIT ONLINE")

# ==========================================
# COMANDOS DE PREFIJO (+)
# ==========================================

@bot.command()
async def ping(ctx):
    latency = round(bot.latency * 1000)
    await ctx.send(f"🏓 ¡Pong! Latencia: {latency}ms")

@bot.command()
async def activar(ctx, gid: str = None):
    if ctx.author.id != OWNER_ID: return
    if not gid: gid = str(ctx.guild.id)
    lics = load_data(LICENSES_FILE)
    exp = datetime.datetime.now() + datetime.timedelta(days=30)
    lics[gid] = exp.strftime("%Y-%m-%d")
    save_data(LICENSES_FILE, lics)
    await ctx.send(f"✅ Servidor {gid} activado por 30 días.")

@bot.command()
async def close(ctx):
    if "ticket-" in ctx.channel.name:
        await ctx.send("Cerrando ticket en 5 segundos...")
        await asyncio.sleep(5)
        await ctx.channel.delete()
    else:
        await ctx.send("Este comando solo puede usarse en canales de tickets.", delete_after=5)

@bot.command()
@commands.is_owner()
async def sync(ctx):
    await bot.tree.sync()
    await ctx.send("Comandos sincronizados.")

# ==========================================
# COMANDOS SLASH (/)
# ==========================================

@bot.tree.command(name="setup", description="Envía el panel de tickets")
@app_commands.checks.has_permissions(administrator=True)
async def setup(it: discord.Interaction):
    if not await check_license(it): return
    cfg = get_guild_config(it.guild_id)
    view = discord.ui.View(timeout=None).add_item(TicketSelect(it.guild_id))
    embed = discord.Embed(title=cfg["panel_title"], description=cfg["panel_description"], color=cfg["color"])
    await it.channel.send(embed=embed, view=view)
    await it.response.send_message("✅ Panel de tickets enviado.", ephemeral=True)

@bot.tree.command(name="config", description="Configura el bot")
@app_commands.checks.has_permissions(administrator=True)
async def config(it: discord.Interaction):
    if not await check_license(it): return
    await it.response.send_message("Panel de Configuración:", view=ConfigMainView(it.guild_id), ephemeral=True)

# ==========================================
# SERVIDOR WEB PARA RENDER (KEEP ALIVE)
# ==========================================
web_app = Flask('')
@web_app.route('/')
def home(): return "TICKET STREAK.XIT ONLINE"
def run_web():
    port = int(os.environ.get('PORT', 8080))
    web_app.run(host='0.0.0.0', port=port)

if __name__ == "__main__":
    t = Thread(target=run_web)
    t.daemon = True
    t.start()
    if not TOKEN: print("ERROR: No se encontró el TOKEN.")
    else: bot.run(TOKEN)
