import os
import sys
import re
import json
import django

# 1. Configuración de Entorno Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'saas_core.settings')
django.setup()

from automation.models import IGAccount, Agency

def repair_json_string(s):
    """
    Limpieza agresiva para corregir JSONs mal formados de cookies exportadas.
    """
    s = s.strip()
    
    # 1. Recuperar corchete inicial si se perdió en el split
    if s.startswith('{') and s.endswith(']'):
        s = '[' + s
        
    # 2. LIMPIEZA DE ESCAPES INVÁLIDOS (El orden importa)
    
    # A. Eliminar doble escape octal (\\054 -> ,)
    # Esto previene que se convierta en \,
    s = s.replace('\\\\054', ',')
    
    # B. Eliminar escape octal simple (\054 -> ,)
    s = s.replace('\\054', ',')
    
    # C. Eliminar escape de coma inválido (\, -> ,) <--- ESTO ARREGLA TU ERROR ACTUAL
    # JSON no permite escapar comas, pero algunos exportadores lo hacen.
    s = s.replace('\\,', ',')
    
    # D. Eliminar escape de barra invertida (\/ -> /)
    s = s.replace('\\/', '/')
    
    # E. Eliminar comillas simples escapadas (\' -> ')
    # Python lo acepta, JSON no.
    s = s.replace("\\'", "'")

    return s

def parse_and_import():
    # Intenta leer ambos nombres de archivo posibles
    filename = 'all.txt'
    if not os.path.exists(filename):
        filename = '5 all.txt'
    
    if not os.path.exists(filename):
        print(f" Error: No encuentro 'all.txt' ni '5 all.txt'")
        return

    print(f" Procesando archivo: {filename}")
    agency, _ = Agency.objects.get_or_create(name="Imported Scrapers Pool")

    count = 0
    with open(filename, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line: continue

            try:
                if '![' not in line: continue
                parts = line.split('![')
                credentials_part = parts[0]
                json_part = parts[1]

                # Separar Usuario y Contraseña
                match = re.match(r'^([a-z]+[0-9]+)(.+)$', credentials_part)
                if match:
                    username = match.group(1)
                    password = match.group(2)
                else:
                    username = credentials_part[:12]
                    password = credentials_part[12:]

                # --- LIMPIEZA ---
                clean_json = repair_json_string(json_part)

                try:
                    cookies_list = json.loads(clean_json)
                except json.JSONDecodeError as e:
                    # Si falla, mostramos log pero seguimos con la siguiente
                    print(f"️ JSON irrecuperable para {username}: {e}")
                    continue

                # Extraer SessionID
                session_id = None
                if isinstance(cookies_list, list):
                    for cookie in cookies_list:
                        if cookie.get('name') == 'sessionid':
                            session_id = cookie.get('value')
                            break
                
                if not session_id:
                    print(f"️ Sin sessionid: {username}")
                    continue

                # Guardar
                account, created = IGAccount.objects.get_or_create(
                    username=username,
                    defaults={
                        'agency': agency,
                        'status': 'active',
                        'config': {'imported': True}
                    }
                )
                account.set_password(password)
                account.session_id = session_id
                account.save()

                state = "Nuevo" if created else "Actualizado"
                print(f" [{state}] {username} | OK")
                count += 1

            except Exception as e:
                print(f" Error línea: {e}")

    print(f"\n Importación finalizada. Total cuentas: {count}")

if __name__ == "__main__":
    parse_and_import()