# -*- coding: utf-8 -*-
"""
CIERRE DE OT - WHATSAPP (Estado: Reparado)
-----------------------------------------------------------
- Fecha de implementación: 27/08/2025
- Versión: 1.2
- Autor: Andrés Sánchez Serrano

📌 Descripción:
Detecta el cambio de estado a "Reparado" y envía notificación detallada a WhatsApp
(incluye técnico, hotel, estancia, horas, fecha de cierre y enlaces a adjuntos).

🔧 Mejoras implementadas:
1. Migración completa a WhatsApp (mudslide) sin Telegram.
2. Capa de envío propia (textos e imágenes) con timeout configurable.
3. Mensaje “CIERRE DE OT” con formato V3.
4. Código autónomo: no depende de helpers externos.
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

from odoo import models

_logger = logging.getLogger(__name__)


# ===================== Utilidades internas (WA + secrets) =====================
def _module_root():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

def _load_secrets_local():
    import yaml
    primary = os.path.join(_module_root(), "secrets.yaml")
    fallback = os.path.join(_module_root(), "secrets.yaml.example")
    path = primary if os.path.exists(primary) else fallback
    try:
        with open(path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        _logger.error(f"Error al cargar secrets: {e}")
        return {}

def _wa_config():
    s = _load_secrets_local()
    return {
        "to": s.get("wa_to", ""),
        "text_cmd": s.get("wa_text_cmd", "npx mudslide@latest send {to} {text}"),
        "image_cmd": s.get("wa_image_cmd", "npx mudslide@latest send {to} --image {file}"),
        "timeout": int(s.get("wa_timeout_sec", 120)),
    }

def _wa_send_text(text):
    cfg = _wa_config()
    if not cfg["to"]:
        _logger.error("WhatsApp: 'wa_to' vacío en secrets.yaml(.example).")
        return
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

    def _convertir_html_a_markdown(self, html_text):
        html_text = re.sub(r'<ul[^>]*>', '', html_text or '')
        html_text = re.sub(r'</ul>', '', html_text)
        html_text = re.sub(r'<li[^>]*>(.*?)</li>', r'• \1', html_text)
        html_text = re.sub(r'<[^>]+>', '', html_text)
        return (html_text or "").strip()

    def _mensaje_cierre(self, estado_anterior, estado_nuevo):
        tecnico = getattr(self.user_id, 'name', 'Sin técnico')
        hotel = getattr(self.category_id, 'name', 'No especificado')
        estancia = getattr(self.equipment_id, 'name', 'No asignado')
        tiempo_dedicado = self.duration or 0
        fecha_cierre = self.close_date.strftime('%d/%m/%Y %H:%M') if self.close_date else "No disponible"
        descripcion = self.description or "Sin descripción"
        instrucciones_html = self.note or "No especificadas"
        instrucciones = self._convertir_html_a_markdown(instrucciones_html)
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        enlace_ot = f"{base_url}/web#id={self.id}&model=maintenance.request&view_type=form"

        mensaje = (
            f"🛠 *CIERRE DE OT # {self.code}*\n"
            f"─────────────V3───────────\n"
            f"🔄 *De:* {estado_anterior} ➡️ *A:* {estado_nuevo}\n"
            f"👷 *Técnico:* {tecnico}\n"
            f"🏢 *Hotel:* {hotel}\n"
            f"🏠 *Estancia:* {estancia}\n"
            f"⏳ *Tiempo Dedicado:* {tiempo_dedicado:.2f} horas\n"
            f"🗓 *Fecha Cierre:* {fecha_cierre}\n"
            f"📄 *Descripción:* {descripcion}\n"
            f"📌 *Instrucciones:*\n{instrucciones}\n"
            f"🔗 Abrir OT: {enlace_ot}\n"
            "───────────────────────────"
        )
        return mensaje

    def write(self, vals):
        estado_anterior = self.stage_id.name if self.stage_id else "Desconocido"
        res = super().write(vals)
        estado_nuevo = self.stage_id.name if self.stage_id else "Desconocido"

        if 'stage_id' in vals and estado_anterior != estado_nuevo and estado_nuevo and estado_nuevo.lower() == "reparado":
            _logger.info(f"📢 Enviando notificación WA: OT {self.code} pasó de '{estado_anterior}' a '{estado_nuevo}'.")
            _wa_send_text(self._mensaje_cierre(estado_anterior, estado_nuevo))

            # Enviar adjuntos (texto con enlaces) + imágenes
            base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
            adjuntos = self.env['ir.attachment'].search([('res_model', '=', 'maintenance.request'),
                                                         ('res_id', '=', self.id)])
            enlaces = []
            for adj in adjuntos:
                url = f"{base_url}/web/content/{adj.id}"
                if str(adj.mimetype or "").startswith('image/'):
                    enlaces.append(f"🖼 {adj.name}: {url}")
                    if adj.datas:
                        _wa_send_image_bytes(adj.name, adj.datas)
                else:
                    enlaces.append(f"📎 {adj.name}: {url}")

            if enlaces:
                _wa_send_text("Adjuntos:\n" + "\n".join(enlaces))

        return res
