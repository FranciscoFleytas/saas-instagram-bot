import time
import os
import shutil
import random
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BotEngine:
    """
    CLASE MADRE: Gestiona el navegador, proxy, cookies y login.
    Todos los bots (Scraper, Outreach, Comment) heredan de aquí.
    """
    
    def __init__(self, account_data, proxy_data=None):
        self.account = account_data
        self.proxy = proxy_data
        self.driver = None
        
        # Inicializamos el navegador automáticamente al crear la clase
        self.init_driver()
        self.login_if_needed()

    def init_driver(self):
        """Configura Chrome con permisos para Pop-ups y Proxy"""
        print(f"[{self.account.username}] Inicializando Motor Chrome...")
        
        options = uc.ChromeOptions()
        
        # --- CONFIGURACIÓN CRÍTICA PARA POP-UPS ---
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-notifications")
        
        # Preferencias avanzadas: 1 = Permitir, 2 = Bloquear
        prefs = {
            "profile.default_content_setting_values.popups": 1,       # <--- ESTO ARREGLA EL BLOQUEO
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False
        }
        options.add_experimental_option("prefs", prefs)
        # -------------------------------------------

        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--start-maximized")
        # options.add_argument("--headless=new") # Descomentar si quieres modo invisible

        # Configuración de Proxy (si existe)
        plugin_path = None
        if self.proxy:
            plugin_path = self._create_proxy_auth_extension(
                self.proxy['host'], self.proxy['port'], 
                self.proxy['user'], self.proxy['pass']
            )
            options.add_argument(f'--load-extension={plugin_path}')

        try:
            # Iniciar Chrome
            self.driver = uc.Chrome(options=options, version_main=142) # Ajusta versión si es necesario
            self.driver.set_window_size(1280, 800)
        except Exception as e:
            print(f"Error fatal iniciando Chrome: {e}")
            raise e
        finally:
            # Limpieza de carpeta temporal del proxy
            if plugin_path and os.path.exists(plugin_path):
                try: shutil.rmtree(plugin_path)
                except: pass

    def login_if_needed(self):
        """Maneja el login usando cookies o contraseña"""
        try:
            self.driver.get("https://www.instagram.com/")
            time.sleep(3)

            # 1. Intento por COOKIES (SessionID)
            if self.account.session_id:
                print(f"[{self.account.username}] Intentando login con SessionID...")
                self.driver.add_cookie({
                    'name': 'sessionid',
                    'value': self.account.session_id,
                    'domain': '.instagram.com',
                    'path': '/',
                    'secure': True,
                    'httpOnly': True
                })
                self.driver.refresh()
                time.sleep(5)
                
                if self._is_logged_in():
                    print(f"[{self.account.username}] Login con Cookie EXITOSO.")
                    return

            # 2. Intento por CREDENCIALES (Usuario/Pass)
            print(f"[{self.account.username}] Login con Cookie falló/no existe. Usando Password...")
            self._login_manual()

        except Exception as e:
            print(f"Error en Login: {e}")

    def _login_manual(self):
        try:
            user_input = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )
            pass_input = self.driver.find_element(By.NAME, "password")
            
            user_input.clear()
            user_input.send_keys(self.account.username)
            time.sleep(1)
            
            pass_input.clear()
            # Desencriptamos la contraseña si es necesario
            password = self.account.get_password()
            pass_input.send_keys(password)
            
            pass_input.send_keys(Keys.ENTER) # type: ignore
            time.sleep(8)
            
            if self._is_logged_in():
                print(f"[{self.account.username}] Login manual EXITOSO.")
                # Opcional: Aquí podrías guardar la nueva cookie en DB
            else:
                print(f"[{self.account.username}] FALLO Login manual.")
                
        except Exception as e:
            print(f"Error Login Manual: {e}")

    def _is_logged_in(self):
        """Verifica si estamos dentro detectando elementos de la UI"""
        try:
            # Buscamos iconos típicos de usuario logueado (Home, Search, Avatar)
            self.driver.find_element(By.XPATH, "//*[local-name()='svg' and @aria-label='Home' or @aria-label='Inicio']")
            return True
        except:
            if "accounts/login" in self.driver.current_url:
                return False
            # A veces IG carga pero no muestra el Home inmediatamente
            return False

    def _create_proxy_auth_extension(self, host, port, user, password):
        """Crea extensión temporal para autenticar el proxy"""
        session_id = str(random.randint(10000, 99999))
        folder = os.path.join(os.getcwd(), f'proxy_auth_{session_id}')
        os.makedirs(folder, exist_ok=True)
        
        manifest_json = """
        {
            "version": "1.0.0",
            "manifest_version": 3,
            "name": "Chrome Proxy Auth",
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
        
        with open(os.path.join(folder, "manifest.json"), 'w') as f: f.write(manifest_json)
        with open(os.path.join(folder, "background.js"), 'w') as f: f.write(background_js)
        return folder

    def human_typing(self, element, text):
        """Simula escritura humana con pausas aleatorias"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.05, 0.15))

    def dismiss_popups(self):
        """Cierra popups molestos de 'Activar Notificaciones'"""
        try:
            btn = WebDriverWait(self.driver, 2).until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Not Now' or text()='Ahora no']"))
            )
            btn.click()
        except: pass

    def quit(self):
        if self.driver:
            self.driver.quit()