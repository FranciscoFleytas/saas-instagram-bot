import os
import sys
import time
import django
from instagrapi import Client
from instagrapi.exceptions import (
    BadPassword, ReloginAttemptExceeded, ChallengeRequired,
    FeedbackRequired, LoginRequired, PleaseWaitFewMinutes
)

# 1. Configuración del Entorno Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_core.settings')
django.setup()

from automation.models import IGAccount, Agency

def check_account_status(account):
    """
    Intenta realizar una acción benigna (obtener info del propio perfil)
    para verificar si la session_id sigue viva.
    """
    client = Client()
    
    # Configurar Proxy si existe (CRÍTICO para evitar bloqueos por IP)
    if account.proxy:
        proxy_url = f"http://{account.proxy.username}:{account.proxy.password}@{account.proxy.ip_address}:{account.proxy.port}"
        client.set_proxy(proxy_url)

    try:
        print(f" Verificando: {account.username}...")

        # 1. Login vía SessionID
        if not account.session_id:
            print(f"    Sin SessionID")
            return "no_session"

        client.login_by_sessionid(account.session_id)

        # 2. Prueba de Fuego: Obtener info del usuario logueado
        # Si la cuenta está baneada o la cookie venció, esto fallará.
        me = client.account_info()
        
        print(f"    ACTIVA | ID: {me.pk} | Nombre: {me.full_name}")
        return "active"

    except (ChallengeRequired, CheckpointRequired):
        print(f"   ️ CHALLENGE (Requiere verificación SMS/Email)")
        return "challenge"
    
    except (LoginRequired, BadPassword):
        print(f"    COOKIE VENCIDA (Requiere re-login con password)")
        return "expired"
    
    except FeedbackRequired:
        print(f"   ️ LIMITADA (Action Block temporal)")
        return "limited"

    except Exception as e:
        error_msg = str(e).lower()
        if "feedback_required" in error_msg:
            return "limited"
        elif "login_required" in error_msg:
            return "expired"
        elif "challenge_required" in error_msg:
            return "challenge"
        
        print(f"    ERROR DESCONOCIDO: {e}")
        return "error"

def main():
    print("--- INICIANDO DIAGNÓSTICO DE CUENTAS ---")
    
    # Obtenemos todas las cuentas de la agencia de scrapers
    try:
        agency = Agency.objects.get(name="Imported Scrapers Pool")
        accounts = IGAccount.objects.filter(agency=agency)
    except Agency.DoesNotExist:
        print("No se encontró la agencia 'Imported Scrapers Pool'. Usando todas las cuentas.")
        accounts = IGAccount.objects.all()

    stats = {
        "active": 0,
        "expired": 0,
        "challenge": 0,
        "limited": 0,
        "error": 0,
        "no_session": 0
    }

    for acc in accounts:
        status = check_account_status(acc)
        
        # Actualizar estado en Base de Datos
        if status in ['active', 'challenge', 'limited']:
            acc.status = status
            acc.save()
        elif status == 'expired':
            acc.status = 'inactive' # Marcamos como inactiva para no usarla
            acc.save()
            
        stats[status] = stats.get(status, 0) + 1
        
        # Pausa pequeña para no saturar tu IP local si no usas proxies
        time.sleep(1)

    print("\n--- REPORTE FINAL ---")
    print(f" Activas: {stats['active']}")
    print(f" Cookies Vencidas: {stats['expired']}")
    print(f"️ En Challenge: {stats['challenge']}")
    print(f"️ Limitadas: {stats['limited']}")
    print(f" Errores: {stats['error']}")

if __name__ == "__main__":
    main()