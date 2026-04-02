# Mensajeria
Esto es la evolucion de un servicio de mensajes usando netcat y Zenity por medio de mensajes emergentes a un servicio de Mensajeria cuasi simultaneo usando una maquina servidor y aplicaciones clientes 

# 🚀 LAN Messaging Server (Python Edition)

Una implementación robusta, multihilo y segura de un servidor de mensajería diseñado específicamente para entornos de red local (LAN). Este servidor gestiona múltiples conexiones simultáneas, comandos de usuario y protecciones básicas contra ataques comunes.

---

## ✨ Características Principales

* **Multihilo:** Maneja hasta 50 clientes en paralelo mediante `threading`.
* **Gestión de Comandos:** Soporte nativo para mensajes privados, lista de usuarios y ayuda.
* **Robustez Senior:**
    * **Protección Anti-DoS:** Límite estricto de búfer para evitar desbordamiento de memoria.
    * **Gestión de Colisiones:** Renombrado automático si dos usuarios eligen el mismo nombre.
    * **Timeouts:** Desconexión automática por inactividad (5 min por defecto).
* **Arquitectura Limpia:** Código encapsulado en una clase orientada a objetos para facilitar su escalabilidad y mantenimiento.

---

## 🛠️ Requisitos Técnicos

* **Lenguaje:** Python 3.10 o superior.
* **Librerías:** Únicamente librerías estándar (`socket`, `threading`, `datetime`).
* **Red:** Acceso a una red LAN con visibilidad entre dispositivos (Puerto **12345** TCP).

---