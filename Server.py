import socket
import threading
import re
from datetime import datetime
from typing import Dict, Tuple

# ─── Configuración ────────────────────────────────────────────────────────────
HOST             = "0.0.0.0"
PORT             = 12345
BUFFER_SIZE      = 8192
MAX_MSG_LEN      = 1024
MAX_CLIENTS      = 50
IDLE_TIMEOUT     = 300
MAX_BUFFER_ACCUM = 65536
RESERVED_NAMES   = {"SYSTEM", "ADMIN", "SERVIDOR"}

clients: Dict[socket.socket, Tuple[str, str]] = {}
clients_lock = threading.RLock()

# Evento global para señalizar el apagado desde cualquier hilo
shutdown_event = threading.Event()


# ─── Logging ──────────────────────────────────────────────────────────────────

def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─── Utilidades de red ────────────────────────────────────────────────────────

def send(client_socket: socket.socket, message: str) -> bool:
    """
    Envío seguro con delimitador '\n'.
    Solo devuelve False si falla — NO elimina el cliente.
    La eliminación es responsabilidad de handle_client.
    """
    try:
        client_socket.sendall((message + "\n").encode("utf-8"))
        return True
    except (OSError, ConnectionResetError, BrokenPipeError):
        return False


def broadcast(message: str, sender_socket: socket.socket | None = None) -> None:
    """Envía un mensaje a todos los clientes excepto al remitente."""
    with clients_lock:
        targets = list(clients.keys())
    for sock in targets:
        if sock != sender_socket:
            send(sock, message)


def find_client_by_name(name: str) -> socket.socket | None:
    """Busca un socket por nombre de usuario."""
    with clients_lock:
        for sock, (n, _) in clients.items():
            if n == name:
                return sock
    return None


def get_client_list() -> list[str]:
    """Devuelve la lista de nombres de usuarios conectados."""
    with clients_lock:
        return [name for name, _ in clients.values()]


def _remove_client(client_socket: socket.socket) -> str | None:
    """
    Elimina el cliente del registro y cierra su socket.
    Punto único de eliminación — seguro ante llamadas dobles.
    """
    with clients_lock:
        entry = clients.pop(client_socket, None)

    if not entry:
        return None  # Ya fue eliminado antes

    name, ip = entry
    log(f"[-] Desconectado: {name} ({ip})")

    try:
        client_socket.close()
    except OSError:
        pass

    return name


# ─── Procesado de mensajes ────────────────────────────────────────────────────

def _flush_buffer(client_socket: socket.socket, buffer: str) -> str:
    """Extrae y procesa todos los mensajes completos del buffer."""
    while "\n" in buffer:
        msg, buffer = buffer.split("\n", 1)
        msg = msg.strip()[:MAX_MSG_LEN]
        if msg:
            process_message(client_socket, msg)
    return buffer


def process_message(client_socket: socket.socket, msg: str) -> None:
    """Despacha un mensaje según sea comando o broadcast."""
    with clients_lock:
        entry = clients.get(client_socket)
        if not entry:
            return
        name = entry[0]

    # ── /msg — Privado ────────────────────────────────────────────────────────
    if msg.startswith("/msg "):
        parts = msg.split(maxsplit=2)
        if len(parts) < 3 or not parts[2].strip():
            send(client_socket, "❌ Uso: /msg <usuario> <mensaje>")
            return

        target_name, private_text = parts[1], parts[2].strip()

        if target_name == name:
            send(client_socket, "❌ No puedes enviarte un mensaje a ti mismo.")
            return

        target_socket = find_client_by_name(target_name)
        if not target_socket:
            send(client_socket, f"❌ Usuario '{target_name}' no encontrado.")
            return

        send(target_socket, f"💬 [Privado de {name}]: {private_text}")
        send(client_socket,  f"📩 [Privado a {target_name}]: {private_text}")
        log(f"[PRIVADO] {name} → {target_name}: {private_text}")
        return

    # ── Comandos simples ──────────────────────────────────────────────────────
    cmd = msg.lower().split(maxsplit=1)[0]

    if cmd == "/list":
        users = get_client_list()
        send(client_socket, f"👥 Conectados ({len(users)}): {', '.join(users) or '(nadie)'}")
        return

    if cmd == "/help":
        for line in [
            "═══════════════════════════════",
            "  /msg <usuario> <texto>  → Privado",
            "  /list                  → Ver conectados",
            "  /help                  → Esta ayuda",
            "═══════════════════════════════",
        ]:
            send(client_socket, line)
        return

    # ── Broadcast normal ──────────────────────────────────────────────────────
    log(f"{name}: {msg}")
    send(client_socket, f"[Tú]: {msg}")
    broadcast(f"{name}: {msg}", sender_socket=client_socket)


# ─── Handshake ────────────────────────────────────────────────────────────────

def receive_line(sock: socket.socket, max_bytes: int = 4096) -> tuple[str | None, str]:
    """
    Lee bytes hasta encontrar '\n' o agotar max_bytes.
    Devuelve (línea, buffer_restante) o (None, "") si falla.
    """
    buffer = ""
    while "\n" not in buffer:
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except socket.timeout:
            return None, ""
        if not chunk:
            return None, ""
        buffer += chunk.decode("utf-8", errors="ignore")
        if len(buffer) > max_bytes:
            if "\n" in buffer:
                break
            return None, ""

    line, remaining = buffer.split("\n", 1)
    return line.strip(), remaining


# ─── Gestión de cliente ───────────────────────────────────────────────────────

