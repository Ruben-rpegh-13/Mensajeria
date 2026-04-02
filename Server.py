import socket
import threading
import re
from datetime import datetime
from typing import Dict, Tuple

# ─── Configuración ────────────────────────────────────────────────────────────
HOST = "0.0.0.0"
PORT = 12345
BUFFER_SIZE = 8192
MAX_MSG_LEN = 1024
MAX_CLIENTS = 50
IDLE_TIMEOUT = 300
MAX_BUFFER_ACCUM = 65536
RESERVED_NAMES = {"SYSTEM", "ADMIN"}

clients: Dict[socket.socket, Tuple[str, str]] = {}
clients_lock = threading.RLock()


# ─── Logging ──────────────────────────────────────────────────────────────────
def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ─── Utilidades ───────────────────────────────────────────────────────────────
def send(client_socket: socket.socket, message: str) -> bool:
    try:
        client_socket.sendall((message + "\n").encode("utf-8"))
        return True
    except (OSError, ConnectionResetError, BrokenPipeError):
        _remove_client(client_socket)
        return False


def broadcast(message: str, sender_socket: socket.socket | None = None) -> None:
    with clients_lock:
        targets = list(clients.keys())
    for sock in targets:
        if sock != sender_socket:
            send(sock, message)


def find_client_by_name(name: str) -> socket.socket | None:
    with clients_lock:
        for sock, (n, _) in clients.items():
            if n == name:
                return sock
    return None


def get_client_list() -> list[str]:
    with clients_lock:
        return [name for name, _ in clients.values()]


def _remove_client(client_socket: socket.socket) -> str | None:
    with clients_lock:
        entry = clients.pop(client_socket, None)
    if not entry:
        return None
    name, ip = entry
    log(f"[-] Desconectado: {name} ({ip})")
    try:
        client_socket.close()
    except OSError:
        pass
    return name


# ─── Procesado de mensajes ────────────────────────────────────────────────────
def _process_pending_messages(client_socket: socket.socket, buffer: str) -> str:
    while "\n" in buffer:
        msg, buffer = buffer.split("\n", 1)
        msg = msg.strip()[:MAX_MSG_LEN]
        if msg:
            process_message(client_socket, msg)
    return buffer


def process_message(client_socket: socket.socket, msg: str) -> None:
    with clients_lock:
        entry = clients.get(client_socket)
        if not entry:
            return
        name = entry[0]

    if msg.startswith("/msg "):
        parts = msg.split(maxsplit=2)
        if len(parts) < 3 or not parts[2]:
            send(client_socket, "❌ Uso: /msg <usuario> <mensaje>")
            return
        target_name = parts[1]
        private_text = parts[2]
        if target_name == name:
            send(client_socket, "❌ No puedes enviarte un mensaje a ti mismo.")
            return
        target_socket = find_client_by_name(target_name)
        if not target_socket:
            send(client_socket, f"❌ Usuario '{target_name}' no encontrado.")
            return
        send(target_socket, f"💬 [Privado de {name}]: {private_text}")
        send(client_socket, f"📩 [Privado a {target_name}]: {private_text}")
        log(f"[PRIVADO] {name} → {target_name}: {private_text}")
        return

    cmd = msg.lower().split(maxsplit=1)[0]
    if cmd == "/list":
        users = get_client_list()
        send(client_socket, f"👥 Conectados ({len(users)}): {', '.join(users) or '(nadie)'}")
        return
    if cmd == "/help":
        send(client_socket, "/msg <usuario> <texto>\n/list\n/help")
        return

    log(f"{name}: {msg}")
    send(client_socket, f"[Tú]: {msg}")
    broadcast(f"{name}: {msg}", sender_socket=client_socket)


# ─── Handshake ────────────────────────────────────────────────────────────────
def receive_line(sock: socket.socket) -> tuple[str | None, str]:
    buffer = ""
    while "\n" not in buffer:
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except socket.timeout:
            return None, ""
        if not chunk:
            return None, ""
        buffer += chunk.decode("utf-8", errors="ignore")
        if len(buffer) > 1024:
            return None, ""
    line, remaining = buffer.split("\n", 1)
    return line.strip(), remaining


