import socket
import threading
import sys
import argparse

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 12345
BUFFER_SIZE = 8192


def listen_for_messages(client_socket: socket.socket, stop_event: threading.Event):
    buffer = ""

    while not stop_event.is_set():
        try:
            data = client_socket.recv(BUFFER_SIZE)

            if not data:
                print("\n[!] Conexión cerrada por el servidor.")
                break

            buffer += data.decode('utf-8', errors='replace')

            while "\n" in buffer:
                mensaje, buffer = buffer.split("\n", 1)

                sys.stdout.write("\r\033[K")
                print(mensaje)
                sys.stdout.write("> ")
                sys.stdout.flush()

        except socket.timeout:
            # 👈 NO cerrar conexión por timeout
            continue

        except (ConnectionResetError, OSError):
            print("\n[!] Conexión perdida con el servidor.")
            break

    stop_event.set()
    print("\n[!] Hilo de recepción finalizado.")


def start_client():
    parser = argparse.ArgumentParser(description="Cliente de chat LAN")
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("-p", "--port", type=int, default=DEFAULT_PORT)
    args = parser.parse_args()

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    # 🔥 mejora clave VS Code / sockets
    client.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # 🔥 timeout no bloqueante
    client.settimeout(1)

    try:
        client.connect((args.host, args.port))
        print(f"✅ Conectado a {args.host}:{args.port}")
    except Exception as e:
        print(f"❌ Error de conexión: {e}")
        return

    # 👇 evitar bloqueo en recv inicial
    name = input("Introduce tu nombre: ").strip() or "Anon"
    client.sendall((name + "\n").encode('utf-8'))

    stop_event = threading.Event()

    thread = threading.Thread(
        target=listen_for_messages,
        args=(client, stop_event),
        daemon=True
    )
    thread.start()

    print("\n" + "═" * 60)
    print("🎉 CHAT LAN ACTIVO")
    print("   /msg <usuario> <mensaje>")
    print("   exit / salir")
    print("═" * 60 + "\n")

    try:
        while not stop_event.is_set():
            try:
                msg = input("> ")
            except EOFError:
                break

            if msg.lower() in {"exit", "salir", "quit"}:
                break

            if msg.startswith("/msg "):
                parts = msg.split(" ", 2)
                if len(parts) < 3:
                    print("❌ Uso: /msg usuario mensaje")
                    continue

            if msg.strip():
                client.sendall((msg + "\n").encode('utf-8'))

    except KeyboardInterrupt:
        print("\n[!] Interrumpido por el usuario.")

    finally:
        stop_event.set()

        try:
            client.shutdown(socket.SHUT_RDWR)
        except:
            pass

        client.close()
        print("\n👋 Te has desconectado.")


if __name__ == "__main__":
    start_client()