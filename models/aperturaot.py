# -*- coding: utf-8 -*-
"""
MÓDULO DE NOTIFICACIONES OTs - WHATSAPP
-----------------------------------------------------------
- Fecha de implementación: 27/08/2025
- Versión: 1.2
- Autor: Andrés Sánchez Serrano

📌 Descripción:
Envía notificaciones a WhatsApp cuando se crea una OT y cuando cambia de estado
(salvo el cierre "Reparado", que lo gestiona cierreot.py).

🔧 Mejoras implementadas:
1. Migración completa a WhatsApp (mudslide) sin Telegram.
2. Uso de secrets.yaml con fallback a secrets.yaml.example.
3. Adjuntos de imágenes en la creación de OT.
4. Código autónomo: no depende de helpers externos ni de otros modelos.
-----------------------------------------------------------
"""
import logging
import re
import base64
import os
import shlex
import tempfile
import subprocess
from datetime import datetime

from odoo import models, api

_logger = logging.getLogger(__name__)


# ===================== Utilidades internas (WA + secrets) =====================
def _module_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _load_secrets_local():
    """Lee secrets.yaml (o el .example) desde la raíz del módulo."""
    import yaml
    primary = os.path.join(_module_root(), "secrets.yaml")
    fallback = os.path.join(_module_root(), "secrets.yaml.example")
    path = primary if os.path.exists(primary) else fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
            return data
    except Exception as e:
        _logger.error(f"Error al cargar secrets: {e}")
        return {}

def _wa_config():
    s = _load_secrets_local()
    return {
        "to": s.get("wa_to", ""),  # ej.: "1203...@g.us"
        "text_cmd": s.get("wa_text_cmd", "npx mudslide@latest send {to} {text}"),
        "image_cmd": s.get("wa_image_cmd", "npx mudslide@latest send {to} --image {file}"),
        "timeout": int(s.get("wa_timeout_sec", 120)),
    }

def _wa_send_text(text):
    cfg = _wa_config()
    if not cfg["to"]:
        _logger.error("WhatsApp: 'wa_to' vacío en secrets.yaml(.example).")
        return
    # Importante: mudslide acepta: npx mudslide@latest send <to> "<mensaje>"
    cmd = cfg["text_cmd"].format(
        to=shlex.quote(cfg["to"]),
        text=shlex.quote(text),
    )
    try:
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=cfg["timeout"])
        if res.returncode != 0:
            _logger.error(f"WA ERROR ({res.returncode}): {res.stderr}")
        else:
            _logger.info("✅ WhatsApp: mensaje de texto enviado.")
    except subprocess.TimeoutExpired:
        _logger.error(f"WA EXC: El envío por WhatsApp superó {cfg['timeout']} segundos (timeout).")
    except Exception as e:
        _logger.error(f"WA EXC: {e}")

def _wa_send_image_bytes(filename, data_b64):
    cfg = _wa_config()
    if not cfg["to"]:
        _logger.error("WhatsApp: 'wa_to' vacío en secrets.yaml(.example).")
        return
    try:
        raw = base64.b64decode(data_b64)
        ext = os.path.splitext(filename or '')[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(raw)
            tmp_path = tmp.name
        cmd = cfg["image_cmd"].format(
            to=shlex.quote(cfg["to"]),
            file=shlex.quote(tmp_path),
        )
        res = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=cfg["timeout"])
        if res.returncode != 0:
            _logger.error(f"WA IMG ERROR ({res.returncode}): {res.stderr}")
        else:
            _logger.info(f"✅ WhatsApp: imagen enviada ({filename}).")
    except subprocess.TimeoutExpired:
        _logger.error(f"WA IMG EXC: Envío de imagen superó {cfg['timeout']} segundos (timeout).")
    except Exception as e:
        _logger.error(f"WA IMG EXC: {e}")


