import requests
import urllib3
from django.core.management.base import BaseCommand

from automation.engine.bot_fast_interaction import build_proxy_url, _get_default_proxy_data
from automation.models import IGAccount

TEST_URL = "https://geo.brdtest.com/welcome.txt?product=resi&method=native"


class Command(BaseCommand):
    help = "Prueba el proxy Bright Data de una IGAccount usando requests."

    def add_arguments(self, parser):
        parser.add_argument("--username", type=str, required=True, help="Username de IGAccount")

    def handle(self, *args, **options):
        # Evita spam de warnings cuando usamos verify=False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        username = options["username"]
        account = IGAccount.objects.filter(username=username).first()
        if not account:
            self.stderr.write(self.style.ERROR(f"IGAccount no encontrada: {username}"))
            return

        account_proxy = {
            "host": (getattr(account, "proxy_host", "") or "").strip(),
            "port": getattr(account, "proxy_port", None),
            "user": (getattr(account, "proxy_user", "") or "").strip(),
            "password": (getattr(account, "proxy_password", "") or "").strip(),
        }
        if not account_proxy["host"] or not account_proxy["port"]:
            account_proxy = None

        default_proxy = _get_default_proxy_data()
        proxy_data = account_proxy or default_proxy

        proxy_url = build_proxy_url(proxy_data)
        if not proxy_url:
            self.stdout.write(self.style.WARNING(
                f"{username} no tiene proxy configurado y no hay proxy global activo."
            ))
            return

        self.stdout.write(f"Probando proxy para {username}: {proxy_url}")
        proxies = {"http": proxy_url, "https": proxy_url}

        try:
            resp = requests.get(
                TEST_URL,
                proxies=proxies,
                timeout=20,
                verify=False,  # FIX: Bright Data test endpoint puede fallar verificación SSL
            )
            preview = (resp.text or "")[:200].replace("\n", "\\n")
            self.stdout.write(self.style.SUCCESS(f"Status code: {resp.status_code}"))
            self.stdout.write(f"Body (200 chars): {preview}")
        except requests.RequestException as exc:
            self.stderr.write(self.style.ERROR(f"Fallo al probar proxy: {exc}"))
