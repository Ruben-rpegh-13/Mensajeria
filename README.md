# Mensajeria

Esto es la evolucion de un servicio de mensajes usando netcat y Zenity por medio de mensajes emergentes a un servicio de Mensajeria cuasi simultaneo usando una maquina servidor y aplicaciones clientes.

# LAN Messaging Server (Python Edition)

Una implementación robusta, multihilo y segura de un servidor de mensajería diseñado específicamente para entornos de red local (LAN). Este servidor gestiona múltiples conexiones simultáneas, comandos de usuario y protecciones básicas contra ataques comunes.

---

## Características Principales

- **Multihilo:** Maneja hasta 50 clientes en paralelo mediante `threading`.
- **Gestión de Comandos:**
  - `/msg <usuario> <texto>` - Mensaje privado
  - `/list` - Ver usuarios conectados
  - `/help` - Ayuda
- **Consola de Administrador:**
  - `/kick <usuario>` - Expulsar usuario
  - `/shutdown` - Apagar servidor
  - broadcast directo - Enviar mensaje a todos
- **Robustez Senior:**
  - **Rate Limiting:** Límite de 9 msgs/segundo por cliente (token bucket).
  - **Protección Anti-DoS:** Límite de buffer para evitar desbordamiento de memoria.
  - **Sanitización:** Nombres de usuario limpios, rechazo de nombres vacíos.
  - **Gestión de Colisiones:** Renombrado automático si dos usuarios eligen el mismo nombre.
  - **Timeouts:** Desconexión automática por inactividad (5 min).
  - **Nombres Reservados:** SYSTEM, ADMIN, SERVIDOR no permitidos.

---

## Requisitos Técnicos

- **Lenguaje:** Python 3.10 o superior.
- **Librerías:** Únicamente librerías estándar (`socket`, `threading`, `datetime`).
- **Red:** Acceso a una red LAN con visibilidad entre dispositivos (Puerto **12345** TCP).

---

## Uso

```bash
python Server.py
```

El servidor escuchará en `0.0.0.0:12345` por defecto.

### Consumidores

Con cualquier cliente TCP, por ejemplo:

```bash
nc 192.168.1.x 12345
```

O desde Python:
```python
import socket
s = socket.socket()
s.connect(("192.168.1.x", 12345))
s.sendall(b"TuNombre\n")
```

---

## Configuración (Opcional)

Crear `config.json` para personalizar:

```json
{
  "host": "0.0.0.0",
  "port": 12345,
  "max_clients": 50,
  "max_msgs_per_sec": 9,
  "idle_timeout": 300
}
```