# =============================== Modelo principal ==============================
class MaintenanceRequest(models.Model):
    _inherit = "maintenance.request"

    # -------------------------- Utilidades de formato --------------------------
    def _convertir_html_a_markdown(self, html_text):
        html_text = re.sub(r'<ul[^>]*>', '', html_text or '')
        html_text = re.sub(r'</ul>', '', html_text)
        html_text = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1', html_text)
        html_text = re.sub(r'<[^>]+>', '', html_text)
        return (html_text or "").strip()

    # ------------------------------ Envíos WA ----------------------------------
    def enviar_alerta_ot(self, tipo="nueva", estado_anterior=None, estado_nuevo=None):
        _logger.info(f"📢 Enviando notificación WA para OT {self.code} (tipo={tipo}).")

        resumen_ot = self.name or "Sin resumen"
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        enlace_ot = f"{base_url}/web#id={self.id}&model=maintenance.request&view_type=form"

        # Cambios de estado (excepto Reparado que lo gestiona cierreot.py)
        if tipo == "estado" and estado_anterior and estado_nuevo:
            if estado_nuevo.lower() == "reparado":
                _logger.info("🔁 'Reparado' lo gestiona cierreot.py. No se envía desde aperturaot.py.")
                return
            mensaje = (
                f"🛠 CAMBIO DE ESTADO # {self.code}\n"
                f"─────────────V3───────────\n"
                f"🔄 *De:* {estado_anterior}  ➡️  *A:* {estado_nuevo}\n"
                f"📝 *Resumen:* {resumen_ot}\n"
                f"🔗 Abrir OT: {enlace_ot}\n"
            )
            _wa_send_text(mensaje)
            return

        # Nueva OT
        tecnico = self.user_id.name or "Sin técnico asignado"
        hotel = self.category_id.name or "No especificado"
        estancia = self.equipment_id.name or "No asignado"
        equipo_mantenimiento = self.maintenance_team_id.name or "No asignado"
        fecha_creacion = self.create_date.strftime('%d/%m/%Y %H:%M') if self.create_date else "No disponible"
        descripcion = self.description or "Sin descripción"
        instrucciones_html = self.note or "No especificadas"
        instrucciones = self._convertir_html_a_markdown(instrucciones_html)
        fecha_notificacion = datetime.now().strftime('%d/%m/%Y %H:%M')

        mensaje = (
            f"🛠 NUEVA OT CREADA # {self.code}\n"
            f"─────────────V3───────────\n"
            f"📅 *Fecha Notificación:* {fecha_notificacion}\n"
            f"📝 *Resumen:* {resumen_ot}\n"
            f"👷 *Técnico:* {tecnico}\n"
            f"🏢 *Hotel:* {hotel}\n"
            f"🏠 *Estancia:* {estancia}\n"
            f"👥 *Equipo de Mantenimiento:* {equipo_mantenimiento}\n"
            f"📅 *Fecha Creación:* {fecha_creacion}\n"
            f"📄 *Descripción:* {descripcion}\n"
            f"📌 *Instrucciones:*\n{instrucciones}\n"
            f"🔗 Abrir OT: {enlace_ot}\n"
            "───────────────────────────"
        )
        _wa_send_text(mensaje)

        # Adjuntos (solo imágenes)
        adjuntos = self.env['ir.attachment'].search([
            ('res_model', '=', 'maintenance.request'),
            ('res_id', '=', self.id),
            ('mimetype', 'like', 'image%')
        ])
        for adj in adjuntos:
            if adj.datas:
                _wa_send_image_bytes(adj.name, adj.datas)

    # ------------------------ Hooks create/write de Odoo -----------------------
    @api.model
    def create(self, vals):
        record = super().create(vals)
        record.enviar_alerta_ot(tipo="nueva")
        return record

    def write(self, vals):
        estado_anterior = self.stage_id.name if 'stage_id' in vals else None
        res = super().write(vals)
        estado_nuevo = self.stage_id.name if 'stage_id' in vals else None
        if estado_anterior and estado_nuevo and estado_anterior != estado_nuevo:
            self.enviar_alerta_ot(tipo="estado", estado_anterior=estado_anterior, estado_nuevo=estado_nuevo)
        return res
