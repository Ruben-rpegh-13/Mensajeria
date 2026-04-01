import socket
import threading
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
HOST = "0.0.0.0"
PORT = 12345
BUFFER_SIZE = 4096

clients = {}                      # socket -> (nombre, ip)
clients_lock = threading.RLock()


def log(msg: str):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


# ==================== UTILIDADES ====================

def send(client_socket, message: str):
    """Envío seguro con delimitador"""
    try:
        client_socket.sendall((message + "\n").encode('utf-8'))
    except (OSError, ConnectionResetError):
        _internal_remove(client_socket)


def broadcast(message: str, sender_socket=None):
    """Envía mensaje a todos excepto remitente"""
    with clients_lock:
        for client_socket in list(clients.keys()):
            if client_socket == sender_socket:
                continue
            send(client_socket, message)


def find_client_by_name(name: str):
    """Busca un cliente por nombre"""
    with clients_lock:
        for sock, (n, _) in clients.items():
            if n == name:
                return sock
    return None


def _internal_remove(client_socket):
    if client_socket in clients:
        name, ip = clients.pop(client_socket)
        log(f"[-] Desconectado: {name} ({ip})")
        try:
            client_socket.close()
        except OSError:
            pass
        return name
    return None


def remove_client(client_socket):
    with clients_lock:
        return _internal_remove(client_socket)


# ==================== LÓGICA CLIENTE ====================

def process_message(client_socket, msg: str):
    with clients_lock:
        name, ip = clients.get(client_socket, ("Anon", "??"))

    # ==================== /msg PRIVADO ====================
    if msg.startswith("/msg "):
        parts = msg.split(" ", 2)

        if len(parts) < 3:
            send(client_socket, "❌ Uso: /msg usuario mensaje")
            return

        target_name = parts[1]
        private_msg = parts[2]

        target_socket = find_client_by_name(target_name)

        if not target_socket:
            send(client_socket, f"❌ Usuario '{target_name}' no encontrado")
            return

        # Enviar al receptor
        send(target_socket, f"💬 [Privado] {name}: {private_msg}")

        # Confirmación al emisor
        send(client_socket, f"📩 [A {target_name}]: {private_msg}")

        log(f"[PRIVADO] {name} -> {target_name}: {private_msg}")
        return

    # ==================== MENSAJE NORMAL ====================
    full_msg = f"{name}@{ip}: {msg}"
    log(full_msg)
    broadcast(full_msg, client_socket)


def handle_client(client_socket, addr):
    ip = addr[0]
    name = "Anon"
    buffer = ""

    try:
        # ==================== HANDSHAKE ====================
        send(client_socket, "Introduce tu nombre:")

        data = client_socket.recv(BUFFER_SIZE)
        if not data:
            return

        raw_name = data.decode('utf-8', errors='ignore').strip()[:20] or "Anon"

        with clients_lock:
            name = raw_name
            counter = 1
            existing_names = [n for n, _ in clients.values()]

            while name in existing_names:
                name = f"{raw_name}_{counter}"
                counter += 1

            clients[client_socket] = (name, ip)

        log(f"[+] Conectado: {name} ({ip})")
        broadcast(f"📢 [SYSTEM] {name} se ha unido al chat")

        client_socket.settimeout(300)

        # ==================== LOOP PRINCIPAL ====================
        while True:
            try:
                data = client_socket.recv(BUFFER_SIZE)

                if not data:
                    break

                buffer += data.decode('utf-8', errors='ignore')

                while "\n" in buffer:
                    msg, buffer = buffer.split("\n", 1)
                    msg = msg.strip()[:256]

                    if msg:
                        process_message(client_socket, msg)

            except socket.timeout:
                continue  # no desconectar por timeout

    except (ConnectionResetError, OSError):
        pass

    finally:
        removed_name = remove_client(client_socket)

        if removed_name:
            broadcast(f"🚫 [SYSTEM] {removed_name} ha salido del chat")

        try:
            client_socket.close()
        except (OSError, AttributeError):
            pass


# ==================== SERVIDOR ====================

def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((HOST, PORT))
            server.listen(20)

            log(f"🚀 Servidor LAN iniciado en {HOST}:{PORT}")
            log("Presiona Ctrl+C para detener.\n")

            while True:
                conn, addr = server.accept()

                threading.Thread(
                    target=handle_client,
                    args=(conn, addr),
                    daemon=True
                ).start()

        except KeyboardInterrupt:
            log("\n⛔ Servidor detenido por el administrador.")
        except Exception as e:
            log(f"❌ Error crítico: {e}")


if __name__ == "__main__":
    start_server()