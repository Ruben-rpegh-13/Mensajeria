import socket
import threading
import sys

# ==================== CONFIGURACIÓN ====================
SERVER_HOST = "127.0.0.1"  # Cambia a tu IP LAN
PORT = 12345

stop_flag = False  # Para terminar el hilo de escucha

def listen_for_messages(client_socket):
    """Hilo para recibir mensajes del servidor."""
    global stop_flag
    while not stop_flag:
        try:
            message = client_socket.recv(1024).decode('utf-8')
            if not message:
                print("\n[!] El servidor cerró la conexión.")
                stop_flag = True
                break
            print(f"\r{message}\n> ", end="")
        except (ConnectionResetError, OSError):
            print("\n[!] Conexión perdida con el servidor.")
            stop_flag = True
            break

def start_client():
    global stop_flag
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    
    try:
        client.connect((SERVER_HOST, PORT))
    except ConnectionRefusedError:
        print(f"❌ No se encontró el servidor en {SERVER_HOST}:{PORT}.")
        return

    # 1. Registro (Handshake)
    prompt = client.recv(1024).decode('utf-8')
    name = input(prompt).strip()[:20] or "Anon"
    client.sendall(name.encode('utf-8'))

    # 2. Hilo de recepción
    threading.Thread(target=listen_for_messages, args=(client,), daemon=True).start()

    print("\n--- CHAT CONECTADO ---")
    print("Escribe tus mensajes y pulsa Enter. Para salir escribe 'exit'.\n")

    # 3. Bucle de envío
    try:
        while not stop_flag:
            msg = input("> ")
            if msg.lower() == "exit":
                stop_flag = True
                break
            if msg.strip():
                try:
                    client.sendall(msg.encode('utf-8'))
                except (OSError, ConnectionResetError):
                    print("\n[!] Error enviando mensaje. Conexión perdida.")
                    stop_flag = True
                    break
    except KeyboardInterrupt:
        stop_flag = True
    finally:
        client.close()
        print("\n👋 Te has desconectado del chat.")

if __name__ == "__main__":
    start_client()