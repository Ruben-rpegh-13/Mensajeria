import socket
import threading
import sys
import argparse
import select

# ─── Configuración ────────────────────────────────────────────────────────────
DEFAULT_HOST    = "127.0.0.1"
DEFAULT_PORT    = 12345
BUFFER_SIZE     = 8192
MAX_MSG_LENGTH  = 1024      # Límite de longitud de mensaje
SOCKET_TIMEOUT  = 1.0       # Timeout para recv (segundos)
INPUT_TIMEOUT   = 0.2       # Timeout para select() en stdin

# ─── Lock global para escritura en stdout ─────────────────────────────────────
# Evita que el hilo receptor y el main thread mezclen texto en la consola.
print_lock = threading.Lock()


def safe_print(msg: str, reprint_prompt: bool = True) -> None:
    """Imprime un mensaje borrando el prompt activo y reimprimiéndolo después."""
    with print_lock:
        sys.stdout.write("\r\033[K")    # Borra la línea actual (prompt)
        print(msg)
        if reprint_prompt:
            sys.stdout.write("> ")
            sys.stdout.flush()


# ─── Hilo receptor ────────────────────────────────────────────────────────────

def listen_for_messages(
    client_socket: socket.socket,
    stop_event: threading.Event
) -> None:
    """
    Escucha mensajes entrantes del servidor en un hilo dedicado.
    Usa un buffer para reconstruir mensajes delimitados por '\\n'.
    """
    buffer = ""

    while not stop_event.is_set():
        try:
            data = client_socket.recv(BUFFER_SIZE)

            if not data:
                # El servidor cerró la conexión limpiamente.
                safe_print("\n[!] El servidor cerró la conexión.", reprint_prompt=False)
                break

            buffer += data.decode("utf-8", errors="replace")

            # Procesar todos los mensajes completos del buffer
            while "\n" in buffer:
                message, buffer = buffer.split("\n", 1)
                message = message.strip()
                if message:
                    safe_print(message)

        except socket.timeout:
            # Timeout normal → volver a comprobar stop_event
            continue

        except (ConnectionResetError, ConnectionAbortedError):
            safe_print("\n[!] Conexión reiniciada por el servidor.", reprint_prompt=False)
            break

        except OSError as e:
            # El socket fue cerrado desde el main thread al hacer shutdown()
            if not stop_event.is_set():
                safe_print(f"\n[!] Error de socket: {e}", reprint_prompt=False)
            break

    stop_event.set()


# ─── Cliente ──────────────────────────────────────────────────────────────────

