import time
import random
import re
import google.generativeai as genai
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

# Importamos la Clase Madre
from .engine_base import BotEngine

class CommentBot(BotEngine):
    """
    Motor de Interacción: Comenta, Da Like y Guarda posts.
    Versión 6.1: SaaS Ready (Soporta instrucciones personalizadas del cliente).
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
        context = {"caption": "", "image_desc": "Visual content"}
        try:
            try:
                meta_desc = self.driver.find_element(By.XPATH, "//meta[@property='og:description'] | //meta[@name='description']")
                raw_content = meta_desc.get_attribute("content")
                clean_caption = raw_content
                
                if " on Instagram" in raw_content and ":" in raw_content:
                    clean_caption = raw_content.split(":", 1)[1].strip().replace('"', '').replace("'", "")
                
                if "likes" in clean_caption.lower() and "comments" in clean_caption.lower():
                    clean_caption = "" 
                
                context["caption"] = clean_caption
            except: pass

            try:
                img_elem = self.driver.find_element(By.XPATH, "//img[@alt and string-length(@alt)>5]")
                alt = img_elem.get_attribute("alt")
                if alt: context["image_desc"] = alt
            except: pass

        except Exception as e:
            print(f"[Error Contexto] {e}")
            
        return context

    def _generate_ai_comment(self, post_context, user_persona=None, focus_selection=None):
        """
        Genera comentario recibiendo parámetros opcionales del Dashboard del cliente.
        """
        
        # 1. DEFINIR FOCO (ANGLES)
        # Si el cliente seleccionó focos en el Dashboard, usamos esos.
        # Si no, usamos los predeterminados.
        if focus_selection and isinstance(focus_selection, list) and len(focus_selection) > 0:
            # Ejemplo: El cliente marcó ["Humor", "Pregunta"]
            selected_angle = random.choice(focus_selection)
        else:
            # Default (Tu lógica actual)
            text_angles = [
                "FOCUS: Compliment the visual aesthetic.",
                "FOCUS: Minimalist agreement (Cool, Great shot).",
                "FOCUS: Highlight the mood of the image."
            ]
            caption = post_context.get('caption', '')
            if len(caption) > 5:
                text_angles.extend([
                    "FOCUS: Agree with the main point of the text.",
                    "FOCUS: Mention a keyword from the caption.",
                    "FOCUS: Highlight the mindset described."
                ])
            selected_angle = random.choice(text_angles)
        
        # 2. DEFINIR PERSONA (Instrucción Extra)
        # Si el cliente escribió algo en el textarea: "Soy coach de fitness, sé sarcástico."
        custom_instruction_str = ""
        if user_persona:
            custom_instruction_str = f"USER IDENTITY/STYLE: {user_persona} (Adopt this persona)."

        # Palabras prohibidas
        common_words = ["wow", "good", "great", "nice", "love", "awesome", "amazing"]
        forbidden = random.sample(common_words, 3)
        
        prompt = f"""
        ROLE: Expert Social Media User.
        TASK: Write a SHORT, natural comment for an Instagram post.
        
        {custom_instruction_str}
        
        INPUT DATA:
        - CAPTION: "{post_context.get('caption')}"
        - IMAGE: "{post_context.get('image_desc')}"
        
        LOGIC:
        1. If CAPTION is empty/garbage -> Ignore it, use IMAGE only.
        2. Else -> Connect CAPTION topic with IMAGE.
        
        CONSTRAINTS:
        - Angle: {selected_angle}
        - Language: ENGLISH ONLY.
        - NO EMOJIS (Strict).
        - Max Length: 6-8 words.
        - Forbidden words: {forbidden}
        """
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip().replace('"', '').replace("Comment:", "")
            if len(text) > 100 or ":" in text: return "Solid visual."
            return text
        except:
            return "Solid view."

    # ==============================================================================
    # 2. HERRAMIENTAS DE INTERACCIÓN
    # ==============================================================================

    def _click_icon_global(self, target_labels, avoid_labels=None):
        if avoid_labels:
            conditions_avoid = " or ".join([f"@aria-label='{label}'" for label in avoid_labels])
            xpath_avoid = f"//*[local-name()='svg' and ({conditions_avoid})]"
            try:
                if self.driver.find_elements(By.XPATH, xpath_avoid):
                    return "ALREADY_DONE"
            except: pass

        conditions = " or ".join([f"@aria-label='{label}'" for label in target_labels])
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
        targets = ["Me gusta", "Like"]
        avoids = ["Deshacer me gusta", "Ya no me gusta", "Unlike"]
        return True if self._click_icon_global(targets, avoids) in ["CLICKED", "ALREADY_DONE"] else False

    def save_post(self):
        print("   -> Intentando Guardar...")
        targets = ["Guardar", "Save"]
        avoids = ["Eliminar", "Eliminar de guardado", "Remove", "Unsave"]
        return True if self._click_icon_global(targets, avoids) in ["CLICKED", "ALREADY_DONE"] else False

    def comment_post(self, context, user_persona=None, focus_selection=None):
        print("   -> Generando Comentario IA...")
        
        # --- CAMBIO AQUÍ: Pasamos las preferencias del usuario ---
        comment_text = self._generate_ai_comment(context, user_persona, focus_selection)
        print(f"   [AI] Texto: {comment_text}")
        
        try:
            xpath_area = "//textarea[@aria-label='Add a comment…'] | //textarea[@aria-label='Agrega un comentario...']"
            wait = WebDriverWait(self.driver, 10)
            
            box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            self.driver.execute_script("arguments[0].click();", box)
            time.sleep(1)
            
            self.human_typing(xpath_area, comment_text)
            time.sleep(random.uniform(0.5, 1.5))
            
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
    # 3. EJECUCIÓN PRINCIPAL CON PARÁMETROS
    # ==============================================================================
    def execute_interaction(self, post_url, do_like=True, do_save=False, do_comment=True, 
                          user_persona=None, focus_selection=None):
        """
        Ahora acepta user_persona (Texto) y focus_selection (Lista)
        """
        print(f"--- Interactuando con: {post_url} ---")
        try:
            self.driver.get(post_url)
            time.sleep(random.uniform(4, 6))
            self.dismiss_popups()

            context = self._get_post_context()
            print(f"   [CONTEXTO] Caption limpio: '{context['caption'][:40]}...'")

            if do_like:
                self.like_post()
                time.sleep(random.uniform(1, 2))

            if do_save:
                self.save_post()
                time.sleep(random.uniform(1, 2))

            if do_comment:
                # Pasamos los parámetros hacia abajo
                self.comment_post(context, user_persona, focus_selection)
                time.sleep(random.uniform(3, 5))

            return True

        except Exception as e:
            print(f"Error interacción: {e}")
            return False