import json
import os
from django.core.management.base import BaseCommand
from automation.models import IGAccount, Agency

class Command(BaseCommand):
    help = "Importa cuentas desde JSON guardando COOKIES COMPLETAS"

    def add_arguments(self, parser):
        parser.add_argument('--file', type=str, default='cuentas1.json', help='Ruta al archivo JSON')

    def handle(self, *args, **options):
        file_path = options['file']

        if not os.path.exists(file_path):
            self.stdout.write(self.style.ERROR(f"No se encontró: {file_path}"))
            return

        agency, _ = Agency.objects.get_or_create(name="Imported JSON Pool")

        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        self.stdout.write(f"Procesando {len(data)} cuentas con cookies completas...")
        
        count = 0
        for entry in data:
            username = entry.get('user')
            raw_cookies = entry.get('cookies', {}) # Obtenemos el diccionario completo
            
            # Extraemos sessionid para el campo legacy/rápido
            session_id = raw_cookies.get('sessionid')

            if not username or not session_id:
                continue

            # Parseo de Proxy (si aplica)
            proxy_str = entry.get('proxy', "")
            p_host, p_port, p_user, p_pass = "", None, "", ""
            if proxy_str:
                try:
                    if "@" in proxy_str:
                        creds, addr = proxy_str.split("@")
                        p_user, p_pass = creds.split(":")
                        p_host, p_port = addr.split(":")
                    else:
                        parts = proxy_str.split(":")
                        if len(parts) >= 2:
                            p_host, p_port = parts[0], parts[1]
                except: pass

            # Guardar en DB incluyendo el campo 'cookies'
            IGAccount.objects.update_or_create(
                username=username,
                defaults={
                    "agency": agency,
                    "session_id": session_id,
                    "cookies": raw_cookies,  # <--- AQUÍ GUARDAMOS TODO EL JSON
                    "status": "ACTIVE",
                    "proxy_host": p_host,
                    "proxy_port": int(p_port) if p_port else None,
                    "proxy_user": p_user,
                    "proxy_password": p_pass
                }
            )
            count += 1

        self.stdout.write(self.style.SUCCESS(f"✅ Se importaron/actualizaron {count} cuentas con cookies full."))