"""
RESUMEN SEMANAL DE OTs - WHATSAPP
-----------------------------------------------------------
- Fecha de implementación: 27/08/2025
- Versión: 1.2
- Autor: Andrés Sánchez Serrano

📌 Descripción:
Genera y envía un resumen semanal de OTs a WhatsApp (Mudslide).
Muestra OTs creadas, cerradas, horas y comparativa con la semana anterior.

🔧 Mejoras implementadas:
1. Migración de Telegram a WhatsApp (mudslide).
2. Centralización de helper de envío WA.
3. Comparativa con semana anterior.
4. Detalle de técnicos y horas.
-----------------------------------------------------------
"""

import logging, os, shlex, subprocess, base64, tempfile
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


class WeeklySummary(models.Model):
    _name = "resumen_semanal"
    _description = "Resumen semanal de órdenes de trabajo (WhatsApp)"

    def enviar_resumen_semanal(self):
        helpers = self.env["btr.wa.helpers"]

        hoy = fields.Date.today()
        inicio_semana = hoy - timedelta(days=hoy.weekday())
        fin_semana = inicio_semana + timedelta(days=6)
        inicio_anterior = inicio_semana - timedelta(days=7)
        fin_anterior = inicio_semana - timedelta(days=1)

        MR = self.env['maintenance.request']

        # Semana actual
        ots_creadas = MR.search_count([('create_date', '>=', inicio_semana), ('create_date', '<=', fin_semana)])
        ots_cerradas = MR.search([('close_date', '>=', inicio_semana), ('close_date', '<=', fin_semana)])
        horas = sum(ot.duration or 0 for ot in ots_cerradas)

        # Semana anterior
        ots_cerradas_ant = MR.search([('close_date', '>=', inicio_anterior), ('close_date', '<=', fin_anterior)])
        horas_ant = sum(ot.duration or 0 for ot in ots_cerradas_ant)

        diff_ots = len(ots_cerradas) - len(ots_cerradas_ant)
        diff_horas = horas - horas_ant

        # Mensaje
        mensaje = (
            f"📊 *RESUMEN SEMANAL*\n"
            f"─────────────────────\n"
            f"📅 Semana: {inicio_semana.strftime('%d/%m')} - {fin_semana.strftime('%d/%m')}\n"
            f"✅ OTs creadas: {ots_creadas}\n"
            f"🛠️ OTs cerradas: {len(ots_cerradas)} ({'+' if diff_ots>=0 else ''}{diff_ots} vs semana ant.)\n"
            f"⏳ Horas: {horas:.2f}h ({'+' if diff_horas>=0 else ''}{diff_horas:.2f} vs ant.)\n"
            f"─────────────────────"
        )
        helpers._wa_send_text(mensaje)

