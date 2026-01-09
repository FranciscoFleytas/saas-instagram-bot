import json
import os

def procesar_cuentas():
    input_file = '100_decoded.txt'
    output_file = 'cuentas.json'
    
    nuevas_cuentas = []
    
    # 1. Leer el archivo de texto
    if not os.path.exists(input_file):
        print(f" Error: No encuentro el archivo {input_file}")
        return

    print(f" Procesando {input_file}...")
    
    with open(input_file, 'r', encoding='utf-8') as f:
        lineas = f.readlines()

    count = 0
    for linea in lineas:
        try:
            # El formato es user:pass:email:emailpass:[json]
            # Usamos split con maxsplit para no romper el json si tiene : dentro
            partes = linea.strip().split(':', 4)
            
            if len(partes) < 5:
                continue
                
            usuario = partes[0]
            password = partes[1]
            raw_cookies = partes[4] # La parte del JSON
            
            # Parsear las cookies para buscar el sessionid
            cookies = json.loads(raw_cookies)
            session_id = None
            
            for cookie in cookies:
                if cookie.get('name') == 'sessionid':
                    session_id = cookie.get('value')
                    break
            
            if usuario and password and session_id:
                nuevas_cuentas.append({
                    "user": usuario,
                    "pass": password,
                    "sessionid": session_id
                })
                count += 1
                
        except Exception as e:
            print(f"️ Error procesando una línea: {e}")
            continue

    # 2. Guardar o combinar con cuentas.json existente
    lista_final = nuevas_cuentas
    
    # Si ya tienes cuentas, las leemos para no borrarlas (opcional)
    if os.path.exists(output_file):
        try:
            with open(output_file, 'r', encoding='utf-8') as f:
                existentes = json.load(f)
                if isinstance(existentes, list):
                    # Combinar listas (evitando duplicados por usuario si quieres)
                    users_existentes = {c['user'] for c in existentes}
                    for nueva in nuevas_cuentas:
                        if nueva['user'] not in users_existentes:
                            existentes.append(nueva)
                    lista_final = existentes
        except:
            pass # Si falla leer el anterior, usamos solo las nuevas

    # Escribir el archivo final
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(lista_final, f, indent=4)

    print(f" ¡Éxito! Se han procesado {count} cuentas nuevas.")
    print(f" Archivo guardado: {output_file} (Total cuentas: {len(lista_final)})")

if __name__ == "__main__":
    procesar_cuentas()