class ChatClient:
    HELP_TEXT = (
        "\n" + "═" * 50 + "\n"
        "  Comandos disponibles:\n"
        "  /msg <usuario> <texto>  → Mensaje privado\n"
        "  /list                  → Listar usuarios\n"
        "  /help                  → Mostrar esta ayuda\n"
        "  exit / salir / quit    → Desconectarse\n"
        "═" * 50
    )

    def __init__(self, host: str, port: int) -> None:
        self.host = host
        self.port = port
        self.socket: socket.socket | None = None
        self.stop_event = threading.Event()
        self.username = ""

    # ── Conexión ─────────────────────────────────────────────────────────────

    def connect(self) -> bool:
        """Establece la conexión TCP con el servidor."""
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.socket.settimeout(SOCKET_TIMEOUT)

        try:
            self.socket.connect((self.host, self.port))
            print(f"✅ Conectado a {self.host}:{self.port}")
            return True
        except ConnectionRefusedError:
            print(f"❌ El servidor rechazó la conexión en {self.host}:{self.port}")
        except socket.timeout:
            print(f"❌ Timeout al intentar conectar con {self.host}:{self.port}")
        except OSError as e:
            print(f"❌ Error de red: {e}")

        self.socket.close()
        return False

    # ── Registro ──────────────────────────────────────────────────────────────

    def register_name(self) -> None:
        """Solicita y envía el nombre de usuario al servidor."""
        raw = input("Introduce tu nombre: ").strip()
        # Sanitizar: eliminar caracteres de control y limitar longitud
        name = "".join(c for c in raw if c.isprintable() and c not in "\n\r")[:32]
        self.username = name or "Anon"
        self._send(self.username)
        print(f"👤 Registrado como: {self.username}")

    # ── Envío seguro ─────────────────────────────────────────────────────────

    def _send(self, text: str) -> bool:
        """
        Envía texto al servidor con delimitador '\\n'.
        Devuelve False si falla el envío.
        """
        if not text.strip():
            return True

        # Truncar si el mensaje supera el límite
        if len(text) > MAX_MSG_LENGTH:
            safe_print(f"⚠️  Mensaje truncado a {MAX_MSG_LENGTH} caracteres.")
            text = text[:MAX_MSG_LENGTH]

        try:
            self.socket.sendall((text + "\n").encode("utf-8"))
            return True
        except (BrokenPipeError, ConnectionResetError):
            safe_print("\n[!] No se pudo enviar: conexión perdida.", reprint_prompt=False)
            self.stop_event.set()
            return False
        except OSError as e:
            safe_print(f"\n[!] Error al enviar: {e}", reprint_prompt=False)
            self.stop_event.set()
            return False

    # ── Procesado de comandos ────────────────────────────────────────────────

    def _handle_command(self, msg: str) -> bool:
        """
        Procesa comandos especiales.
        Devuelve True si el mensaje debe enviarse al servidor,
        False si fue procesado localmente.
        """
        lower = msg.lower().strip()

        if lower in {"exit", "salir", "quit"}:
            return False  # Señal de salida manejada en el loop principal

        if lower == "/help":
            safe_print(self.HELP_TEXT)
            return False

        if lower == "/list":
            return True  # El servidor gestiona este comando

        if msg.startswith("/msg "):
            parts = msg.split(" ", 2)
            if len(parts) < 3 or not parts[2].strip():
                safe_print("❌ Uso: /msg <usuario> <mensaje>")
                return False
            return True

        return True  # Mensaje normal → enviar

    # ── Loop principal ────────────────────────────────────────────────────────

    def _input_loop(self) -> None:
        """
        Lee input del usuario usando select() para no bloquear
        indefinidamente, permitiendo que stop_event corte el loop
        aunque el usuario no haya escrito nada.
        """
        sys.stdout.write("> ")
        sys.stdout.flush()

        while not self.stop_event.is_set():
            # Esperar hasta INPUT_TIMEOUT segundos antes de re-chequear stop_event
            ready, _, _ = select.select([sys.stdin], [], [], INPUT_TIMEOUT)

            if self.stop_event.is_set():
                break

            if not ready:
                continue

            try:
                msg = sys.stdin.readline()
            except EOFError:
                break

            if not msg:   # EOF real (Ctrl-D)
                break

            msg = msg.rstrip("\n").rstrip("\r")
            lower = msg.lower().strip()

            if lower in {"exit", "salir", "quit"}:
                break

            if msg.strip():
                should_send = self._handle_command(msg)
                if should_send:
                    if not self._send(msg):
                        break

            with print_lock:
                sys.stdout.write("> ")
                sys.stdout.flush()

    # ── Punto de entrada ─────────────────────────────────────────────────────

    def run(self) -> None:
        """Conecta, registra el usuario y arranca los hilos."""
        if not self.connect():
            return

        self.register_name()

        # Hilo receptor (daemon: muere si el proceso principal termina)
        recv_thread = threading.Thread(
            target=listen_for_messages,
            args=(self.socket, self.stop_event),
            daemon=True,
            name="RecvThread",
        )
        recv_thread.start()

        print(self.HELP_TEXT)

        try:
            self._input_loop()
        except KeyboardInterrupt:
            print("\n[!] Interrumpido por el usuario (Ctrl+C).")
        finally:
            self._shutdown(recv_thread)

    # ── Cierre limpio ────────────────────────────────────────────────────────

    def _shutdown(self, recv_thread: threading.Thread) -> None:
        """Cierra el socket y espera que el hilo receptor termine."""
        self.stop_event.set()

        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass

        self.socket.close()

        # Esperar al hilo receptor (máximo 2 s)
        recv_thread.join(timeout=2.0)

        print("\n👋 Desconectado. ¡Hasta luego!")


# ─── Entrada ──────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(description="Cliente de chat LAN")
    parser.add_argument(
        "--host", default=DEFAULT_HOST,
        help=f"IP del servidor (por defecto: {DEFAULT_HOST})"
    )
    parser.add_argument(
        "-p", "--port", type=int, default=DEFAULT_PORT,
        help=f"Puerto del servidor (por defecto: {DEFAULT_PORT})"
    )
    args = parser.parse_args()

    client = ChatClient(host=args.host, port=args.port)
    client.run()


if __name__ == "__main__":
    main()