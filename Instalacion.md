
## 🚀 Instalación y Uso

1.  **Guardar el script:** Guarda el código del servidor como `server.py`.
2.  **Ejecutar el servidor:**
    ```bash
    python server.py
    ```
3.  **Conexión de clientes:** Los clientes deben apuntar a la IP local del servidor (ej. `192.168.1.15`) en el puerto `12345`.

---

## 💬 Comandos Disponibles en el Chat

| Comando | Descripción | Ejemplo |
| :--- | :--- | :--- |
| `/msg <user> <text>` | Envía un mensaje privado a un usuario específico. | `/msg Juan hola!` |
| `/list` | Muestra la lista de todos los usuarios conectados. | `/list` |
| `/help` | Muestra el menú de ayuda con los comandos. | `/help` |

---

## 🌐 Configuración de Red (Importante)

Para que el servidor sea accesible desde otros ordenadores en la misma red, asegúrate de cumplir estos requisitos:

### 1. Firewall de Windows
Es necesario abrir el puerto **12345** para tráfico TCP de entrada:
1.  Ir a **Reglas de Entrada** > **Nueva Regla**.
2.  Seleccionar **Puerto** > **TCP** > **12345**.
3.  Permitir la conexión en perfiles **Privados**.

### 2. Perfil de Red
Ambos ordenadores (servidor y cliente) deben tener su red configurada como **"Privada"** en los ajustes de red de Windows. Si está en "Pública", el PC ignorará las conexiones entrantes por seguridad.

---

## 🧠 Notas del Desarrollador (Refactorización)

Este servidor fue optimizado para corregir fallos críticos de seguridad y estabilidad:
* **Encapsulamiento:** Se migró de variables globales a una clase `ChatServer` para evitar estados compartidos corruptos.
* **Manejo de Búfer:** Se implementó una lógica de segmentación por `\n` y un límite de tamaño de búfer para prevenir ataques por saturación de RAM.
* **Cierre Atómico:** Uso de `socket.shutdown()` antes de `close()` para asegurar que el cliente reciba la señal de desconexión inmediatamente y evitar sockets "zombie".
* **Thread-Safety:** Uso de `RLock` para garantizar que la lista de clientes sea accedida de forma segura por múltiples hilos.

---