def handle_client(client_socket: socket.socket, addr: tuple) -> None:
    """Hilo dedicado por cliente: handshake → loop → limpieza."""
    ip = addr[0]
    buffer = ""

    try:
        # ── Handshake ─────────────────────────────────────────────────────────
        client_socket.settimeout(10)
        raw_name, pending = receive_line(client_socket)

        if not raw_name:
            return

        raw_name = re.sub(r"[^\w\-]", "", raw_name)[:32] or "Anon"
        if raw_name.upper() in RESERVED_NAMES:
            raw_name = "User"

        with clients_lock:
            if len(clients) >= MAX_CLIENTS:
                send(client_socket, "❌ Servidor lleno. Inténtalo más tarde.")
                return

            existing = {n for n, _ in clients.values()}
            name = raw_name
            i = 1
            while name in existing:
                name = f"{raw_name}_{i}"
                i += 1

            clients[client_socket] = (name, ip)

        log(f"[+] Conectado: {name} ({ip})")
        send(client_socket, f"✅ Bienvenido, {name}! Escribe /help para ver los comandos.")
        broadcast(f"📢 [SYSTEM] {name} se ha unido al chat.", sender_socket=client_socket)

        buffer = _flush_buffer(client_socket, pending)

        # ── Loop principal ────────────────────────────────────────────────────
        client_socket.settimeout(IDLE_TIMEOUT)

        while not shutdown_event.is_set():
            try:
                data = client_socket.recv(BUFFER_SIZE)
            except socket.timeout:
                send(client_socket, "⏰ Desconectado por inactividad.")
                break
            except (OSError, ConnectionResetError, BrokenPipeError):
                break

            if not data:
                break

            buffer += data.decode("utf-8", errors="ignore")

            if len(buffer) > MAX_BUFFER_ACCUM:
                send(client_socket, "❌ Buffer excedido. Desconectando.")
                break

            buffer = _flush_buffer(client_socket, buffer)

    finally:
        removed_name = _remove_client(client_socket)
        if removed_name:
            broadcast(f"🚫 [SYSTEM] {removed_name} ha salido del chat.")


# ─── Consola de administrador ─────────────────────────────────────────────────

def admin_console(server_socket: socket.socket) -> None:
    """Hilo de consola para comandos de administración."""
    print("\n🖥️  Consola de administrador activa")
    print("  <mensaje>          → Broadcast")
    print("  /kick <usuario>    → Expulsar")
    print("  /list              → Ver conectados")
    print("  /shutdown          → Apagar servidor")
    print("─" * 50)

    while not shutdown_event.is_set():
        try:
            command = input("Admin > ").strip()
        except EOFError:
            break

        if not command:
            continue

        lower = command.lower()

        # ── /kick ─────────────────────────────────────────────────────────────
        if lower.startswith("/kick "):
            target_name = command.split(maxsplit=1)[1].strip()
            target_socket = find_client_by_name(target_name)
            if not target_socket:
                print(f"❌ Usuario '{target_name}' no encontrado.")
                continue
            send(target_socket, "🚫 Has sido expulsado por el administrador.")
            removed = _remove_client(target_socket)
            if removed:
                broadcast(f"🚫 [ADMIN] {removed} ha sido expulsado.")
                log(f"[KICK] {removed} expulsado.")
            continue

        # ── /list ─────────────────────────────────────────────────────────────
        if lower == "/list":
            users = get_client_list()
            print(f"👥 Conectados ({len(users)}): {', '.join(users) or '(nadie)'}")
            continue

        # ── /shutdown ─────────────────────────────────────────────────────────
        if lower in ("/shutdown", "/exit", "/quit", "/apagar"):
            log("⛔ Apagando por orden del administrador...")
            broadcast("🔴 [SYSTEM] El servidor se está apagando. ¡Hasta pronto!")
            shutdown_event.set()        # Señal global a todos los hilos
            try:
                server_socket.close()   # Desbloquea server.accept()
            except OSError:
                pass
            break

        # ── Broadcast de admin ────────────────────────────────────────────────
        broadcast(f"📢 [ADMIN] {command}")
        log(f"[BROADCAST] {command}")


# ─── Servidor principal ───────────────────────────────────────────────────────

def start_server() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.settimeout(1.0)  # Permite chequear shutdown_event entre accepts

    try:
        server.bind((HOST, PORT))
        server.listen(MAX_CLIENTS)
        log(f"🚀 Servidor iniciado en {HOST}:{PORT}")

        console_thread = threading.Thread(
            target=admin_console,
            args=(server,),
            daemon=True,
            name="AdminConsole",
        )
        console_thread.start()

        while not shutdown_event.is_set():
            try:
                conn, addr = server.accept()
            except socket.timeout:
                continue   # Recomprobar shutdown_event
            except OSError:
                break      # Socket cerrado por /shutdown

            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True,
                name=f"Client-{addr[0]}:{addr[1]}",
            ).start()

    except KeyboardInterrupt:
        log("\n⛔ Ctrl+C recibido. Apagando...")
        shutdown_event.set()

    finally:
        if not shutdown_event.is_set():
            broadcast("🔴 [SYSTEM] El servidor se está apagando. ¡Hasta pronto!")
        with clients_lock:
            for sock in list(clients.keys()):
                try:
                    sock.close()
                except OSError:
                    pass
            clients.clear()
        try:
            server.close()
        except OSError:
            pass
        log("✅ Servidor cerrado.")


if __name__ == "__main__":
    start_server()