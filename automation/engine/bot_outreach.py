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
from automation.models import Lead

class OutreachBot(BotEngine):
    """
    Motor de Outreach: Envía DMs personalizados usando Gemini.
    Hereda la navegación segura de BotEngine.
    """
    
    def __init__(self, account_data, proxy_data=None, headless=False):
        # Inicializa la clase madre
        super().__init__(account_data, proxy_data, headless)
        
        # Configura Gemini (Usar variable de entorno en producción)
        genai.configure(api_key="AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g") 
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def _get_real_name_and_bio(self, fallback_name):
        """Extrae el nombre real del perfil para no hablar como robot"""
        real_name = fallback_name
        bio_text = "Emprendedor"

        try:
            # Estrategia Meta Tag (Igual que en tu script original)
            meta_title = self.driver.find_element(By.XPATH, "//meta[@property='og:title']").get_attribute("content")
            if "(" in meta_title:
                extracted = meta_title.split('(')[0].strip()
                if extracted and "Instagram" not in extracted:
                    real_name = extracted
        except: pass

        try:
            bio_text = self.driver.find_element(By.XPATH, "//meta[@property='og:description']").get_attribute("content")
        except: pass

        return real_name, bio_text

    def _generate_ai_message(self, real_name, bio_text):
        """Tu prompt BBI Standard original"""
        prompt = f"""
        Objetivo: Mensaje de transición/profundización en Instagram DM.
        Prospecto: {real_name}. Bio: "{bio_text}".
        
        INSTRUCCIONES DE ESTILO (BBI Standard):
        1. Usa el PRIMER NOMBRE.
        2. Tono masculino, profesional y premium.
        3. Sin relleno, sin preguntas suaves.
        4. Estructura: [Nombre] you have [Elogio], [Observación] | [Invitación]?
        
        REGLAS:
        - IDIOMA: Inglés.
        - SIN EMOJIS.
        - Formato: Dos partes separadas por "|".
        """
        try:
            response = self.model.generate_content(prompt)
            return response.text.strip().replace('"', '')
        except:
            return f"{real_name} impressive profile | open to discuss strategy?"

    def send_dm_to_lead(self, lead_id):
        """
        Función Principal: Busca el lead en DB, va al perfil y envía el DM.
        """
        try:
            # 1. Obtener lead de la Base de Datos
            lead = Lead.objects.get(id=lead_id)
            target_url = f"https://www.instagram.com/{lead.ig_username}/"
            
            print(f"--- Visitando Lead: {lead.ig_username} ---")
            self.driver.get(target_url)
            time.sleep(random.uniform(4, 6))
            self.dismiss_popups()

            # 2. Extraer datos y Generar Mensaje
            real_name, bio = self._get_real_name_and_bio(lead.ig_username)
            full_msg = self._generate_ai_message(real_name, bio)
            parts = [p.strip() for p in full_msg.split('|') if p.strip()]

            print(f"Mensaje Generado para {real_name}: {parts}")

            # 3. Entrar al Chat (Estrategia Barrido + Tres Puntos)
            entrado = False
            
            # Intento A: Botón Directo
            try:
                btn = self.driver.find_element(By.XPATH, "//div[text()='Message' or text()='Enviar mensaje']")
                btn.click()
                entrado = True
            except:
                # Intento B: Tres Puntos
                try:
                    dots = self.driver.find_element(By.XPATH, "//*[local-name()='svg' and @aria-label='Options']/ancestor::div[@role='button']")
                    dots.click()
                    time.sleep(1)
                    menu_btn = self.driver.find_element(By.XPATH, "//div[contains(text(), 'Message') or contains(text(), 'Enviar')]")
                    menu_btn.click()
                    entrado = True
                except: pass

            if not entrado:
                print("No se pudo entrar al chat.")
                return False

            # 4. Escribir en la caja
            time.sleep(random.uniform(3, 5))
            box = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//div[@contenteditable='true'] | //div[@role='textbox']"))
            )
            box.click()

            for part in parts:
                self.human_typing(box, part)
                time.sleep(0.5)
                box.send_keys(Keys.ENTER)
                time.sleep(random.uniform(2, 4)) # Pausa entre mensajes
            
            # 5. Actualizar Estado en Base de Datos
            lead.status = 'contacted'
            lead.save()
            print(f"Exito: DM enviado a {lead.ig_username}")
            return True

        except Exception as e:
            print(f"Error enviando DM: {e}")
            return False