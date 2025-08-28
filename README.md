# BTR Automation WhatsApp (v1.1.0)

MÓDULO DE NOTIFICACIONES OTs - WHATSAPP
-----------------------------------------------------------
- Fecha de implementación: 26/08/2025
- Versión: 1.1
- Autor: Andrés Sánchez Serrano


## Descripción
Módulo Odoo para enviar notificaciones de Órdenes de Trabajo por **WhatsApp** (vía `npx mudslide`).

- Avisos de **nueva OT**.
- Avisos de **cambio de estado** (el cierre *Reparado* se manda desde `cierreot.py`).
- **Resumen diario** y **semanal** vía WhatsApp.

## Configuración
1. Copia `secrets.yaml.example` a `secrets.yaml` y ajusta los valores.
2. Comprueba conexión con WhatsApp: `npx mudslide groups`.
3. Reinicia Odoo y actualiza el módulo.

## Archivos clave
- `models/aperturaot.py`
- `models/cierreot.py`
- `models/resumen_diario.py`
- `models/resumen_semanal.py`
- `data/cron_jobs.xml`

## Licencia
LGPL-3
