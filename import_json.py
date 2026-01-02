import os
import sys
import json
import django

# 1. Configurar entorno Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_core.settings')
django.setup()

from automation.models import IGAccount, Agency

def import_from_json():
    filename = 'cuentas.json'
    if not os.path.exists(filename):
        print(f"No encuentro el archivo '{filename}'")
        return

    # Obtener o crear la agencia
    agency, _ = Agency.objects.get_or_create(name="Imported Scrapers Pool")
    print(f"Agencia destino: {agency.name}")

    with open(filename, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count_new = 0
    count_updated = 0

    print(f"Procesando {len(data)} cuentas...")

    for item in data:
        username = item.get('user')
        password = item.get('pass')
        session_id = item.get('sessionid')

        if not username:
            continue

        # Crear o Recuperar cuenta
        account, created = IGAccount.objects.get_or_create(
            username=username,
            defaults={
                'agency': agency,
                'status': 'active', # Forzamos activo
                'config': {'imported': True}
            }
        )

        # Actualizamos siempre para asegurar que tengan la última password/session
        account.set_password(password) # Encripta la password
        account.session_id = session_id
        account.agency = agency
        account.status = 'active' # Reactivamos si estaba 'expired'
        account.save()

        if created:
            print(f"[NUEVA] {username} agregada.")
            count_new += 1
        else:
            print(f"[ACTUALIZADA] {username} lista.")
            count_updated += 1

    print("\n" + "="*40)
    print(f"IMPORTACIÓN TERMINADA")
    print(f"Nuevas: {count_new}")
    print(f"Actualizadas: {count_updated}")
    print(f"Total en Pool: {IGAccount.objects.filter(agency=agency).count()}")
    print("="*40)

if __name__ == "__main__":
    import_from_json()