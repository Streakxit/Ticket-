import discord
from discord.ext import commands
from discord import app_commands
import datetime
import io
import json
import os
from flask import Flask
from threading import Thread

# ==========================================
# SERVIDOR WEB PARA RENDER (KEEP ALIVE)
# ==========================================
app = Flask('')
@app.route('/')
def home(): return "TICKET STREAK.XIT ONLINE"

def run():
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 8080))

def keep_alive():
    t = Thread(target=run)
    t.start()

# ==========================================
# CONFIGURACIÓN BASE
# ==========================================
TOKEN = os.environ.get('TOKEN') # Se saca de las variables de entorno de Render
OWNER_ID = 123456789012345678  # <--- PON TU ID DE DISCORD AQUÍ
LICENSES_FILE = "licencias.json"
CONFIG_FILE = "config_servidores.json"
STATS_FILE = "stats.json"

# --- Utilidades de Datos ---
def load_data(file):
    if os.path.exists(file):
        try:
            with open(file, "r") as f: return json.load(f)
        except: return {}
    return {}

def save_data(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=4)

def get_guild_config(guild_id):
    configs = load_data(CONFIG_FILE); gid = str(guild_id)
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
    if gid not in configs: return default
    for k, v in default.items():
        if k not in configs[gid]: configs[gid][k] = v
    return configs[gid]

def is_licensed(guild_id):
    lics = load_data(LICENSES_FILE); gid = str(guild_id)
    if gid not in lics: return False
    try:
        return datetime.datetime.strptime(lics[gid], "%Y-%m-%d") > datetime.datetime.now()
    except: return False

async def check_license(it):
    if not is_licensed(it.guild_id):
        await it.response.send_message(embed=discord.Embed(title="❌ Licencia Expirada", description="Este servidor no cuenta con una suscripción activa.", color=discord.Color.red()), ephemeral=True)
        return False
    return True

def add_staff_point(user_id):
    stats = load_data(STATS_FILE); uid = str(user_id)
    pts = stats.get(uid, 0)
    stats[uid] = (pts if isinstance(pts, int) else 0) + 1
    save_data(STATS_FILE, stats)

async def generate_transcript(channel):
    messages = []
    async for m in channel.history(limit=None, oldest_first=True):
        ts = m.created_at.strftime("%Y-%m-%d %H:%M:%S")
        content = m.content if m.content else "[Archivo/Embed]"
        messages.append(f"[{ts}] {m.author.display_name}: {content}")
    return "\n".join(messages)

# ==========================================
# VISTAS DE CONFIGURACIÓN
# ==========================================
class AppearanceModal(discord.ui.Modal, title="Editar Apariencia"):
    p_title = discord.ui.TextInput(label="Título Panel Principal")
    p_desc = discord.ui.TextInput(label="Descripción Panel Principal", style=discord.TextStyle.paragraph)
    w_title = discord.ui.TextInput(label="Título Bienvenida Ticket")
    w_desc = discord.ui.TextInput(label="Descripción Bienvenida Ticket", style=discord.TextStyle.paragraph)
    color = discord.ui.TextInput(label="Color Hex (ej: #5865F2)", max_length=7)

    def __init__(self, guild_id):
        super().__init__(); self.gid = str(guild_id); cfg = get_guild_config(guild_id)
        self.p_title.default, self.p_desc.default = cfg["panel_title"], cfg["panel_description"]
        self.w_title.default, self.w_desc.default = cfg["welcome_title"], cfg["welcome_description"]
        self.color.default = hex(cfg["color"]).replace("0x", "#")

    async def on_submit(self, it):
        cfgs = load_data(CONFIG_FILE); c = cfgs.get(self.gid, get_guild_config(self.gid))
        c.update({"panel_title": self.p_title.value, "panel_description": self.p_desc.value, "welcome_title": self.w_title.value, "welcome_description": self.w_desc.value})
        try: c["color"] = int(self.color.value.replace("#", ""), 16)
        except: pass
        cfgs[self.gid] = c; save_data(CONFIG_FILE, cfgs)
        await it.response.send_message("✅ Apariencia actualizada.", ephemeral=True)

