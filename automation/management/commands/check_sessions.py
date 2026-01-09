import time
from django.core.management.base import BaseCommand
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, LoginRequired, ChallengeRequired, 
    FeedbackRequired, PleaseWaitFewMinutes
)
from automation.models import IGAccount

class Command(BaseCommand):
    help = "Verifica la integridad de las sessionid y marca las expiradas."

    def add_arguments(self, parser):
        parser.add_argument(
            '--batch-size', 
            type=int, 
            default=110, 
            help='Número de cuentas a verificar por ejecución'
        )

    def handle(self, *args, **options):
        batch_size = options['batch_size']
        
        # 1. Filtramos solo las que están teóricamente "ACTIVAS" para no gastar recursos en las ya muertas
        accounts = IGAccount.objects.filter(status='ACTIVE')[:batch_size]
        
        if not accounts:
            self.stdout.write(self.style.WARNING("No hay cuentas activas para verificar."))
            return

        self.stdout.write(f"--- Iniciando verificación de {len(accounts)} cuentas ---")

        stats = {"active": 0, "expired": 0, "challenge": 0, "error": 0}

        for account in accounts:
            status = self.check_session(account)
            
            # Actualizamos la estadística
            if status == "ACTIVE":
                stats["active"] += 1
            elif status == "SESSION_EXPIRED":
                stats["expired"] += 1
            elif status == "CHALLENGE":
                stats["challenge"] += 1
            else:
                stats["error"] += 1
            
            # Pausa de seguridad para evitar saturación local/proxy
            time.sleep(2)

        self.stdout.write(self.style.SUCCESS(f"\nResumen:"))
        self.stdout.write(f" Activas: {stats['active']}")
        self.stdout.write(f" Expiradas (SESSION_EXPIRED): {stats['expired']}")
        self.stdout.write(f"️ Challenge: {stats['challenge']}")

    def check_session(self, account):
        """Intenta validar la sesión usando instagrapi"""
        client = Client()
        
        # Configuración de Proxy (Basado en tu models.py)
        if account.proxy_host and account.proxy_port:
            try:
                # Formato: http://user:pass@host:port
                proxy_url = f"http://{account.proxy_user}:{account.proxy_password}@{account.proxy_host}:{account.proxy_port}"
                client.set_proxy(proxy_url)
            except Exception as e:
                self.stdout.write(self.style.ERROR(f"[{account.username}] Error config proxy: {e}"))
                # Si falla el proxy, no podemos culpar a la sesión todavía, devolvemos error
                return "PROXY_ERROR"

        try:
            if not account.session_id:
                self.mark_as(account, "SESSION_EXPIRED")
                return "SESSION_EXPIRED"

            # Intento de Login
            client.login_by_sessionid(account.session_id)
            
            # Prueba de Fuego: Obtener info propia
            client.account_info()
            
            self.stdout.write(self.style.SUCCESS(f"[{account.username}]  OK"))
            return "ACTIVE"

        except (LoginRequired, BadPassword):
            self.stdout.write(self.style.ERROR(f"[{account.username}]  Session Expirada"))
            self.mark_as(account, "SESSION_EXPIRED")
            return "SESSION_EXPIRED"

        except (ChallengeRequired, FeedbackRequired):
            self.stdout.write(self.style.WARNING(f"[{account.username}] ️ Challenge/Limitada"))
            self.mark_as(account, "CHALLENGE")
            return "CHALLENGE"

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[{account.username}]  Error desconocido: {e}"))
            return "ERROR"

    def mark_as(self, account, new_status):
        """Helper para guardar el nuevo estado"""
        if account.status != new_status:
            account.status = new_status
            account.save(update_fields=['status'])