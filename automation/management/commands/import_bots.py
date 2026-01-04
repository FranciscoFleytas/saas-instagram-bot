import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from automation.models import IGAccount, Agency


SESSION_RE = re.compile(r'"name"\s*:\s*"sessionid".*?"value"\s*:\s*"([^"]+)"', re.DOTALL)
DS_USER_RE = re.compile(r'"name"\s*:\s*"ds_user_id".*?"value"\s*:\s*"([^"]+)"', re.DOTALL)


class Command(BaseCommand):
    help = "Importa IGAccounts desde un txt tipo username:pass:email:pass:[cookies_json] extrayendo sessionid."

    def add_arguments(self, parser):
        parser.add_argument("--file", type=str, required=True, help="Path al 100_decoded.txt")
        parser.add_argument("--agency-id", type=str, default=None, help="UUID de Agency (opcional)")
        parser.add_argument("--agency-name", type=str, default=None, help="Nombre Agency (opcional, crea si no existe)")
        parser.add_argument("--status", type=str, default="ACTIVE", help="Status a setear (default ACTIVE)")
        parser.add_argument("--dry-run", action="store_true", help="No escribe nada, solo muestra resumen")
        parser.add_argument("--update-existing", action="store_true", help="Actualiza session_id si el username ya existe")

    def handle(self, *args, **opts):
        file_path = Path(opts["file"]).expanduser().resolve()
        if not file_path.exists():
            self.stderr.write(self.style.ERROR(f"No existe el archivo: {file_path}"))
            return

        agency = None
        if opts["agency_id"]:
            agency = Agency.objects.filter(id=opts["agency_id"]).first()
            if not agency:
                self.stderr.write(self.style.ERROR("agency-id no encontrado."))
                return
        elif opts["agency_name"]:
            agency, _ = Agency.objects.get_or_create(
                name=opts["agency_name"],
                defaults={"plan_level": "FREE"},
            )

        status = (opts["status"] or "ACTIVE").upper()
        update_existing = bool(opts["update_existing"])
        dry_run = bool(opts["dry_run"])

        created = 0
        updated = 0
        skipped = 0
        no_session = 0

        # Leemos línea por línea. Si alguna línea viene "cortada" (como el inicio del archivo),
        # se va a skippear y listo.
        lines = file_path.read_text(encoding="utf-8", errors="ignore").splitlines()

        # Heurística: intentamos parsear solo líneas con al menos 5 partes separadas por ":" y que tengan '['
        # usando maxsplit=4 para no romper el JSON.
        with transaction.atomic():
            for idx, line in enumerate(lines, start=1):
                line = line.strip()
                if not line or "[" not in line or ":" not in line:
                    skipped += 1
                    continue

                parts = line.split(":", 4)
                if len(parts) < 5:
                    skipped += 1
                    continue

                username = parts[0].strip()
                cookies_blob = parts[4].strip()

                # Extraer sessionid desde el json/cadena
                m = SESSION_RE.search(cookies_blob)
                if not m:
                    no_session += 1
                    continue

                session_id = m.group(1).strip()
                if not session_id:
                    no_session += 1
                    continue

                # (Opcional) ds_user_id, por si te sirve para debug
                ds_user_id = None
                m2 = DS_USER_RE.search(cookies_blob)
                if m2:
                    ds_user_id = m2.group(1).strip()

                if dry_run:
                    continue

                obj = IGAccount.objects.filter(username=username).first()
                if obj:
                    if update_existing:
                        obj.session_id = session_id
                        obj.status = status
                        if agency:
                            obj.agency = agency
                        obj.save(update_fields=["session_id", "status", "agency"])
                        updated += 1
                    else:
                        skipped += 1
                    continue

                IGAccount.objects.create(
                    username=username,
                    status=status,
                    session_id=session_id,
                    agency=agency,
                )
                created += 1

            if dry_run:
                transaction.set_rollback(True)

        self.stdout.write(self.style.SUCCESS("Import finalizado."))
        self.stdout.write(f" - created: {created}")
        self.stdout.write(f" - updated: {updated}")
        self.stdout.write(f" - skipped: {skipped}")
        self.stdout.write(f" - no_sessionid: {no_session}")
        self.stdout.write(f" - agency: {agency.id if agency else 'None'}")
        self.stdout.write(f" - file: {file_path}")
