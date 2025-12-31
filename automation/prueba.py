import os
import sys
import django

# --- CONFIGURACIÓN DE DJANGO ---
# Esto hace que el script entienda dónde está tu proyecto
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_core.settings')
django.setup()

# --- IMPORTACIONES ---
from automation.models import Agency, IGAccount, Lead
from automation.engine.bot_scraper import ScraperBot

def run_test():
    print("--- INICIANDO PRUEBA DE FUEGO ---")

    # 1. Crear Agencia
    agency, _ = Agency.objects.get_or_create(name="Agencia Test")

    # 2. Configurar Cuenta (DATOS REALES REQUERIDOS)
    # ---------------------------------------------------------
    MI_USUARIO = "asdassda846" 
    MI_SESSION_ID = "78997034247%3AzV40CX7VrDeG1a%3A7%3AAYhxm6thd-XWkH69_m1y9aTuPlqqo6TTvg7jbSaE9Q" 
    # ---------------------------------------------------------

    if MI_USUARIO == "TU_USUARIO_REAL_AQUI":
        print("[ERROR] Debes editar el archivo prueba.py y poner tu Usuario y SessionID reales en las líneas 23 y 24.")
        return

    print(f"Configurando cuenta: {MI_USUARIO}...")
    
    # Guardamos o actualizamos la cuenta en la DB
    account, created = IGAccount.objects.get_or_create(
        username=MI_USUARIO,
        defaults={
            'agency': agency,
            'session_id': MI_SESSION_ID,
            'password_encrypted': b'dummy', # No se usa en esta prueba
            'config': {}
        }
    )
    
    # Si ya existía, actualizamos la cookie por si acaso
    if not created:
        account.session_id = MI_SESSION_ID
        account.save()

    # 3. Iniciar el Bot
    # headless=False para ver el navegador
    print(">>> Instanciando Bot...")
    bot = ScraperBot(account_data=account, proxy_data=None, headless=False)
    
    try:
        print(">>> 1. Abriendo Chrome...")
        bot.start_driver()
        
        print(">>> 2. Verificando Login...")
        bot.login()
        
        print(">>> 3. Scrapeando perfil de prueba ('noahfleming')...")
        bot.run_scraping_task(target_profile="noahfleming", max_leads=2)
        
        # 4. Verificar Resultados
        total = Lead.objects.count()
        print(f"\n[EXITO] Total de Leads en Base de Datos: {total}")
        
        last = Lead.objects.last()
        if last:
            print(f"Último lead capturado: {last.ig_username}")
            print(f"Datos: {last.data}")

    except Exception as e:
        print(f"\n[ERROR CRITICO] {e}")
        import traceback
        traceback.print_exc()
        
    finally:
        print(">>> Cerrando navegador...")
        if bot: bot.close()

if __name__ == "__main__":
    run_test()