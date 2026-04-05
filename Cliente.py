import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime
import json
import os

# ─── Configuración ─────────────────────────────────────────────────────────────
DEFAULT_HOST   = "127.0.0.1"
DEFAULT_PORT   = 12345
BUFFER_SIZE    = 8192
MAX_MSG_LENGTH = 1024
SOCKET_TIMEOUT = 1.0
CONFIG_FILE    = "chat_config.json"

# ─── Paleta de colores ──────────────────────────────────────────────────────────
C = {
    "bg":           "#0f1117",
    "bg2":          "#1a1d27",
    "bg3":          "#22263a",
    "border":       "#2e3352",
    "accent":       "#4f8ef7",
    "accent2":      "#6c63ff",
    "green":        "#3dd68c",
    "red":          "#f75f5f",
    "yellow":       "#f7c948",
    "text":         "#e2e8f0",
    "text2":        "#8892a4",
    "text3":        "#4a5568",
    "self_msg":     "#4f8ef7",
    "other_msg":    "#e2e8f0",
    "system_msg":   "#6c63ff",
    "private_msg":  "#f7c948",
}

FONT_MONO  = ("Consolas", 11)
FONT_MONO2 = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)
FONT_UI_B  = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SMALL = ("Segoe UI", 9)

# ─── Persistencia ─────────────────────────────────────────────────────────────

