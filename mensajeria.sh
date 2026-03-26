#!/bin/bash

# Crear FIFO seguro
FIFO=$(mktemp -u /tmp/chat_XXXXX)
mkfifo "$FIFO"

PIDS=()

cleanup() {
    rm -f "$FIFO"
    for pid in "${PIDS[@]}"; do
        kill "$pid" 2>/dev/null
    done
}
trap cleanup EXIT

# Selección de modo
MODE=$(zenity --list --title="Chat Netcat" --text="Selecciona modo:" \
  --radiolist --column="Sel" --column="Opción" \
  TRUE "Servidor" FALSE "Cliente")

[ -z "$MODE" ] && exit

# Configuración
if [[ "$MODE" == "Servidor" ]]; then
    PORT=$(zenity --entry --title="Puerto" --text="Puerto:" --entry-text="12345")
    [ -z "$PORT" ] && exit

    exec 3<> "$FIFO"

    nc -l -p "$PORT" <&3 | while read -r line; do
        zenity --notification --text="Mensaje: $line" 2>/dev/null
        echo "👤 Cliente: $line"
    done &
    PIDS+=($!)

else
    IP=$(zenity --entry --title="IP" --text="IP servidor:")
    PORT=$(zenity --entry --title="Puerto" --text="Puerto:" --entry-text="12345")

    if [ -z "$IP" ] || [ -z "$PORT" ]; then
        exit
    fi

    exec 3<> "$FIFO"

    nc "$IP" "$PORT" <&3 | while read -r line; do
        zenity --notification --text="Mensaje: $line" 2>/dev/null
        echo "👤 Servidor: $line"
    done &
    PIDS+=($!)
fi

# Envío de mensajes
while true; do
    MSG=$(zenity --entry --title="Enviar" --text="Mensaje (Cancelar para salir):")

    [ $? -ne 0 ] && break

    if [ -n "$MSG" ]; then
        echo "🟢 Tú: $MSG"
        echo "$MSG" >&3
    fi
done
