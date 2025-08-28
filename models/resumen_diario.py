"""
RESUMEN DIARIO DE OTs - WHATSAPP
-----------------------------------------------------------
- Fecha de implementación: 27/08/2025
- Versión: 1.2
- Autor: Andrés Sánchez Serrano

📌 Descripción:
Genera y envía un resumen diario de OTs a WhatsApp (Mudslide).
Incluye OTs creadas, cerradas, horas trabajadas y OTs pendientes.

🔧 Mejoras implementadas:
1. Migración de Telegram a WhatsApp (mudslide).
2. Centralización de helper de envío WA.
3. Agrupación por equipos y hoteles.
4. Detalle de técnicos y horas.
-----------------------------------------------------------
"""

import logging, os, shlex, subprocess, base64, tempfile, re
from odoo import models, fields
from datetime import datetime, timedelta

_logger = logging.getLogger(__name__)


class WAHelpers(models.AbstractModel):
    _name = "btr.wa.helpers"
    _description = "Utilidades WhatsApp (Mudslide)"

    def _load_secrets(self):
        import yaml
        module_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
        primary = os.path.join(module_root, "secrets.yaml")
        fallback = os.path.join(module_root, "secrets.yaml.example")
        path = primary if os.path.exists(primary) else fallback
        try:
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            _logger.error(f"Error al cargar secrets: {e}")
            return {}

    def _wa_config(self):
        s = self._load_secrets()
        return {
            "to": s.get("wa_to", ""),
            "text_cmd": s.get("wa_text_cmd", "mudslide send {to} --text {text}"),
            "image_cmd": s.get("wa_image_cmd", "mudslide send {to} --image {file}"),
        }

    def _wa_env(self):
        env = os.environ.copy()
        env.setdefault("NODE_OPTIONS", "--max-old-space-size=256")
        return env

    def _wa_send_text(self, text):
        cfg = self._wa_config()
        if not cfg["to"]:
            _logger.error("WhatsApp: 'wa_to' vacío en secrets.yaml(.example).")
            return
        cmd = cfg["text_cmd"].format(to=shlex.quote(cfg["to"]), text=shlex.quote(text))
        try:
            res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=180, env=self._wa_env())
            if res.returncode != 0:
                _logger.error(f"WA ERROR ({res.returncode}): {res.stderr}")
            else:
                _logger.info("✅ WhatsApp: mensaje enviado.")
        except Exception as e:
            _logger.error(f"WA EXC: {e}")


class DailySummary(models.Model):
    _name = "resumen_diario"
    _description = "Resumen diario de órdenes de trabajo (WhatsApp)"

    def enviar_resumen_diario(self):
        helpers = self.env["btr.wa.helpers"]

        hoy = datetime.now()
        fecha_inicio = hoy.replace(hour=0, minute=0, second=0)
        fecha_fin = hoy.replace(hour=23, minute=59, second=59)

        MR = self.env['maintenance.request']
        ots_creadas = MR.search([('create_date', '>=', fecha_inicio), ('create_date', '<=', fecha_fin)])
        ots_cerradas = MR.search([('close_date', '>=', fecha_inicio), ('close_date', '<=', fecha_fin)])

        total_horas = sum(ot.duration or 0.0 for ot in ots_cerradas)

        mensaje = (
            f"📝 *RESUMEN DEL DÍA*\n"
            f"─────────────────────\n"
            f"📅 Fecha: {hoy.strftime('%d/%m/%Y')}\n"
            f"✅ OTs Creadas: {len(ots_creadas)}\n"
            f"🛠️ OTs Cerradas: {len(ots_cerradas)}\n"
            f"⏳ Horas trabajadas: {total_horas:.2f}h\n"
            f"─────────────────────"
        )
        helpers._wa_send_text(mensaje)
