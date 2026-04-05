"""
Chat LAN — Cliente GUI
Requiere Python 3.10+ y tkinter (incluido en la stdlib).
Uso: python chat_client_gui.py
"""

import socket
import threading
import tkinter as tk
from tkinter import scrolledtext, messagebox
from datetime import datetime

# ─── Configuración ─────────────────────────────────────────────────────────────
DEFAULT_HOST   = "127.0.0.1"
DEFAULT_PORT   = 12345
BUFFER_SIZE    = 8192
MAX_MSG_LENGTH = 1024
SOCKET_TIMEOUT = 1.0

# ─── Paleta de colores ──────────────────────────────────────────────────────────
C = {
    "bg":           "#0f1117",   # Fondo principal
    "bg2":          "#1a1d27",   # Paneles secundarios
    "bg3":          "#22263a",   # Input / campos
    "border":       "#2e3352",   # Bordes sutiles
    "accent":       "#4f8ef7",   # Azul principal
    "accent2":      "#6c63ff",   # Violeta secundario
    "green":        "#3dd68c",   # Éxito / conexión
    "red":          "#f75f5f",   # Error / desconexión
    "yellow":       "#f7c948",   # Advertencia / privado
    "text":         "#e2e8f0",   # Texto principal
    "text2":        "#8892a4",   # Texto secundario
    "text3":        "#4a5568",   # Texto muy tenue
    "self_msg":     "#4f8ef7",   # Color msgs propios
    "other_msg":    "#e2e8f0",   # Color msgs ajenos
    "system_msg":   "#6c63ff",   # Color msgs sistema
    "private_msg":  "#f7c948",   # Color msgs privados
}

FONT_MONO  = ("Consolas", 11)
FONT_MONO2 = ("Consolas", 10)
FONT_UI    = ("Segoe UI", 10)
FONT_UI_B  = ("Segoe UI", 10, "bold")
FONT_TITLE = ("Segoe UI", 18, "bold")
FONT_SMALL = ("Segoe UI", 9)


# ══════════════════════════════════════════════════════════════════════════════
#  LÓGICA DE RED (igual que el cliente terminal, adaptada a callbacks de GUI)
# ══════════════════════════════════════════════════════════════════════════════