# ─── Cliente handler ──────────────────────────────────────────────────────────
def handle_client(client_socket: socket.socket, addr: tuple) -> None:
    ip = addr[0]
    name: str | None = None
    buffer = ""

    try:
        client_socket.settimeout(10)
        raw_name, pending_buffer = receive_line(client_socket)
        if not raw_name:
            return

        raw_name = re.sub(r"[^\w\-]", "", raw_name)[:32] or "Anon"
        if raw_name.upper() in RESERVED_NAMES:
            raw_name = "User"

        with clients_lock:
            if len(clients) >= MAX_CLIENTS:
                send(client_socket, "❌ Servidor lleno")
                return
            existing = {n for n, _ in clients.values()}
            name = raw_name
            i = 1
            while name in existing:
                name = f"{raw_name}_{i}"
                i += 1
            clients[client_socket] = (name, ip)

        log(f"[+] Conectado: {name} ({ip})")
        send(client_socket, f"✅ Bienvenido {name}")
        broadcast(f"📢 {name} se ha unido", client_socket)

        buffer = _process_pending_messages(client_socket, pending_buffer)
        client_socket.settimeout(IDLE_TIMEOUT)

        while True:
            try:
                data = client_socket.recv(BUFFER_SIZE)
            except socket.timeout:
                send(client_socket, "⏰ Timeout")
                break
            except (OSError, ConnectionResetError, BrokenPipeError):
                break
            if not data:
                break
            buffer += data.decode("utf-8", errors="ignore")
            if len(buffer) > MAX_BUFFER_ACCUM:
                send(client_socket, "❌ Mensaje demasiado largo")
                break
            buffer = _process_pending_messages(client_socket, buffer)

    finally:
        removed_name = _remove_client(client_socket)
        if removed_name:
            broadcast(f"🚫 {removed_name} ha salido")


# ─── Consola de administrador (con /kick) ─────────────────────────────────────
def admin_console() -> None:
    print("\n🖥️  Consola de administrador ACTIVADA")
    print("Comandos disponibles:")
    print("   <mensaje>               → Broadcast a todos")
    print("   /kick <usuario>         → Expulsar usuario")
    print("   /shutdown               → Apagar servidor")
    print("-" * 60)

    while True:
        try:
            command = input("Admin > ").strip()
            if not command:
                continue

            # Comando KICK
            if command.lower().startswith("/kick "):
                parts = command.split(maxsplit=1)
                if len(parts) < 2 or not parts[1].strip():
                    print("❌ Uso: /kick <usuario>")
                    continue

                target_name = parts[1].strip()
                target_socket = find_client_by_name(target_name)

                if not target_socket:
                    print(f"❌ Usuario '{target_name}' no encontrado.")
                    continue

                # Mensaje al usuario kickeado
                send(target_socket, "🚫 Has sido expulsado por el administrador")

                # Removerlo
                removed_name = _remove_client(target_socket)
                if removed_name:
                    broadcast(f"🚫 [ADMIN] {removed_name} ha sido kickeado")
                    log(f"[KICK] {removed_name} expulsado por administrador")
                continue

            # Comando SHUTDOWN
            if command.lower() in ("/shutdown", "/exit", "/quit", "/apagar"):
                log("⛔ Apagando servidor por orden del administrador...")
                with clients_lock:
                    for sock in list(clients.keys()):
                        try:
                            send(sock, "🔴 Servidor apagándose por administrador")
                            sock.close()
                        except:
                            pass
                    clients.clear()
                raise KeyboardInterrupt

            # Broadcast normal
            broadcast_msg = f"📢 [SERVIDOR] {command}"
            broadcast(broadcast_msg)
            log(f"[BROADCAST] {command}")

        except (EOFError, KeyboardInterrupt):
            break


# ─── Servidor principal ───────────────────────────────────────────────────────
def start_server() -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind((HOST, PORT))
        server.listen(MAX_CLIENTS)
        log(f"🚀 Servidor iniciado en {HOST}:{PORT}")

        console_thread = threading.Thread(target=admin_console, daemon=True)
        console_thread.start()

        while True:
            conn, addr = server.accept()
            threading.Thread(
                target=handle_client,
                args=(conn, addr),
                daemon=True
            ).start()

    except KeyboardInterrupt:
        log("⛔ Apagando servidor...")
    except Exception as e:
        log(f"❌ Error crítico: {e}")
    finally:
        with clients_lock:
            for sock in list(clients.keys()):
                try:
                    send(sock, "🔴 Servidor apagándose")
                    sock.close()
                except:
                    pass
            clients.clear()
        try:
            server.close()
        except:
            pass
        log("✅ Servidor cerrado completamente")


if __name__ == "__main__":
    start_server()