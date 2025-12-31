import time
import random
import logging
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

logger = logging.getLogger(__name__)

class BotEngine:
    """
    Clase Madre: Maneja el navegador, login y funciones humanas básicas.
    Heredada por ScraperBot, OutreachBot y CommentBot.
    """
    def __init__(self, account_data, proxy_data=None):
        self.account = account_data
        self.proxy = proxy_data
        self.driver = None

    def start_driver(self):
        options = uc.ChromeOptions()
        options.add_argument("--disable-notifications")
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--lang=en-US") 
        
        # PROXY SETUP
        if self.proxy:
            pass

        # HEADLESS (Descomentar para producción real)
        # options.add_argument('--headless=new') 

        # Iniciar Driver
        try:
            # --- CORRECCIÓN AQUÍ: Agregamos version_main=142 ---
            self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
            self.driver.set_window_size(1280, 850)
            logger.info("Chrome iniciado correctamente.")
        except Exception as e:
            logger.error(f"Error iniciando Chrome: {e}")
            raise e

    def login(self):
        """Login usando SessionID (Cookies)"""
        if not self.driver: return False
        try:
            logger.info(f"Logueando: {self.account.username}")
            self.driver.get("https://www.instagram.com/404")
            time.sleep(2)
            
            cookie = {
                'name': 'sessionid',
                'value': self.account.session_id, # Asumiendo que el modelo tiene este campo
                'domain': '.instagram.com',
                'path': '/',
                'secure': True,
                'httpOnly': True
            }
            self.driver.add_cookie(cookie)
            
            self.driver.get("https://www.instagram.com/")
            time.sleep(5)
            self.dismiss_popups()
            return True
        except Exception as e:
            logger.error(f"Error en Login: {e}")
            return False

    def dismiss_popups(self):
        """Cierra popups molestos (Turn on Notifications, etc)"""
        textos = ["Not Now", "Ahora no", "Cancel", "Cancelar"]
        for txt in textos:
            try:
                xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
                botones = self.driver.find_elements(By.XPATH, xpath)
                for btn in botones:
                    if btn.is_displayed():
                        self.driver.execute_script("arguments[0].click();", btn)
                        time.sleep(1)
            except: pass

    def human_typing(self, element_or_xpath, text):
        """
        Escribe texto simulando comportamiento humano.
        Soporta RECONEXIÓN si el elemento se vuelve 'stale' (refresco de React).
        Puede recibir un WebElement o un XPath (str).
        """
        wait = WebDriverWait(self.driver, 10)
        
        # Si nos pasan un objeto WebElement, necesitamos su XPath para poder reconectarlo
        # Si nos pasan un string, lo usamos directo.
        xpath = element_or_xpath
        element = None

        if not isinstance(element_or_xpath, str):
            # Es un WebElement, intentamos escribir directo, pero si falla no tenemos el xpath para recuperar
            # Por eso en CommentBot debemos pasar el XPATH, no el elemento.
            element = element_or_xpath
        else:
            # Es un XPath, lo buscamos
            try:
                element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
            except:
                logger.warning(f"No se encontró elemento para escribir: {xpath}")
                return

        # Escritura letra por letra
        for char in text:
            try:
                element.send_keys(char)
                time.sleep(random.uniform(0.03, 0.09))
            except StaleElementReferenceException:
                # RECUPERACIÓN DE ERROR (El Bug de la "letra única")
                if isinstance(element_or_xpath, str):
                    element = wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
                    element.send_keys(char)
                    time.sleep(random.uniform(0.03, 0.09))
                else:
                    logger.error("Elemento Stale y no tengo XPath para recuperarlo.")
                    break
            except Exception as e:
                logger.error(f"Error escribiendo: {e}")
                break

    def close(self):
        if self.driver:
            try: self.driver.quit()
            except: pass