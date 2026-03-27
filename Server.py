import socket
import threading
from datetime import datetime

# ==================== CONFIGURACIÓN ====================
HOST = "0.0.0.0"      # Escucha en toda la red local
PORT = 12345

# Recursos compartidos y Thread Safety
clients = {}                      # socket -> (nombre, ip)
clients_lock = threading.RLock()  # RLock evita deadlock


def log(msg: str):
    """Logging con timestamp para monitorear el servidor."""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")


def broadcast(message: str, sender_socket=None):
    """Envía un mensaje a todos excepto al remitente."""
    msg_bytes = message.encode('utf-8')

    with clients_lock:
        for client_socket in list(clients.keys()):
            if client_socket == sender_socket:
                continue
            try:
                client_socket.sendall(msg_bytes)
            except (OSError, ConnectionResetError):
                # Limpieza silenciosa si el envío falla
                _internal_remove(client_socket)


def _internal_remove(client_socket):
    """Lógica interna de limpieza (debe llamarse CON el lock adquirido)."""
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
    """Interfaz pública para eliminar clientes con seguridad de hilos."""
    with clients_lock:
        return _internal_remove(client_socket)


def handle_client(client_socket, addr):
    ip = addr[0]
    name = "Anon"

    try:
        # 1. Handshake - Registro de usuario
        client_socket.sendall(b"Introduce tu nombre: ")
        data = client_socket.recv(1024)
        if not data:
            return

        # Nombre limpio y limitado
        raw_name = data.decode('utf-8', errors='ignore').strip()[:20] or "Anon"

        with clients_lock:
            # Garantizar nombre único (todo dentro del mismo lock)
            name = raw_name
            counter = 1
            existing_names = [n for n, _ in clients.values()]
            while name in existing_names:
                name = f"{raw_name}_{counter}"
                counter += 1
            clients[client_socket] = (name, ip)

        log(f"[+] Conectado: {name} ({ip})")
        broadcast(f"📢 [SYSTEM] {name} se ha unido al chat")

        # Activamos timeout SOLO después del handshake
        client_socket.settimeout(300)  # 5 minutos de inactividad

        # 2. Bucle principal de mensajes
        while True:
            data = client_socket.recv(1024)
            if not data:
                break

            msg = data.decode('utf-8', errors='ignore').strip()[:256]
            if msg:
                full_msg = f"{name}@{ip}: {msg}"
                log(full_msg)
                broadcast(full_msg, client_socket)

    except socket.timeout:
        log(f"[!] Timeout por inactividad: {name} ({ip})")
    except (ConnectionResetError, OSError):
        pass  # desconexiones normales
    finally:
        # Limpieza siempre
        removed_name = remove_client(client_socket)
        if removed_name:
            broadcast(f"🚫 [SYSTEM] {removed_name} ha salido del chat")

        # Cerramos el socket siempre (por si nunca se registró)
        try:
            client_socket.close()
        except (OSError, AttributeError):
            pass


def start_server():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        try:
            server.bind((HOST, PORT))
            server.listen(20)  # Más conexiones simultáneas en LAN
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