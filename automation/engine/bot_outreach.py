import time
import random
import google.generativeai as genai
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from django.conf import settings

# Importamos la Clase Madre y el Modelo
from .engine_base import BotEngine
from automation.models import Lead, IGAccount

class OutreachBot(BotEngine):
    """
    Motor de Outreach: Envía DMs personalizados usando Gemini.
    Basado en la lógica funcional 'bot_outreach_escritorio.py'.
    """
    
    def __init__(self, account_data, proxy_data=None):
        # 1. Configuración de Gemini (Idealmente mover API KEY a settings.py)
        # Nota: Usamos la KEY que estaba en tu script funcional
        genai.configure(api_key="AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g") 
        self.model = genai.GenerativeModel('gemini-2.5-flash')
        
        # 2. Inicializar Motor Base (Selenium + Proxy)
        # Nota: BotEngine ya maneja el login y cookies internamente
        super().__init__(account_data, proxy_data)

    def _get_real_name_and_bio(self, fallback_name):
        """
        Extrae el Nombre Real (Display Name) y la Bio usando Meta Tags.
        Lógica portada de bot_outreach_escritorio.py
        """
        real_name = fallback_name
        bio_text = "Emprendedor"

        try:
            # 1. INTENTO DE NOMBRE REAL VIA META TAG (El más seguro)
            # Formato usual: "Nombre Real (@usuario) • Instagram..."
            meta_title = self.driver.find_element(By.XPATH, "//meta[@property='og:title']").get_attribute("content")
            
            if "(" in meta_title:
                # Cortamos antes del parentesis del usuario
                extracted_name = meta_title.split('(')[0].strip()
                # Si el nombre extraido no esta vacio y no es generico, lo usamos
                if extracted_name and "Instagram" not in extracted_name:
                    real_name = extracted_name
        except: 
            pass

        try:
            # 2. EXTRAER BIO
            bio_text = self.driver.find_element(By.XPATH, "//meta[@property='og:description']").get_attribute("content")
        except: 
            pass

        return real_name, bio_text

    def _generate_ai_message(self, real_name, bio_text):
        """
        Prompt optimizado para Tier A - BBI Style (No Emojis / No Fillers)
        Lógica portada EXACTA de bot_outreach_escritorio.py
        """
        prompt = f"""
        Objetivo: Mensaje de transición/profundización en Instagram DM.
        Prospecto (Nombre Real): {real_name}.
        Bio: "{bio_text}".
        
        INSTRUCCIONES DE ESTILO (BBI Standard):
        1. Usa estrictamente el PRIMER NOMBRE (ej: si es "Juan Perez", usa "Juan").
        2. Tono masculino, profesional y premium.
        3. Elimina "relleno", exageraciones y preguntas suaves.
        4. Estructura: [Nombre] you have [Elogio Específico], [Observación de potencial/dolor suave] | [Invitación a profundizar]?
        5. Formato: Generar exactamente DOS PARTES separadas por el símbolo "|".

        REGLAS ESTRICTAS:
        - IDIOMA: Inglés (English).
        - SIN EMOJIS (No emojis at all).
        - SIN SALUDOS GENÉRICOS (No "Hi", "Hello", "Hey").
        - El mensaje debe invitar a seguir la charla técnica/estratégica, no a "iniciar" una conversación privada.

        EJEMPLOS DE REFERENCIA:
        - "{real_name} you have a remarkably polished aesthetic, but the exposure doesn't fully reflect that standard | if you're open, I can share how the method applies to your profile?"
        - "{real_name} you have extremely intentional content, though visibility seems modest compared to your execution | would you be open to hearing how we align visibility with quality?"
        """
        try:
            response = self.model.generate_content(prompt)
            # Limpieza de posibles caracteres extraños
            return response.text.strip().replace('"', '')
        except Exception as e:
            print(f"Error en Gemini: {e}")
            # Fallback seguro si falla la IA
            return f"{real_name} impressive profile structure | open to discuss a strategy?"

    def _clean_message_part(self, text):
        text = text.strip()
        if text.endswith(','): text = text[:-1]
        if text: text = text[0].upper() + text[1:]
        return text

    def send_dm_to_lead(self, lead_id):
        """
        Ejecuta la secuencia de envío.
        """
        try:
            # 1. Recuperar Lead de DB
            lead = Lead.objects.get(id=lead_id)
            target_url = f"https://www.instagram.com/{lead.ig_username}/"
            
            print(f"--- Visitando Lead: {lead.ig_username} ---")
            self.driver.get(target_url)
            time.sleep(random.uniform(5, 7))
            self.dismiss_popups()

            # 2. Análisis de Perfil
            real_name, bio = self._get_real_name_and_bio(lead.ig_username)
            print(f"   Identificado: {real_name} (Bio: {bio[:30]}...)")

            # 3. Generación de Mensaje
            full_msg = self._generate_ai_message(real_name, bio)
            raw_parts = full_msg.split('|')
            mensajes_a_enviar = [self._clean_message_part(p) for p in raw_parts if p.strip()]
            
            print(f"   Gemini Generated: {mensajes_a_enviar}")

            # 4. Entrar al Chat (Estrategia Dual: Directo + Tres Puntos)
            wait = WebDriverWait(self.driver, 8)
            entrado_al_chat = False
            
            # --- ESTRATEGIA A: BOTÓN VISIBLE (Inglés + Español) ---
            posibles_botones = [
                "//div[text()='Message']", "//div[text()='Mensaje']", "//div[text()='Enviar mensaje']", 
                "//button[contains(., 'Message')]", "//button[contains(., 'Mensaje')]"
            ]
            
            boton_directo = None
            for xpath in posibles_botones:
                try:
                    elementos = self.driver.find_elements(By.XPATH, xpath)
                    for el in elementos:
                        if el.is_displayed():
                            boton_directo = el
                            break
                    if boton_directo: break
                except: pass
            
            if boton_directo:
                try:
                    boton_directo.click()
                    entrado_al_chat = True
                except:
                    self.driver.execute_script("arguments[0].click();", boton_directo)
                    entrado_al_chat = True
            
            # --- ESTRATEGIA B: TRES PUNTOS (Fallback) ---
            if not entrado_al_chat:
                print("   Botón directo no encontrado, intentando menú de opciones...")
                try:
                    xpath_dots = "//*[local-name()='svg' and (@aria-label='Options' or @aria-label='Opciones')]/ancestor::div[@role='button']"
                    btn_dots = wait.until(EC.element_to_be_clickable((By.XPATH, xpath_dots)))
                    self.driver.execute_script("arguments[0].click();", btn_dots)
                    time.sleep(1.5)
                    
                    # Buscar opción de mensaje en el menú desplegable
                    menu_xpath = "//div[@role='dialog']//div[contains(text(), 'Message') or contains(text(), 'Mensaje') or contains(text(), 'Enviar')]"
                    btn_menu = self.driver.find_element(By.XPATH, menu_xpath)
                    btn_menu.click()
                    entrado_al_chat = True
                except Exception as e:
                    print(f"   Fallo estrategia Tres Puntos: {e}")

            if not entrado_al_chat:
                print("   [ERROR] No se pudo abrir el chat.")
                return False

            # 5. Escribir Mensaje
            time.sleep(random.uniform(4, 6))
            self.dismiss_popups() # A veces sale popup de notificaciones al entrar al chat

            print("   Buscando caja de texto...")
            xpath_box = "//div[@contenteditable='true'] | //div[@role='textbox']"
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_box)))
            
            try: box.click()
            except: self.driver.execute_script("arguments[0].click();", box)
            time.sleep(1)

            # Bucle de envío de partes
            for i, parte in enumerate(mensajes_a_enviar):
                print(f"   Escribiendo parte {i+1}...")
                self.human_typing(box, parte) # Usamos el método de BotEngine
                time.sleep(0.5)
                box.send_keys(Keys.ENTER)
                
                # Pausa natural entre mensajes si hay más de uno
                if i < len(mensajes_a_enviar) - 1:
                    tiempo_pensar = random.uniform(2.5, 4.5)
                    time.sleep(tiempo_pensar)
            
            # 6. Actualizar DB
            lead.status = 'contacted'
            lead.save()
            print(f"   [EXITO] DM enviado a {lead.ig_username}")
            return True

        except Exception as e:
            print(f"   [ERROR FATAL] Fallo enviando DM: {e}")
            return False