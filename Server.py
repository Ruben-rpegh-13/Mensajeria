import socket
import threading

# Configuración
HOST = "192.168.0.47"
PORT = 12345

# Recursos compartidos y Thread Safety
clients = {}  # socket -> (nombre, ip)
clients_lock = threading.Lock()

def broadcast(message, sender_socket=None):
    """Envía mensaje a todos los clientes de forma segura."""
    msg_bytes = message.encode('utf-8')
    
    with clients_lock:
        # Iteramos sobre una copia de las llaves para poder borrar si falla
        for client in list(clients.keys()):
            if client != sender_socket:
                try:
                    client.send(msg_bytes)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    remove_client(client)

def remove_client(client_socket):
    """Elimina al cliente del diccionario y cierra el socket."""
    with clients_lock:
        if client_socket in clients:
            name, ip = clients[client_socket]
            print(f"[-] Desconectado: {name} ({ip})")
            del clients[client_socket]
            try:
                client_socket.close()
            except OSError:
                pass

def handle_client(client_socket, addr):
    ip = addr[0]
    name = "Anon"
    
    try:
        # 1. Fase de Handshake (Nombre)
        client_socket.send("Introduce tu nombre: ".encode('utf-8'))
        data = client_socket.recv(1024)
        if not data:
            client_socket.close()
            return
            
        name = data.decode('utf-8').strip() or "Anon"
        
        with clients_lock:
            clients[client_socket] = (name, ip)
        
        print(f"[+] Conectado: {name} ({ip})")
        broadcast(f"📢 [SYSTEM] {name} se ha unido al chat")

        # 2. Loop de mensajes
        while True:
            data = client_socket.recv(1024)
            if not data:
                break
                
            msg = data.decode('utf-8')
            full_msg = f"{name}@{ip}: {msg}"
            print(full_msg)
            broadcast(full_msg, client_socket)

    except (ConnectionResetError, UnicodeDecodeError):
        pass # Errores comunes de desconexión o caracteres extraños
    finally:
        # Aseguramos que el cliente sea removido y se avise a los demás
        remove_client(client_socket)
        broadcast(f"🚫 [SYSTEM] {name} ha salido del chat")

def start_server():
    # Usamos contexto 'with' para asegurar que el socket se cierre al terminar
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
        # SO_REUSEADDR permite reiniciar el servidor sin esperar al kernel
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        try:
            server.bind((HOST, PORT))
            server.listen()
            print(f"🚀 Servidor LAN iniciado en {HOST}:{PORT}")
            print("Presiona Ctrl+C para detener.")

            while True:
                client_socket, addr = server.accept()
                thread = threading.Thread(
                    target=handle_client,
                    args=(client_socket, addr),
                    daemon=True # El hilo muere si el programa principal se cierra
                )
                thread.start()
        except KeyboardInterrupt:
            print("\nTerminando servidor...")
        except Exception as e:
            print(f"Error crítico en el servidor: {e}")

if __name__ == "__main__":
    start_server()