class ChatClient:
    def __init__(self, host: str, port: int, username: str,
                on_message,    # callback(msg: str, kind: str)
                on_disconnect  # callback(reason: str)
                ):
        self.host       = host
        self.port       = port
        self.username   = username
        self.on_message = on_message
        self.on_disconnect = on_disconnect
        self._socket: socket.socket | None = None
        self._stop      = threading.Event()

    def connect(self) -> tuple[bool, str]:
        """Intenta conectar. Devuelve (ok, mensaje_error)."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(SOCKET_TIMEOUT)
            s.connect((self.host, self.port))
            self._socket = s
            # Enviar nombre
            s.sendall((self.username + "\n").encode("utf-8"))
            return True, ""
        except ConnectionRefusedError:
            return False, f"Conexión rechazada en {self.host}:{self.port}"
        except socket.timeout:
            return False, f"Timeout conectando a {self.host}:{self.port}"
        except OSError as e:
            return False, str(e)

    def start_receiving(self):
        """Arranca el hilo receptor."""
        t = threading.Thread(target=self._recv_loop, daemon=True, name="RecvThread")
        t.start()

    def _recv_loop(self):
        buffer = ""
        while not self._stop.is_set():
            try:
                data = self._socket.recv(BUFFER_SIZE)
                if not data:
                    self.on_disconnect("El servidor cerró la conexión.")
                    break
                buffer += data.decode("utf-8", errors="replace")
                while "\n" in buffer:
                    msg, buffer = buffer.split("\n", 1)
                    msg = msg.strip()
                    if msg:
                        kind = _classify(msg)
                        self.on_message(msg, kind)
            except socket.timeout:
                continue
            except (ConnectionResetError, ConnectionAbortedError):
                if not self._stop.is_set():
                    self.on_disconnect("Conexión reiniciada por el servidor.")
                break
            except OSError:
                if not self._stop.is_set():
                    self.on_disconnect("Error de socket.")
                break
        self._stop.set()

    def send(self, text: str) -> bool:
        if not text.strip() or self._socket is None:
            return False
        text = text[:MAX_MSG_LENGTH]
        try:
            self._socket.sendall((text + "\n").encode("utf-8"))
            return True
        except (OSError, BrokenPipeError, ConnectionResetError):
            self._stop.set()
            return False

    def disconnect(self):
        self._stop.set()
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None


def _classify(msg: str) -> str:
    """Clasifica el mensaje para colorearlo en la UI."""
    if msg.startswith("[Tú]:"):
        return "self"
    if msg.startswith("💬") or msg.startswith("📩"):
        return "private"
    if "[SYSTEM]" in msg or "[ADMIN]" in msg or msg.startswith("📢") \
            or msg.startswith("🚫") or msg.startswith("✅") \
            or msg.startswith("🔴") or msg.startswith("⏰") \
            or msg.startswith("👥") or msg.startswith("❌") \
            or msg.startswith("⚠️"):
        return "system"
    return "other"


# ══════════════════════════════════════════════════════════════════════════════
#  PANTALLA DE CONEXIÓN
# ══════════════════════════════════════════════════════════════════════════════

class LoginScreen(tk.Frame):
    def __init__(self, master, on_connect):
        super().__init__(master, bg=C["bg"])
        self.on_connect = on_connect
        self._build()

    def _build(self):
        self.pack(fill="both", expand=True)

        # ── Panel central ──────────────────────────────────────────────────
        center = tk.Frame(self, bg=C["bg"])
        center.place(relx=0.5, rely=0.5, anchor="center")

        # Logo / título
        logo = tk.Label(center, text="◈ LAN CHAT", font=("Consolas", 26, "bold"),
                        bg=C["bg"], fg=C["accent"])
        logo.pack(pady=(0, 4))

        subtitle = tk.Label(center, text="Mensajería en red local",
                            font=FONT_SMALL, bg=C["bg"], fg=C["text2"])
        subtitle.pack(pady=(0, 32))

        # ── Tarjeta de formulario ─────────────────────────────────────────
        card = tk.Frame(center, bg=C["bg2"], bd=0,
                        highlightbackground=C["border"], highlightthickness=1)
        card.pack(ipadx=32, ipady=28)

        def field(parent, label_text, default="", show=""):
            grp = tk.Frame(parent, bg=C["bg2"])
            grp.pack(fill="x", pady=8)
            tk.Label(grp, text=label_text, font=FONT_SMALL,
                    bg=C["bg2"], fg=C["text2"]).pack(anchor="w")
            entry = tk.Entry(grp, font=FONT_MONO2, bg=C["bg3"], fg=C["text"],
                            insertbackground=C["accent"], bd=0, show=show,
                            highlightbackground=C["border"],
                            highlightthickness=1, highlightcolor=C["accent"],
                            relief="flat")
            entry.insert(0, default)
            entry.pack(fill="x", ipady=6, pady=(4, 0))
            return entry

        self.entry_host = field(card, "SERVIDOR (IP)", DEFAULT_HOST)
        self.entry_port = field(card, "PUERTO", str(DEFAULT_PORT))
        self.entry_name = field(card, "TU NOMBRE", "")
        self.entry_name.focus_set()

        # ── Estado / error ─────────────────────────────────────────────────
        self.lbl_status = tk.Label(card, text="", font=FONT_SMALL,
                                bg=C["bg2"], fg=C["red"])
        self.lbl_status.pack(pady=(4, 0))

        # ── Botón conectar ─────────────────────────────────────────────────
        self.btn = _AccentButton(card, text="CONECTAR", command=self._try_connect)
        self.btn.pack(fill="x", pady=(16, 0), ipady=8)

        # Enter en cualquier campo conecta
        for e in (self.entry_host, self.entry_port, self.entry_name):
            e.bind("<Return>", lambda _: self._try_connect())

    def _try_connect(self):
        host = self.entry_host.get().strip() or DEFAULT_HOST
        name = self.entry_name.get().strip() or "Anon"
        name = "".join(c for c in name if c.isprintable() and c not in "\n\r")[:32]

        try:
            port = int(self.entry_port.get().strip())
        except ValueError:
            self._set_error("Puerto inválido.")
            return

        self.btn.configure(state="disabled", text="Conectando…")
        self.lbl_status.configure(text="", fg=C["text2"])
        self.update()

        self.on_connect(host, port, name, self._on_fail)

    def _on_fail(self, reason: str):
        self.btn.configure(state="normal", text="CONECTAR")
        self._set_error(reason)

    def _set_error(self, msg):
        self.lbl_status.configure(text=f"✗  {msg}", fg=C["red"])


# ══════════════════════════════════════════════════════════════════════════════
#  PANTALLA DE CHAT
# ══════════════════════════════════════════════════════════════════════════════

class ChatScreen(tk.Frame):
    def __init__(self, master, client: ChatClient, on_disconnect_ui):
        super().__init__(master, bg=C["bg"])
        self.client = client
        self.on_disconnect_ui = on_disconnect_ui
        self._build()

    def _build(self):
        self.pack(fill="both", expand=True)

        # ── Barra superior ─────────────────────────────────────────────────
        topbar = tk.Frame(self, bg=C["bg2"],
                        highlightbackground=C["border"], highlightthickness=1)
        topbar.pack(fill="x", side="top")

        tk.Label(topbar, text="◈ LAN CHAT", font=("Consolas", 12, "bold"),
                bg=C["bg2"], fg=C["accent"]).pack(side="left", padx=16, pady=10)

        self.lbl_user = tk.Label(
            topbar,
            text=f"  {self.client.username}",
            font=FONT_UI_B, bg=C["bg2"], fg=C["green"]
        )
        self.lbl_user.pack(side="left", padx=4)

        self.lbl_status = tk.Label(topbar, text="● conectado",
                                font=FONT_SMALL, bg=C["bg2"], fg=C["green"])
        self.lbl_status.pack(side="left", padx=12)

        btn_disc = _FlatButton(topbar, text="Desconectar",
                            command=self._disconnect, fg=C["red"])
        btn_disc.pack(side="right", padx=12, pady=8)

        btn_list = _FlatButton(topbar, text="/list",
                            command=lambda: self._send_cmd("/list"))
        btn_list.pack(side="right", padx=4, pady=8)

        btn_help = _FlatButton(topbar, text="/help",
                            command=lambda: self._send_cmd("/help"))
        btn_help.pack(side="right", padx=4, pady=8)

        # ── Cuerpo principal ───────────────────────────────────────────────
        body = tk.Frame(self, bg=C["bg"])
        body.pack(fill="both", expand=True, padx=0, pady=0)

        # Área de mensajes
        msg_frame = tk.Frame(body, bg=C["bg"])
        msg_frame.pack(fill="both", expand=True, padx=12, pady=(12, 0))

        self.txt = scrolledtext.ScrolledText(
            msg_frame,
            font=FONT_MONO2,
            bg=C["bg2"], fg=C["text"],
            bd=0, relief="flat",
            state="disabled",
            wrap="word",
            insertbackground=C["accent"],
            highlightbackground=C["border"],
            highlightthickness=1,
            padx=12, pady=12,
            spacing1=2, spacing3=4,
        )
        self.txt.pack(fill="both", expand=True)

        # Configurar tags de color
        self.txt.tag_config("self",    foreground=C["self_msg"])
        self.txt.tag_config("other",   foreground=C["other_msg"])
        self.txt.tag_config("system",  foreground=C["system_msg"])
        self.txt.tag_config("private", foreground=C["yellow"])
        self.txt.tag_config("time",    foreground=C["text3"])
        self.txt.tag_config("error",   foreground=C["red"])

        # ── Panel de mensaje privado rápido ────────────────────────────────
        self._pm_bar_visible = False
        self._pm_bar = tk.Frame(body, bg=C["bg2"],
                                highlightbackground=C["border"], highlightthickness=1)

        tk.Label(self._pm_bar, text="/msg →", font=FONT_SMALL,
                bg=C["bg2"], fg=C["yellow"]).pack(side="left", padx=(12, 4))

        self.entry_pm_user = tk.Entry(
            self._pm_bar, font=FONT_MONO2, bg=C["bg3"], fg=C["text"],
            insertbackground=C["accent"], bd=0,
            highlightbackground=C["border"], highlightthickness=1,
            width=14, relief="flat"
        )
        self.entry_pm_user.pack(side="left", ipady=4, padx=4)

        self.entry_pm_msg = tk.Entry(
            self._pm_bar, font=FONT_MONO2, bg=C["bg3"], fg=C["text"],
            insertbackground=C["accent"], bd=0,
            highlightbackground=C["border"], highlightthickness=1,
            relief="flat"
        )
        self.entry_pm_msg.pack(side="left", fill="x", expand=True, ipady=4, padx=4)
        self.entry_pm_msg.bind("<Return>", lambda _: self._send_private())

        _FlatButton(self._pm_bar, text="Enviar", fg=C["yellow"],
                    command=self._send_private).pack(side="left", padx=8)
        _FlatButton(self._pm_bar, text="✕", fg=C["text3"],
                    command=self._hide_pm_bar).pack(side="left", padx=(0, 8))

        # ── Barra de entrada ───────────────────────────────────────────────
        input_frame = tk.Frame(self, bg=C["bg"],
                            highlightbackground=C["border"], highlightthickness=1)
        input_frame.pack(fill="x", side="bottom", padx=12, pady=12)

        self.entry = tk.Entry(
            input_frame, font=FONT_MONO,
            bg=C["bg3"], fg=C["text"],
            insertbackground=C["accent"],
            bd=0, relief="flat",
            highlightbackground=C["border"],
            highlightthickness=1,
            highlightcolor=C["accent"],
        )
        self.entry.pack(side="left", fill="both", expand=True, ipady=10, padx=(12, 0))
        self.entry.bind("<Return>", lambda _: self._send_message())
        self.entry.bind("<Tab>", self._on_tab)
        self.entry.focus_set()

        # Botón privado
        btn_pm = _FlatButton(input_frame, text="💬",
                            command=self._toggle_pm_bar, fg=C["yellow"])
        btn_pm.pack(side="left", padx=6)

        btn_send = _AccentButton(input_frame, text="Enviar ↵",
                                command=self._send_message)
        btn_send.pack(side="right", padx=(0, 0), ipady=6, ipadx=12)

        # Contador de caracteres
        self.lbl_count = tk.Label(input_frame, text="0 / 1024",
                                font=FONT_SMALL, bg=C["bg3"], fg=C["text3"])
        self.lbl_count.pack(side="right", padx=8)
        self.entry.bind("<KeyRelease>", self._update_count)

        # ── Mensaje de bienvenida ──────────────────────────────────────────
        self._append_system(
            f"Conectado como {self.client.username}. "
            "Usa /help para ver los comandos."
        )

    # ── Helpers de UI ─────────────────────────────────────────────────────────

    def _append(self, text: str, tag: str):
        """Añade una línea al área de mensajes (thread-safe via after)."""
        def _do():
            ts = datetime.now().strftime("%H:%M")
            self.txt.configure(state="normal")
            self.txt.insert("end", f"[{ts}] ", "time")
            self.txt.insert("end", text + "\n", tag)
            self.txt.configure(state="disabled")
            self.txt.see("end")
        self.after(0, _do)

    def _append_system(self, text: str):
        self._append(text, "system")

    def _append_error(self, text: str):
        self._append(text, "error")

    def _update_count(self, _=None):
        n = len(self.entry.get())
        color = C["red"] if n > MAX_MSG_LENGTH else C["text3"]
        self.lbl_count.configure(text=f"{n} / {MAX_MSG_LENGTH}", fg=color)

    # ── Envío de mensajes ─────────────────────────────────────────────────────

    def _send_message(self):
        msg = self.entry.get().strip()
        if not msg:
            return
        self.entry.delete(0, "end")
        self._update_count()

        lower = msg.lower()
        if lower in {"exit", "salir", "quit"}:
            self._disconnect()
            return

        if msg.startswith("/msg "):
            parts = msg.split(" ", 2)
            if len(parts) < 3 or not parts[2].strip():
                self._append_error("❌ Uso: /msg <usuario> <mensaje>")
                return

        if not self.client.send(msg):
            self._append_error("[!] Error al enviar. Conexión perdida.")

    def _send_cmd(self, cmd: str):
        if not self.client.send(cmd):
            self._append_error("[!] Error al enviar.")

    def _send_private(self):
        user = self.entry_pm_user.get().strip()
        msg  = self.entry_pm_msg.get().strip()
        if not user or not msg:
            return
        self.client.send(f"/msg {user} {msg}")
        self.entry_pm_msg.delete(0, "end")

    # ── Panel privado ──────────────────────────────────────────────────────────

    def _toggle_pm_bar(self):
        if self._pm_bar_visible:
            self._hide_pm_bar()
        else:
            self._pm_bar.pack(fill="x", padx=12, pady=(0, 4),
                            before=self.entry.master)
            self._pm_bar_visible = True
            self.entry_pm_user.focus_set()

    def _hide_pm_bar(self):
        self._pm_bar.pack_forget()
        self._pm_bar_visible = False
        self.entry.focus_set()

    # ── Tab → autocompletado básico de /comandos ──────────────────────────────

    def _on_tab(self, _):
        txt = self.entry.get()
        commands = ["/msg ", "/list", "/help"]
        for cmd in commands:
            if cmd.startswith(txt) and cmd != txt:
                self.entry.delete(0, "end")
                self.entry.insert(0, cmd)
                break
        return "break"  # Evitar que Tab mueva el foco

    # ── Callbacks de red ──────────────────────────────────────────────────────

    def receive_message(self, msg: str, kind: str):
        """Llamado desde el hilo receptor."""
        self._append(msg, kind)

    def handle_disconnect(self, reason: str):
        """Llamado desde el hilo receptor cuando se pierde la conexión."""
        def _do():
            self.lbl_status.configure(text="● desconectado", fg=C["red"])
            self._append_error(f"[!] {reason}")
            self.on_disconnect_ui()
        self.after(0, _do)

    # ── Desconexión voluntaria ────────────────────────────────────────────────

    def _disconnect(self):
        self.client.disconnect()
        self.on_disconnect_ui()


# ══════════════════════════════════════════════════════════════════════════════
#  WIDGETS AUXILIARES
# ══════════════════════════════════════════════════════════════════════════════

class _AccentButton(tk.Button):
    def __init__(self, master, **kw):
        super().__init__(
            master,
            bg=C["accent"], fg="#ffffff",
            activebackground=C["accent2"],
            activeforeground="#ffffff",
            font=FONT_UI_B, bd=0, relief="flat",
            cursor="hand2",
            **kw
        )
        self.bind("<Enter>", lambda _: self.configure(bg=C["accent2"]))
        self.bind("<Leave>", lambda _: self.configure(bg=C["accent"]))


class _FlatButton(tk.Button):
    def __init__(self, master, fg=None, **kw):
        _fg = fg or C["text2"]
        super().__init__(
            master,
            bg=C["bg2"], fg=_fg,
            activebackground=C["bg3"],
            activeforeground=C["text"],
            font=FONT_UI, bd=0, relief="flat",
            cursor="hand2",
            **kw
        )
        self.bind("<Enter>", lambda _: self.configure(bg=C["bg3"]))
        self.bind("<Leave>", lambda _: self.configure(bg=C["bg2"]))


# ══════════════════════════════════════════════════════════════════════════════
#  APP PRINCIPAL — gestiona la transición entre pantallas
# ══════════════════════════════════════════════════════════════════════════════

class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("LAN Chat")
        self.geometry("860x620")
        self.minsize(620, 480)
        self.configure(bg=C["bg"])

        # Icono en la barra de título (texto ASCII como placeholder)
        try:
            self.iconbitmap(default="")
        except Exception:
            pass

        self._client: ChatClient | None = None
        self._current_screen: tk.Frame | None = None
        self._show_login()

    # ── Pantallas ─────────────────────────────────────────────────────────────

    def _show_login(self):
        if self._current_screen:
            self._current_screen.destroy()
        screen = LoginScreen(self, on_connect=self._do_connect)
        self._current_screen = screen

    def _show_chat(self, client: ChatClient):
        if self._current_screen:
            self._current_screen.destroy()
        screen = ChatScreen(
            self, client,
            on_disconnect_ui=self._on_disconnect_ui
        )
        self._current_screen = screen

    # ── Lógica de conexión ────────────────────────────────────────────────────

    def _do_connect(self, host: str, port: int, name: str, on_fail):
        """Conectar en hilo separado para no bloquear la UI."""
        def _worker():
            client = ChatClient(
                host=host, port=port, username=name,
                on_message=self._on_message,
                on_disconnect=self._on_disconnect_net,
            )
            ok, err = client.connect()
            if not ok:
                self.after(0, lambda: on_fail(err))
                return
            self._client = client
            client.start_receiving()
            self.after(0, lambda: self._show_chat(client))

        threading.Thread(target=_worker, daemon=True).start()

    # ── Callbacks de red (pueden venir de cualquier hilo) ─────────────────────

    def _on_message(self, msg: str, kind: str):
        if self._current_screen and isinstance(self._current_screen, ChatScreen):
            self._current_screen.receive_message(msg, kind)

    def _on_disconnect_net(self, reason: str):
        if self._current_screen and isinstance(self._current_screen, ChatScreen):
            self._current_screen.handle_disconnect(reason)

    def _on_disconnect_ui(self):
        """Volver al login tras desconexión."""
        if self._client:
            self._client.disconnect()
            self._client = None
        self.after(100, self._show_login)

    # ── Cierre de ventana ─────────────────────────────────────────────────────

    def destroy(self):
        if self._client:
            self._client.disconnect()
        super().destroy()


# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = App()
    app.mainloop()