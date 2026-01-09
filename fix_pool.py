import os
import sys
import django

# Configurar Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_core.settings')
django.setup()

from automation.models import IGAccount, Agency

def inspect_and_reset():
    print("--- INSPECCIÓN DEL POOL DE CUENTAS ---")
    
    try:
        agency = Agency.objects.get(name="Imported Scrapers Pool")
    except Agency.DoesNotExist:
        print(" Error: No existe la agencia 'Imported Scrapers Pool'")
        return

    accounts = IGAccount.objects.filter(agency=agency)
    print(f"Total cuentas en el Pool: {accounts.count()}\n")

    print(f"{'USUARIO':<20} | {'ESTADO ACTUAL':<15} | {'SESSION ID?':<10}")
    print("-" * 55)

    active_count = 0
    for acc in accounts:
        has_session = " Sí" if acc.session_id else " No"
        print(f"{acc.username:<20} | {acc.status:<15} | {has_session}")
        
        if acc.status == 'active':
            active_count += 1

    print("-" * 55)
    print(f"️ Actualmente SOLO {active_count} cuentas están rotando (status='active').")
    
    # --- OPCIÓN DE RESET ---
    print("\n¿Quieres forzar a TODAS las cuentas a estado 'active' para que roten?")
    confirm = input("Escribe 'SI' para resetear: ")
    
    if confirm.upper() == 'SI':
        updated = accounts.update(status='active')
        print(f"\n {updated} cuentas restablecidas a 'active'.")
        print("Ahora el sistema usará todas aleatoriamente.")
    else:
        print("\nNo se hicieron cambios.")

if __name__ == "__main__":
    inspect_and_reset()