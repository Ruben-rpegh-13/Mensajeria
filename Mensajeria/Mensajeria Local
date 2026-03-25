Método con netcat (recomendado)
En el PC receptor (el que recibirá el mensaje), inicia un listener en un puerto específico:

nc -l 3333

En el PC emisor (el que enviará el mensaje), conecta al IP del receptor usando el mismo puerto:

nc 192.168.1.XX 3333

Reemplaza 192.168.1.XX con la IP real del PC receptor (puedes obtenerla con hostname -I o ip a)

----------------------------------------------------------

Alternativa con notificación gráfica (más visual)

Si quieres que el mensaje aparezca como una ventana emergente (como un MsgBox), puedes combinar netcat con zenity o notify-send.

Instala ZENITY en ambos PCs

sudo apt install zenity

Crea un script en el receptor (daemon.sh)

#!/bin/bash
port=3333
nc -l $port | while read msg; do zenity --info --text "$msg"; done

Hazlo ejecutable:

chmod +x daemon.sh

Ejecuta el script en segundo plano:

./daemon.sh &

Automatiza el inicio con "Aplicaciones al inicio" en MATE para que siempre esté activo. 

Ahora manda el mensaje

echo "Tu mensaje aquí" | nc 192.168.1.XX 3333   