class ConfigMainView(discord.ui.View):
    def __init__(self, guild_id): super().__init__(timeout=None); self.gid = guild_id
    @discord.ui.button(label="📝 Apariencia", style=discord.ButtonStyle.primary)
    async def appearance(self, it, b): await it.response.send_modal(AppearanceModal(self.gid))
    @discord.ui.button(label="⚙️ Ajustes Técnicos", style=discord.ButtonStyle.secondary)
    async def technical(self, it, b): await it.response.send_message("Configura canales y roles en el panel.", ephemeral=True)

# ==========================================
# SISTEMA DE TICKETS
# ==========================================
class FeedbackView(discord.ui.View):
    def __init__(self, channel_id): super().__init__(timeout=None); self.cid = channel_id
    @discord.ui.button(emoji="😍", custom_id="star_5")
    async def s5(self, it, b): await it.response.send_message("¡Gracias por tu calificación!", ephemeral=True)

class TicketControlView(discord.ui.View):
    def __init__(self, guild_id):
        super().__init__(timeout=None); cfg = get_guild_config(guild_id)
        self.add_item(discord.ui.Button(label=cfg["btn_claim_txt"], emoji=cfg["btn_claim_emoji"], style=discord.ButtonStyle.success, custom_id="claim_t"))
        self.add_item(discord.ui.Button(label=cfg["btn_close_txt"], emoji=cfg["btn_close_emoji"], style=discord.ButtonStyle.danger, custom_id="close_t"))

    async def interaction_check(self, it: discord.Interaction) -> bool:
        cid = it.data['custom_id']; cfg = get_guild_config(it.guild_id)
        if cid == "claim_t":
            add_staff_point(it.user.id)
            await it.response.send_message(f"✅ {it.user.mention} ha asumido el ticket.")
        elif cid == "close_t":
            await it.response.send_message("Cerrando...", ephemeral=True)
            await it.channel.delete()
        return True

class TicketSelect(discord.ui.Select):
    def __init__(self, guild_id):
        cfg = get_guild_config(guild_id); options = []
        for opt in cfg["options"]: options.append(discord.SelectOption(label=opt["label"], value=opt["value"]))
        super().__init__(placeholder="Selecciona categoría...", options=options, custom_id="ticket_select")
    async def callback(self, it):
        cfg = get_guild_config(it.guild_id)
        chan = await it.guild.create_text_channel(f"ticket-{it.user.name}")
        await it.response.send_message(f"Ticket creado: {chan.mention}", ephemeral=True)
        await chan.send(embed=discord.Embed(title=cfg["welcome_title"], description=cfg["welcome_description"], color=cfg["color"]), view=TicketControlView(it.guild_id))

class TicketBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default(); intents.message_content, intents.members = True, True
        super().__init__(command_prefix="+", intents=intents)
    async def setup_hook(self):
        self.add_view(TicketControlView(0)); await self.tree.sync()

bot = TicketBot()

@bot.command()
async def activar(ctx, gid: str):
    if ctx.author.id != OWNER_ID: return
    lics = load_data(LICENSES_FILE); exp = datetime.datetime.now() + datetime.timedelta(days=30)
    lics[gid] = exp.strftime("%Y-%m-%d"); save_data(LICENSES_FILE, lics)
    await ctx.send(f"✅ Servidor {gid} activado.")

@bot.tree.command(name="setup")
async def setup(it):
    if not await check_license(it): return
    cfg = get_guild_config(it.guild_id)
    view = discord.ui.View(timeout=None).add_item(TicketSelect(it.guild_id))
    await it.channel.send(embed=discord.Embed(title=cfg["panel_title"], description=cfg["panel_description"], color=cfg["color"]), view=view)
    await it.response.send_message("Panel enviado.", ephemeral=True)

if __name__ == "__main__":
    keep_alive()
    bot.run(TOKEN)
