import time
import random
import google.generativeai as genai
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

# Importamos la Clase Madre
from .engine_base import BotEngine

class CommentBot(BotEngine):
    """
    Motor de Interacción: Comenta, Da Like y Guarda posts.
    Optimizado con datos reales del Diagnóstico (Labels confirmados).
    """
    
    def __init__(self, account_data, proxy_data=None):
        super().__init__(account_data, proxy_data)
        
        # API Key de Gemini
        genai.configure(api_key="AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g") 
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    # ==============================================================================
    # 1. LÓGICA DE LECTURA
    # ==============================================================================
    def _get_post_context(self):
        context = {"caption": "", "image_desc": ""}
        try:
            # 1. Meta Tag og:description
            try:
                meta_desc = self.driver.find_element(By.XPATH, "//meta[@property='og:description'] | //meta[@name='description']")
                raw_content = meta_desc.get_attribute("content")
                if ":" in raw_content:
                    clean_caption = raw_content.split(":", 1)[1].strip()
                    clean_caption = clean_caption.replace('"', '')
                    context["caption"] = clean_caption
                else:
                    context["caption"] = raw_content
            except: pass

            # 2. Alt Text (Respaldo)
            try:
                img_elem = self.driver.find_element(By.XPATH, "//img[@alt and string-length(@alt)>5]")
                alt = img_elem.get_attribute("alt")
                if alt: context["image_desc"] = alt
            except: pass

        except Exception as e:
            print(f"[Error Contexto] {e}")
        return context

    def _generate_ai_comment(self, post_context):
        text_angles = [
            "FOCUS: Agree strongly with the main point.",
            "FOCUS: Pick a specific keyword from the caption.",
            "FOCUS: Compliment the clarity of the explanation.",
            "FOCUS: Minimalist agreement (3-5 words)."
        ]
        selected_angle = random.choice(text_angles)
        
        caption = post_context.get('caption', '')
        if not caption: caption = "Focus on visual aesthetics."

        prompt = f"""
        ROLE: Expert Social Media User.
        TASK: Write a comment for an Instagram post.
        
        POST CONTEXT:
        - Caption: "{caption}"
        - Visual: "{post_context.get('image_desc')}"
        
        INSTRUCTION:
        1. Read the Caption carefully.
        2. Write a short, natural comment.
        3. Angle: {selected_angle}
        
        CONSTRAINTS:
        1. Language: ENGLISH ONLY.
        2. NO EMOJIS.
        3. Keep it under 10 words.
        4. No generic words like 'Great', 'Nice'.
        """
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip().replace('"', '').replace("Comment:", "")
            return text
        except:
            return "This is a really solid perspective."

    # ==============================================================================
    # 2. HERRAMIENTAS DE INTERACCIÓN (AJUSTADAS AL DIAGNÓSTICO)
    # ==============================================================================

    def _click_icon_global(self, target_labels, avoid_labels=None):
        """
        Busca botones GLOBALMENTE (//*).
        target_labels: Lista de nombres para buscar (ej: 'Like', 'Me gusta')
        avoid_labels: Lista de nombres que indican que YA se hizo (ej: 'Deshacer me gusta')
        """
        # 1. Verificar si ya está hecho (Para no quitar likes o guardados)
        if avoid_labels:
            conditions_avoid = " or ".join([f"@aria-label='{label}'" for label in avoid_labels])
            xpath_avoid = f"//*[local-name()='svg' and ({conditions_avoid})]"
            try:
                if self.driver.find_elements(By.XPATH, xpath_avoid):
                    return "ALREADY_DONE"
            except: pass

        # 2. Intentar clic en el objetivo
        conditions = " or ".join([f"@aria-label='{label}'" for label in target_labels])
        # NOTA: Tu diagnóstico mostró que el Label está en el SVG.
        # Buscamos el SVG y subimos a su padre clickeable.
        xpath = f"//*[local-name()='svg' and ({conditions})]/.."
        
        try:
            btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            self.driver.execute_script("arguments[0].click();", btn)
            time.sleep(random.uniform(1, 2))
            return "CLICKED"
        except TimeoutException:
            return "NOT_FOUND"
        except Exception as e:
            print(f"   [Error Click] {e}")
            return "ERROR"

    def like_post(self):
        print("   -> Intentando dar Like...")
        # COMBINACIÓN: Etiquetas confirmadas en tu PC + Etiquetas estándar en Inglés
        targets = ["Me gusta", "Like"]
        avoids = ["Deshacer me gusta", "Ya no me gusta", "Unlike"]
        
        result = self._click_icon_global(targets, avoids)
        
        if result == "CLICKED":
            print("   [LIKE] Exitoso.")
            return True
        elif result == "ALREADY_DONE":
            print("   [LIKE] Ya estaba dado (Saltado).")
            return True
        else:
            print("   [LIKE] No se encontró el botón.")
            return False

    def save_post(self):
        print("   -> Intentando Guardar...")
        # COMBINACIÓN: Etiquetas confirmadas en tu PC + Etiquetas estándar en Inglés
        targets = ["Guardar", "Save"]
        avoids = ["Eliminar", "Eliminar de guardado", "Remove", "Unsave"]
        
        result = self._click_icon_global(targets, avoids)
        
        if result == "CLICKED":
            print("   [SAVE] Exitoso.")
            return True
        elif result == "ALREADY_DONE":
            print("   [SAVE] Ya estaba guardado (Saltado).")
            return True
        else:
            print("   [SAVE] No se encontró el botón.")
            return False

    def comment_post(self, context):
        print("   -> Generando Comentario IA...")
        comment_text = self._generate_ai_comment(context)
        print(f"   [AI] Texto: {comment_text}")
        
        try:
            # Selector de la caja de texto (Confirmado suele ser textarea)
            xpath_area = "//textarea[@aria-label='Add a comment…'] | //textarea[@aria-label='Agrega un comentario...']"
            wait = WebDriverWait(self.driver, 10)
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            
            self.driver.execute_script("arguments[0].click();", box)
            time.sleep(1)
            
            self.human_typing(box, comment_text)
            time.sleep(random.uniform(0.5, 1.5))
            
            box.send_keys(Keys.ENTER)
            print("   [COMENTARIO] Enviado.")
            return True
        except Exception as e:
            print(f"   [ERROR COMENTARIO] {e}")
            return False

    # ==============================================================================
    # 3. EJECUCIÓN PRINCIPAL
    # ==============================================================================
    def execute_interaction(self, post_url, do_like=True, do_save=False, do_comment=True):
        print(f"--- Interactuando con: {post_url} ---")
        try:
            self.driver.get(post_url)
            time.sleep(random.uniform(4, 6))
            self.dismiss_popups()

            context = self._get_post_context()
            print(f"   [CONTEXTO] Caption: {context['caption'][:40]}...")

            if do_like:
                self.like_post()
                time.sleep(random.uniform(1, 2))

            if do_save:
                self.save_post()
                time.sleep(random.uniform(1, 2))

            if do_comment:
                self.comment_post(context)
                time.sleep(random.uniform(3, 5))

            return True

        except Exception as e:
            print(f"Error interacción: {e}")
            return False