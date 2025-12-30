import os
import time
import random
import shutil
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class BotEngine:
    """
    CLASE MADRE: Infraestructura base.
    Maneja Chrome, Proxy Auth, Login y Evasión.
    """
    def __init__(self, account_data, proxy_data=None, headless=False):
        self.username = account_data.username
        self.session_id = account_data.session_id
        self.proxy = proxy_data
        self.headless = headless
        self.driver = None
        self.plugin_path = None
        self.base_dir = os.path.dirname(os.path.abspath(__file__))

    def _create_proxy_auth_extension(self):
        """Crea la extensión de Chrome para autenticar el Proxy"""
        if not self.proxy: return None
        
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
                singleProxy: {{scheme: "http", host: "{self.proxy.ip_address}", port: parseInt({self.proxy.port})}},
                bypassList: ["localhost"]
            }}
        }};
        chrome.proxy.settings.set({{value: config, scope: "regular"}}, function() {{}});
        function callbackFn(details) {{
            return {{ authCredentials: {{ username: "{self.proxy.username}", password: "{self.proxy.password}" }} }};
        }}
        chrome.webRequest.onAuthRequired.addListener(callbackFn, {{urls: ["<all_urls>"]}}, ['blocking']);
        """
        
        # Usamos /tmp para que sea volátil y no ensucie el proyecto
        folder_name = f"/tmp/proxy_auth_{random.randint(10000,99999)}_{self.username}"
        if not os.path.exists(folder_name): os.makedirs(folder_name)
        
        with open(os.path.join(folder_name, "manifest.json"), 'w') as f: f.write(manifest_json)
        with open(os.path.join(folder_name, "background.js"), 'w') as f: f.write(background_js)
        
        return folder_name

    def start_driver(self):
        """Inicia el navegador con undetected-chromedriver"""
        self.plugin_path = self._create_proxy_auth_extension()
        
        options = uc.ChromeOptions()
        if self.plugin_path:
            options.add_argument(f'--load-extension={self.plugin_path}')
        
        options.add_argument("--disable-notifications")
        options.add_argument("--disable-popup-blocking")
        options.add_argument('--lang=en-US') # Forzamos inglés para selectores estables
        options.add_argument('--no-sandbox')
        
        if self.headless:
            options.add_argument('--headless=new')
            
        # Optimización de carga (Imágenes desactivadas parcialmente)
        options.page_load_strategy = 'eager'
        prefs = {"profile.managed_default_content_settings.images": 2}
        options.add_experimental_option("prefs", prefs)

        # Versión fija para evitar problemas con actualizaciones de Chrome
        self.driver = uc.Chrome(options=options, use_subprocess=True, version_main=142)
        self.driver.set_window_size(1280, 800)

    def login(self):
        """Inyecta la cookie de sesión"""
        if not self.driver: raise Exception("Driver no iniciado")
        
        print(f"--- Logueando: {self.username} ---")
        self.driver.get("https://www.instagram.com/404")
        time.sleep(1.5)
        
        self.driver.add_cookie({
            'name': 'sessionid',
            'value': self.session_id,
            'domain': '.instagram.com',
            'path': '/',
            'secure': True,
            'httpOnly': True
        })
        
        self.driver.get("https://www.instagram.com/")
        time.sleep(5)
        self.dismiss_popups()

        if "login" in self.driver.current_url:
            raise Exception("Fallo de Login: SessionID expirada")

    def dismiss_popups(self):
        """Cierra modales de notificaciones"""
        textos = ["Not Now", "Ahora no", "Cancel", "Cancelar"]
        for txt in textos:
            try:
                xpath = f"//button[contains(text(), '{txt}')] | //div[@role='button'][contains(text(), '{txt}')]"
                btns = self.driver.find_elements(By.XPATH, xpath)
                for btn in btns:
                    self.driver.execute_script("arguments[0].click();", btn)
            except: pass

    def human_typing(self, element, text):
        """Simula escritura humana"""
        for char in text:
            element.send_keys(char)
            time.sleep(random.uniform(0.03, 0.08))

    def close(self):
        """Cierra navegador y limpia archivos temporales"""
        if self.driver:
            try: self.driver.quit()
            except: pass
        if self.plugin_path and os.path.exists(self.plugin_path):
            try: shutil.rmtree(self.plugin_path)
            except: pass