import os
import time
import random
import logging
import shutil
import requests
from urllib.parse import urlparse
from django.core.management.base import BaseCommand
from django.conf import settings

# Selenium Imports
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys

# Modelos
from automation.models import IGAccount
try:
    from automation.models import SystemLog
except ImportError:
    SystemLog = None

logger = logging.getLogger(__name__)

class SeleniumHarvesterBot:
    def __init__(self):
        self.driver = None
        self.download_path = "media/harvested_avatars"
        os.makedirs(self.download_path, exist_ok=True)
        
        # Cargar cuentas activas
        self.pool = list(IGAccount.objects.filter(status__iexact='active')
                         .exclude(session_id__isnull=True)
                         .exclude(session_id=""))
        random.shuffle(self.pool)

    def log(self, msg, level='info'):
        print(f"[{level.upper()}] {msg}")
        if SystemLog:
            try:
                SystemLog.objects.create(level=level, message=msg)
            except: pass

    def _get_proxy_config(self, account):
        # 1. Cuenta
        if account.proxy_host and account.proxy_port:
            return (account.proxy_host, account.proxy_port, account.proxy_user, account.proxy_password)
        
        # 2. Global (.env)
        enabled = os.getenv("BRIGHTDATA_PROXY_ENABLED") or getattr(settings, "BRIGHTDATA_PROXY_ENABLED", "0")
        if str(enabled) == "1" or str(enabled).lower() == "true":
            return (
                os.getenv("BRIGHTDATA_PROXY_HOST"),
                os.getenv("BRIGHTDATA_PROXY_PORT"),
                os.getenv("BRIGHTDATA_PROXY_USER"),
                os.getenv("BRIGHTDATA_PROXY_PASSWORD")
            )
        return None

    def _create_proxy_auth_folder(self, host, port, user, password, session_id):
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 3,
            "name": "Chrome Proxy Auth V3",
            "permissions": ["proxy", "webRequest", "webRequestAuthProvider", "webRequestBlocking"],
            "host_permissions": ["<all_urls>"],
            "background": {"service_worker": "background.js"}
        }
        """
        background_js = f"""
        var config = {{
            mode: "fixed_servers",
            rules: {{
                singleProxy: {{scheme: "http", host: "{host}", port: parseInt({port})}},
                bypassList: ["localhost"]
            }}
        }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        function callbackFn(details) {{
            return {{ authCredentials: {{ username: "{user}", password: "{password}" }} }};
        }}
        chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
        """
        
        folder_name = os.path.join(os.getcwd(), f'proxy_ext_{session_id}')
        if not os.path.exists(folder_name):
            os.makedirs(folder_name)
            
        with open(os.path.join(folder_name, "manifest.json"), 'w') as f:
            f.write(manifest_json)
        with open(os.path.join(folder_name, "background.js"), 'w') as f:
            f.write(background_js)
            
        return folder_name

    def _init_driver(self, account):
        proxy_conf = self._get_proxy_config(account)
        options = uc.ChromeOptions()
        plugin_path = None
        
        if proxy_conf:
            host, port, user, pwd = proxy_conf
            safe_sess = account.session_id[-6:] if account.session_id else "000000"
            if user and pwd:
                plugin_path = self._create_proxy_auth_folder(host, port, user, pwd, safe_sess)
                options.add_argument(f'--load-extension={plugin_path}')
            else:
                options.add_argument(f'--proxy-server={host}:{port}')

        options.add_argument("--no-first-run")
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--password-store=basic")
        options.add_argument("--lang=en-US") 

        self.log(f" Iniciando navegador (v142) con cuenta: {account.username}")
        self.driver = uc.Chrome(options=options, version_main=142)
        self.driver.set_window_size(1280, 900)
        self.current_plugin_path = plugin_path

    def login_and_validate(self, account):
        try:
            self._init_driver(account)
            
            self.driver.get("https://www.instagram.com/404")
            time.sleep(2)

            self.driver.add_cookie({
                'name': 'sessionid',
                'value': account.session_id,
                'domain': '.instagram.com',
                'path': '/',
                'secure': True,
                'httpOnly': True
            })

            self.driver.get("https://www.instagram.com/")
            time.sleep(random.uniform(5, 7))

            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/explore/')] | //svg[@aria-label='Home'] | //svg[@aria-label='Inicio']"))
                )
                self._dismiss_popups()
                self.log(" Login exitoso.", 'success')
                return True
            except:
                if "login" in self.driver.current_url:
                    self.log(" La cookie expiró.", 'error')
                else:
                    self.log("️ No se confirmó el login (posible checkpoint).", 'warn')
                return False

        except Exception as e:
            self.log(f" Error driver: {e}", 'error')
            self._cleanup()
            return False

    def _dismiss_popups(self):
        try:
            xpath = "//button[text()='Not Now'] | //button[text()='Ahora no'] | //button[text()='Cancel']"
            btns = self.driver.find_elements(By.XPATH, xpath)
            for btn in btns:
                try: btn.click(); time.sleep(1)
                except: pass
        except: pass

    def _download_image(self, url, username):
        if not url: return False
        try:
            resp = requests.get(url, timeout=10)
            if resp.status_code == 200:
                path = os.path.join(self.download_path, f"{username}.jpg")
                with open(path, 'wb') as f:
                    f.write(resp.content)
                return True
        except: pass
        return False

    def _extract_hd_avatar_from_profile(self, username):
        try:
            try:
                meta_img = self.driver.find_element(By.XPATH, "//meta[@property='og:image']")
                img_url = meta_img.get_attribute("content")
                if img_url: return img_url
            except: pass

            imgs = self.driver.find_elements(By.TAG_NAME, "img")
            for img in imgs:
                alt = img.get_attribute("alt")
                if alt and ("profile picture" in alt or "foto del perfil" in alt):
                    return img.get_attribute("src")
            return None
        except: return None

    def harvest(self, target_username, quantity):
        if not self.pool:
            self.log("No hay cuentas disponibles.", 'error')
            return

        for account in self.pool:
            if self.login_and_validate(account):
                self.log(f" Navegando a: {target_username}")
                self.driver.get(f"https://www.instagram.com/{target_username}/")
                time.sleep(4)
                self._dismiss_popups()

                try:
                    self.log("Buscando enlace de seguidores...")
                    # Selector robusto
                    followers_link = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, '/followers/')]"))
                    )
                    followers_link.click()
                    
                    dialog_box = WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']"))
                    )
                    
                    self.log("⬇️ Diálogo abierto. Esperando carga de items...")
                    time.sleep(4) # Espera generosa inicial

                    collected = 0
                    processed_users = set()
                    consecutive_fails = 0
                    main_window = self.driver.current_window_handle
                    MAX_CONSECUTIVE_FAILS = 15 

                    while collected < quantity:
                        try:
                            # Buscar elementos 'a' de forma general dentro del diálogo
                            elements = dialog_box.find_elements(By.TAG_NAME, "a")
                        except: break

                        new_candidates = []
                        last_element_found = None

                        # --- DEBUG: Ver qué ve el bot ---
                        # print(f"DEBUG: Enlaces raw encontrados: {len(elements)}")

                        for elem in elements:
                            try:
                                href = elem.get_attribute('href')
                                # Filtro más permisivo: solo debe tener un link válido
                                if not href or len(href) < 10: continue
                                
                                # Limpieza
                                clean_href = href.split('?')[0].rstrip('/')
                                user = clean_href.split('/')[-1]
                                
                                # Filtros de seguridad
                                if user == target_username: continue
                                if user in processed_users: 
                                    last_element_found = elem
                                    continue
                                
                                # Palabras prohibidas en la URL
                                forbidden = ['/p/', '/explore/', '/direct/', '/stories/', '/reels/', '/tv/']
                                if any(x in clean_href for x in forbidden): continue
                                
                                new_candidates.append(user)
                                processed_users.add(user)
                                last_element_found = elem
                                
                            except: pass

                        if not new_candidates:
                            consecutive_fails += 1
                            if consecutive_fails % 3 == 0:
                                self.log(f"⏳ Scroll vacío ({consecutive_fails}/{MAX_CONSECUTIVE_FAILS}) - Intentando bajar...", 'info')
                            
                            if consecutive_fails >= MAX_CONSECUTIVE_FAILS:
                                self.log("️ Timeout: No cargan más usuarios.", 'warn')
                                break
                            
                            # ESTRATEGIA DE SCROLL DE EMERGENCIA
                            try:
                                if last_element_found:
                                    self.driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                                else:
                                    # Si no hay 'last_element_found', buscamos el contenedor scrollable explícitamente
                                    # Instagram suele usar esta clase o style overflow-y: auto
                                    scrollable = dialog_box.find_element(By.XPATH, ".//div[contains(@style, 'overflow: hidden auto') or contains(@style, 'overflow-y: auto')]")
                                    self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scrollable)
                            except:
                                # Fallback último recurso
                                self.driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", dialog_box)
                            
                            time.sleep(2.5)
                            continue
                        
                        consecutive_fails = 0 

                        self.log(f"   Procesando {len(new_candidates)} usuarios nuevos...")
                        
                        for user in new_candidates:
                            if collected >= quantity: break
                            
                            try:
                                self.driver.execute_script("window.open('about:blank', '_blank');")
                                WebDriverWait(self.driver, 5).until(lambda d: len(d.window_handles) > 1)
                                self.driver.switch_to.window(self.driver.window_handles[-1])
                                
                                self.driver.get(f"https://www.instagram.com/{user}/")
                                
                                # Esperamos a que cargue algo visual del perfil
                                try:
                                    WebDriverWait(self.driver, 6).until(
                                        EC.presence_of_element_located((By.TAG_NAME, "img"))
                                    )
                                    
                                    img_url = self._extract_hd_avatar_from_profile(user)
                                    
                                    if img_url and self._download_image(img_url, user):
                                        collected += 1
                                        print(f"   -> [{collected}/{quantity}] Foto guardada: {user}")
                                except Exception:
                                    pass # Timeout de carga o perfil vacío

                                self.driver.close()
                                self.driver.switch_to.window(main_window)
                                time.sleep(random.uniform(2, 4)) # Pausa anti-bloqueo
                                
                            except Exception as e:
                                print(f"   [ERROR] Pestaña: {e}")
                                try:
                                    while len(self.driver.window_handles) > 1:
                                        self.driver.switch_to.window(self.driver.window_handles[-1])
                                        self.driver.close()
                                    self.driver.switch_to.window(main_window)
                                except: pass

                        # Scroll natural al final del lote
                        if last_element_found:
                             self.driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                        time.sleep(random.uniform(1.5, 3))

                    self.log(f" Finalizado. {collected} fotos en total.", 'success')
                    break 

                except Exception as e:
                    self.log(f"Error scraping con esta cuenta: {e}", 'error')
                finally:
                    self._cleanup()
            else:
                self.log("Intentando con siguiente cuenta...", 'warn')

    def _cleanup(self):
        if self.driver: 
            try: self.driver.quit()
            except: pass
        if hasattr(self, 'current_plugin_path') and self.current_plugin_path:
            if os.path.exists(self.current_plugin_path):
                try: shutil.rmtree(self.current_plugin_path)
                except: pass

class Command(BaseCommand):
    help = "Descarga fotos usando Selenium."

    def add_arguments(self, parser):
        parser.add_argument('url', type=str, help='Usuario objetivo')
        parser.add_argument('--quantity', type=int, default=10, help='Cantidad')

    def handle(self, *args, **options):
        raw_input = options['url']
        quantity = options['quantity']

        if "instagram.com" in raw_input:
            path = urlparse(raw_input).path.strip("/")
            target_username = path.split("/")[0]
        else:
            target_username = raw_input.strip()

        bot = SeleniumHarvesterBot()
        bot.harvest(target_username, quantity)