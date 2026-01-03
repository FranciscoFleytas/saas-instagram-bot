import time
import random
import re
import google.generativeai as genai
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException
from selenium.webdriver.common.action_chains import ActionChains
from django.conf import settings

# Importamos la Clase Madre
from .engine_base import BotEngine

class CommentBot(BotEngine):
    """
    Motor de Interacción V7: Optimizado con lógica de Escritorio (Fast Typing + Context Fix).
    """
    
    def __init__(self, account_data, proxy_data=None):
        super().__init__(account_data, proxy_data)
        
        # API Key de Gemini
        genai.configure(api_key=settings.GEMINI_API_KEY) 
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    # ==============================================================================
    # 1. LÓGICA DE LECTURA (Portada de script-comentarios.py)
    # ==============================================================================
    def _get_post_context(self):
        context = {"caption": "", "image_desc": ""}
        try:
            # 1. Intentar Meta Tag de Descripción (Método más fiable)
            try:
                meta_desc = self.driver.find_element(By.XPATH, "//meta[@property='og:description'] | //meta[@name='description']")
                raw_content = meta_desc.get_attribute("content")
                
                # Limpieza universal (Funciona en Español e Inglés)
                # Formato típico: "100 likes, 5 comments - Usuario: El texto del post..."
                if ":" in raw_content:
                    # Tomamos todo lo que está después del primer dos puntos
                    clean_caption = raw_content.split(":", 1)[1].strip()
                    clean_caption = clean_caption.replace('"', '') # Quitar comillas extra
                    context["caption"] = clean_caption
                else:
                    context["caption"] = raw_content
            except: pass

            # 2. Intentar Alt Text de la imagen (Respaldo visual)
            try:
                img_elem = self.driver.find_element(By.XPATH, "//article//img")
                alt = img_elem.get_attribute("alt")
                if alt: context["image_desc"] = alt
            except: pass

        except Exception as e:
            print(f"[Error Contexto] {e}")
            
        return context

    def _generate_ai_comment(self, post_context, user_persona=None, focus_selection=None, user_prompt=None):
        """
        Genera comentario fusionando reglas del sistema + instrucciones del usuario.
        """
        
        # 1. Definir Angulo (Focus)
        if focus_selection and isinstance(focus_selection, list) and len(focus_selection) > 0:
            selected_angle = random.choice(focus_selection)
        else:
            text_angles = [
                "FOCUS: Agree with the main point.",
                "FOCUS: Compliment the visual aesthetic.",
                "FOCUS: Highlight the mood.",
                "FOCUS: Minimalist agreement."
            ]
            if len(post_context.get('caption', '')) > 5:
                text_angles.append("FOCUS: Mention a keyword from the text.")
            selected_angle = random.choice(text_angles)

        # 2. Definir Identidad
        persona_str = f"IDENTITY: {user_persona}" if user_persona else "IDENTITY: Expert Social Media User."

        # 3. Construir Prompt Híbrido
        # Si hay user_prompt, lo insertamos COMO INSTRUCCIÓN PRIORITARIA, no reemplazamos todo.
        custom_instruction = ""
        if user_prompt and isinstance(user_prompt, str) and user_prompt.strip():
            custom_instruction = f"IMPORTANT USER INSTRUCTION: {user_prompt}"

        final_prompt = f"""
        ROLE: Social Media Expert.
        TASK: Write a SHORT, natural Instagram comment.
        
        {persona_str}
        {custom_instruction}
        
        INPUT CONTEXT:
        - CAPTION: "{post_context.get('caption')}"
        - IMAGE: "{post_context.get('image_desc')}"
        
        GUIDELINES:
        1. If 'IMPORTANT USER INSTRUCTION' requires a specific language (e.g. Spanish), OBEY IT.
        2. If no language specified, detect language from Caption and match it.
        3. NO EMOJIS (Unless instructed otherwise).
        4. Max length: 1 sentence.
        5. ANGLE: {selected_angle}
        """

        try:
            response = self.model.generate_content(final_prompt)
            text = response.text.strip().replace('"', '').replace("Comment:", "")
            return text
        except:
            return "Great post."

    # ==============================================================================
    # 2. HERRAMIENTAS DE INTERACCIÓN
    # ==============================================================================
    def _click_icon_global(self, target_labels, avoid_labels=None):
        # Lógica de clicks (Like/Save) mantenida igual por ser eficiente
        if avoid_labels:
            conditions_avoid = " or ".join([f"@aria-label='{label}'" for label in avoid_labels])
            xpath_avoid = f"//*[local-name()='svg' and ({conditions_avoid})]"
            try:
                if self.driver.find_elements(By.XPATH, xpath_avoid): return "ALREADY_DONE"
            except: pass

        conditions = " or ".join([f"@aria-label='{label}'" for label in target_labels])
        xpath = f"//*[local-name()='svg' and ({conditions})]/.."
        
        try:
            btn = WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.XPATH, xpath)))
            self.driver.execute_script("arguments[0].click();", btn)
            return "CLICKED"
        except: return "NOT_FOUND"

    def like_post(self):
        print("   -> Like...")
        return self._click_icon_global(["Me gusta", "Like"], ["Deshacer", "Unlike"])

    def save_post(self):
        print("   -> Save...")
        return self._click_icon_global(["Guardar", "Save"], ["Eliminar", "Remove"])

    def comment_post(self, context, user_persona=None, focus_selection=None, user_prompt=None):
        print("   -> Generando Comentario IA...")
        comment_text = self._generate_ai_comment(context, user_persona, focus_selection, user_prompt)
        print(f"   [AI] Texto: {comment_text}")
        
        try:
            xpath_area = "//textarea[@aria-label='Add a comment…'] | //textarea[@aria-label='Agrega un comentario...']"
            wait = WebDriverWait(self.driver, 10)
            
            # 1. UBICAR Y CLICAR (Usando ActionChains como en Escritorio para mayor precisión)
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            try:
                actions = ActionChains(self.driver)
                actions.move_to_element(box).click().perform()
            except:
                self.driver.execute_script("arguments[0].click();", box)

            # Pausa breve para foco
            time.sleep(1)

            # 2. ESCRITURA RÁPIDA (Tiempos ajustados a script-comentarios.py)
            # Re-localizamos por seguridad
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            
            for char in comment_text:
                try:
                    box.send_keys(char)
                except StaleElementReferenceException:
                    box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
                    box.send_keys(char)
                except Exception:
                    # Intento final de recuperación
                    box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
                    box.send_keys(char)
                
                # VELOCIDAD AUMENTADA: 0.02 a 0.07 (Igual que escritorio)
                time.sleep(random.uniform(0.02, 0.07))
            
            time.sleep(random.uniform(0.5, 1.0))
            
            # 3. ENVIAR
            try:
                box.send_keys(Keys.ENTER)
            except StaleElementReferenceException:
                box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
                box.send_keys(Keys.ENTER)
                
            print("   [COMENTARIO] Enviado.")
            return True

        except Exception as e:
            print(f"   [ERROR COMENTARIO] {e}")
            return False

    # ==============================================================================
    # 3. EJECUCIÓN PRINCIPAL
    # ==============================================================================
    def execute_interaction(self, post_url, do_like=True, do_save=False, do_comment=True, 
                          user_persona=None, focus_selection=None, user_prompt=None):
        print(f"--- Interactuando con: {post_url} ---")
        try:
            self.driver.get(post_url)
            time.sleep(random.uniform(3, 5)) # Un poco más rápido que antes
            self.dismiss_popups()

            context = self._get_post_context()
            # Log más limpio para confirmar que leímos bien
            caption_preview = context['caption'][:50].replace('\n', ' ') if context['caption'] else "Sin texto"
            print(f"   [CONTEXTO] Caption: '{caption_preview}...'")

            if do_like:
                self.like_post()
                time.sleep(0.5)

            if do_save:
                self.save_post()
                time.sleep(0.5)

            if do_comment:
                self.comment_post(context, user_persona, focus_selection, user_prompt)
                time.sleep(2)

            return True

        except Exception as e:
            print(f"Error interacción: {e}")
            return False