def save_config(host, port, name, auto=True):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump({"host": host, "port": port, "name": name, "auto": auto}, f)
    except Exception as e:
        print(f"Error guardando config: {e}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except:
            return None
    return None

# ══════════════════════════════════════════════════════════════════════════════
#  LÓGICA DE RED
# ══════════════════════════════════════════════════════════════════════════════

class ChatClient:
    def __init__(self, host: str, port: int, username: str, on_message, on_disconnect):
        self.host = host
        self.port = port
        self.username = username
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self._socket: socket.socket | None = None
        self._stop = threading.Event()

    def connect(self) -> tuple[bool, str]:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(SOCKET_TIMEOUT)
            s.connect((self.host, self.port))
            self._socket = s
            s.sendall((self.username + "\n").encode("utf-8"))
            return True, ""
        except Exception as e:
            return False, str(e)

    def start_receiving(self):
        threading.Thread(target=self._recv_loop, daemon=True).start()

    def _recv_loop(self):
        buffer = ""
        while not self._stop.is_set():
            try:
                data = self._socket.recv(BUFFER_SIZE)
                if not data:
                    self.on_disconnect("Servidor desconectado.")
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    msg, buffer = buffer.split("\n", 1)
                    if msg.strip():
                        self.on_message(msg.strip(), _classify(msg))
            except socket.timeout: continue
            except: break
        self._stop.set()

    def send(self, text: str) -> bool:
        if not text.strip() or not self._socket: return False
        try:
            self._socket.sendall((text[:MAX_MSG_LENGTH] + "\n").encode("utf-8"))
            return True
        except: return False

    def disconnect(self):
        self._stop.set()
        if self._socket:
            try: self._socket.shutdown(socket.SHUT_RDWR)
            except: pass
            self._socket.close()

def _classify(msg: str) -> str:
    if msg.startswith("[Tú]:"): return "self"
    if any(x in msg for x in ["💬", "📩"]): return "private"
    if any(x in msg for x in ["[SYSTEM]", "[ADMIN]", "📢", "✅", "❌"]): return "system"
    return "other"

# ══════════════════════════════════════════════════════════════════════════════
#  PANTALLAS (GUI)
# ══════════════════════════════════════════════════════════════════════════════

class LoginScreen(tk.Frame):
    def __init__(self, master, on_connect, initial_data=None):
        super().__init__(master, bg=C["bg"])
        self.on_connect = on_connect
        self.initial_data = initial_data or {}
        self._build()

    def _build(self):
        self.pack(fill="both", expand=True)
        center = tk.Frame(self, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        tk.Label(center, text="◈ LAN CHAT", font=("Consolas", 26, "bold"), bg=C["bg"], fg=C["accent"]).pack()
        card = tk.Frame(center, bg=C["bg2"], highlightbackground=C["border"], highlightthickness=1)
        card.pack(ipadx=32, ipady=28, pady=20)

        def field(label, key, default):
            tk.Label(card, text=label, font=FONT_SMALL, bg=C["bg2"], fg=C["text2"]).pack(anchor="w", padx=20)
            e = tk.Entry(card, font=FONT_MONO2, bg=C["bg3"], fg=C["text"], bd=0, highlightthickness=1, highlightbackground=C["border"], highlightcolor=C["accent"])
            e.insert(0, self.initial_data.get(key, default))
            e.pack(fill="x", padx=20, ipady=6, pady=(4, 10))
            return e

        self.e_host = field("SERVIDOR (IP)", "host", DEFAULT_HOST)
        self.e_port = field("PUERTO", "port", str(DEFAULT_PORT))
        self.e_name = field("TU NOMBRE", "name", "")
        self.e_name.focus_set()

        self.lbl_status = tk.Label(card, text="", font=FONT_SMALL, bg=C["bg2"], fg=C["red"])
        self.lbl_status.pack()

        self.btn = _AccentButton(card, text="CONECTAR", command=self._handle_click)
        self.btn.pack(fill="x", padx=20, pady=10, ipady=8)

    def _handle_click(self):
        h, p, n = self.e_host.get().strip(), self.e_port.get().strip(), self.e_name.get().strip()
        try:
            self.on_connect(h, int(p), n, self._on_fail)
            self.btn.configure(state="disabled", text="Conectando...")
        except: self._on_fail("Puerto inválido")

    def _on_fail(self, err):
        self.btn.configure(state="normal", text="CONECTAR")
        self.lbl_status.configure(text=f"✗ {err}")

class ChatScreen(tk.Frame):
    def __init__(self, master, client, on_disc_ui):
        super().__init__(master, bg=C["bg"])
        self.client, self.on_disc_ui = client, on_disc_ui
        self._build()

    def _build(self):
        self.pack(fill="both", expand=True)
        # Barra superior básica
        top = tk.Frame(self, bg=C["bg2"], height=50)
        top.pack(fill="x")
        tk.Label(top, text=f"👤 {self.client.username}", bg=C["bg2"], fg=C["green"], font=FONT_UI_B).pack(side="left", padx=15)
        _FlatButton(top, text="Cerrar Sesión", fg=C["red"], command=self.on_disc_ui).pack(side="right", padx=15)

        # Chat area
        self.txt = scrolledtext.ScrolledText(self, bg=C["bg2"], fg=C["text"], font=FONT_MONO2, bd=0, highlightthickness=1, highlightbackground=C["border"])
        self.txt.pack(fill="both", expand=True, padx=15, pady=15)
        self.txt.tag_config("self", foreground=C["self_msg"])
        self.txt.tag_config("system", foreground=C["system_msg"])
        self.txt.tag_config("error", foreground=C["red"])
        
        # Input
        inv = tk.Frame(self, bg=C["bg"])
        inv.pack(fill="x", padx=15, pady=(0,15))
        self.entry = tk.Entry(inv, bg=C["bg3"], fg=C["text"], font=FONT_MONO, bd=0, highlightthickness=1, highlightbackground=C["border"])
        self.entry.pack(side="left", fill="x", expand=True, ipady=10)
        self.entry.bind("<Return>", lambda _: self._send())
        self.entry.focus_set()

    def _send(self):
        m = self.entry.get().strip()
        if m:
            if self.client.send(m): self.entry.delete(0, "end")

    def receive_message(self, msg, kind):
        self.after(0, lambda: self._write(msg, kind))

    def _write(self, msg, kind):
        self.txt.configure(state="normal")
        self.txt.insert("end", f"[{datetime.now().strftime('%H:%M')}] {msg}\n", kind)
        self.txt.configure(state="disabled")
        self.txt.see("end")

# ══════════════════════════════════════════════════════════════════════════════
#  APP PRINCIPAL
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LAN Chat")
        self.geometry("860x620")
        self.configure(bg=C["bg"])
        
        self._client = None
        self._current_screen = None
        
        # Lógica de autoconexión
        config = load_config()
        if config and config.get("auto"):
            self._show_loading()
            self.after(500, lambda: self._do_connect(config['host'], config['port'], config['name'], self._on_auto_fail))
        else:
            self._show_login(config)

    def _show_loading(self):
        self._current_screen = tk.Frame(self, bg=C["bg"])
        self._current_screen.pack(fill="both", expand=True)
        tk.Label(self._current_screen, text="🚀 Autoconectando...", fg=C["accent"], bg=C["bg"], font=FONT_TITLE).place(relx=0.5, rely=0.5, anchor="center")

    def _show_login(self, config=None):
        if self._current_screen: self._current_screen.destroy()
        self._current_screen = LoginScreen(self, self._do_connect, config)

    def _do_connect(self, h, p, n, on_fail):
        def worker():
            client = ChatClient(h, p, n, self._on_msg, self._on_disc_net)
            ok, err = client.connect()
            if ok:
                save_config(h, p, n, True)
                self._client = client
                self.after(0, lambda: self._show_chat())
                client.start_receiving()
            else:
                self.after(0, lambda: on_fail(err))
        threading.Thread(target=worker, daemon=True).start()

    def _show_chat(self):
        if self._current_screen: self._current_screen.destroy()
        self._current_screen = ChatScreen(self, self._client, self._on_disc_ui)

    def _on_auto_fail(self, err):
        self._show_login(load_config()) # Cargar últimos datos para corregir

    def _on_msg(self, m, k):
        if isinstance(self._current_screen, ChatScreen): self._current_screen.receive_message(m, k)

    def _on_disc_net(self, r):
        if isinstance(self._current_screen, ChatScreen): self._current_screen._write(f"Desconectado: {r}", "error")

    def _on_disc_ui(self):
        # Al cerrar sesión manual, desactivamos el 'auto' para que no re-conecte al instante
        config = load_config()
        if config: save_config(config['host'], config['port'], config['name'], False)
        if self._client: self._client.disconnect()
        self._show_login(config)

# Widgets auxiliares (Iguales a los anteriores para mantener estética)
class _AccentButton(tk.Button):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C["accent"], fg="white", font=FONT_UI_B, bd=0, cursor="hand2", **kw)
class _FlatButton(tk.Button):
    def __init__(self, master, **kw):
        super().__init__(master, bg=C["bg2"], font=FONT_UI, bd=0, cursor="hand2", **kw)

if __name__ == "__main__":
    App().mainloop()