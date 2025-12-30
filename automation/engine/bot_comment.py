import time
import random
import google.generativeai as genai
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException

# Importamos la Clase Madre
from .engine_base import BotEngine

class CommentBot(BotEngine):
    """
    Motor de Engagement: Comenta posts usando Gemini Vision (Contexto).
    Hereda la navegación segura de BotEngine.
    """

    def __init__(self, account_data, proxy_data=None, headless=False):
        super().__init__(account_data, proxy_data, headless)
        
        # Configuración de IA (Igual que en tu script original)
        # RECOMENDACIÓN: Mover API KEY a settings.py o variables de entorno
        genai.configure(api_key="AIzaSyCAn6MmtSo9mkVzWOcO0KOdcnRD9U7KB-g")
        self.model = genai.GenerativeModel('gemini-2.5-flash')

    def _get_post_context(self):
        """
        Extrae la descripción (Caption) y Alt Text de la imagen.
        Lógica preservada de tu script-comentarios.py
        """
        context = {"caption": "", "image_desc": ""}
        try:
            # 1. Meta Tag og:description (Más fiable que leer el DOM visual)
            try:
                meta_desc = self.driver.find_element(By.XPATH, "//meta[@property='og:description'] | //meta[@name='description']")
                raw_content = meta_desc.get_attribute("content")
                
                # Limpieza: El texto suele venir formato 'likes, comments - usuario: "TEXTO"'
                if ":" in raw_content:
                    clean_caption = raw_content.split(":", 1)[1].strip()
                    clean_caption = clean_caption.replace('"', '')
                    context["caption"] = clean_caption
                else:
                    context["caption"] = raw_content
            except: pass

            # 2. Alt Text de la imagen (Respaldo visual)
            try:
                img_elem = self.driver.find_element(By.XPATH, "//article//img")
                alt = img_elem.get_attribute("alt")
                if alt: context["image_desc"] = alt
            except: pass

        except: pass
        return context

    def _generate_ai_comment(self, post_context, custom_instruction=None):
        """Genera el comentario usando Gemini con tus 'Ángulos' de venta"""
        
        # Ángulos rotativos para evitar patrones repetitivos
        text_angles = [
            "FOCUS: Agree strongly with the main point.",
            "FOCUS: Pick a specific keyword from the caption.",
            "FOCUS: Compliment the clarity of the explanation.",
            "FOCUS: Minimalist agreement (3-5 words).",
            "FOCUS: Highlight the mindset behind the text.",
            "FOCUS: Express gratitude for sharing this insight.",
            "FOCUS: Professional acknowledgment of the strategy."
        ]
        
        common_words = ["good", "great", "nice", "love", "awesome", "amazing", "true", "agree"]
        forbidden = random.sample(common_words, 3) # Bloqueamos 3 al azar cada vez
        
        selected_angle = random.choice(text_angles)
        
        # Si el usuario definió un prompt personalizado (Feature nueva del PDF)
        extra_instruction = ""
        if custom_instruction:
            extra_instruction = f"USER CUSTOM RULE: {custom_instruction}"

        prompt = f"""
        ROLE: Expert Social Media User.
        TASK: Write a comment for an Instagram post.
        
        POST CONTEXT:
        - Caption: "{post_context.get('caption')}"
        - Visual: "{post_context.get('image_desc')}"
        
        INSTRUCTION:
        1. Read the Caption carefully.
        2. Write a comment that proves you read it.
        3. Angle: {selected_angle}
        4. {extra_instruction}
        
        CONSTRAINTS:
        1. Language: ENGLISH ONLY.
        2. NO EMOJIS (Strict).
        3. DO NOT use these words: {forbidden}.
        4. Keep it natural and short (1 sentence).
        """
        try:
            response = self.model.generate_content(prompt)
            text = response.text.strip().replace('"', '').replace("Comment:", "")
            return text
        except:
            return "Solid perspective."

    def execute_comment(self, post_url):
        """
        Función Principal: Navega al post y deja el comentario.
        """
        print(f"--- Comentando en: {post_url} ---")
        self.driver.get(post_url)
        time.sleep(random.uniform(5, 7))
        self.dismiss_popups()
        
        # 1. Analizar contexto
        context = self._get_post_context()
        print(f"Contexto capturado: {context['caption'][:50]}...")
        
        # 2. Generar texto
        comment_text = self._generate_ai_comment(context)
        print(f"Gemini generó: {comment_text}")
        
        wait = WebDriverWait(self.driver, 10)
        xpath_area = "//textarea[@aria-label='Agrega un comentario...'] | //textarea[@aria-label='Add a comment…']"
        
        try:
            # 3. Localizar caja de texto
            comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
            
            # Click seguro (ActionChains)
            try:
                actions = ActionChains(self.driver)
                actions.move_to_element(comment_box).click().perform()
            except StaleElementReferenceException:
                comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
                ActionChains(self.driver).move_to_element(comment_box).click().perform()

            time.sleep(1)
            
            # 4. Escribir (Usando método de la Clase Madre)
            self.human_typing(comment_box, comment_text)
            time.sleep(random.uniform(1, 2))
            
            # 5. Enviar (Enter)
            try:
                comment_box.send_keys(Keys.ENTER)
            except StaleElementReferenceException:
                comment_box = wait.until(EC.presence_of_element_located((By.XPATH, xpath_area)))
                comment_box.send_keys(Keys.ENTER)
            
            time.sleep(4)
            print("Comentario publicado exitosamente.")
            return True

        except Exception as e:
            print(f"Error al comentar: {e}")
            return False