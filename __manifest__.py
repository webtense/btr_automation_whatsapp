{
    "name": "BTR Automation WhatsApp",
    "version": "1.1.1",
    "summary": "Automatización de resúmenes y alertas de OTs vía WhatsApp (Mudslide npx)",
    "description": "Envía notificaciones de creación y cambios de estado de OTs, además de resúmenes diario y semanal, utilizando WhatsApp mediante comandos npx (mudslide).",
    "author": "Andres Sanchez",
    "website": "https://boitaullresort.com",
    "category": "Maintenance",
    "license": "LGPL-3",
    "depends": ["base", "maintenance"],
    "data": [
        "data/cron_jobs.xml",
        "security/ir.model.access.csv"
    ],
    "installable": True,
    "auto_install": False,
    "application": True,
    "assets": {
        "web.assets_backend": []
    }
}
