import time
import random
from instagrapi import Client
from automation.models import IGAccount

class FastInteractionBot:
    """
    Motor de Interacción vía API (Instagrapi).
    Manejo inteligente de fallos: Si la Cookie falla, usa Password automáticamente.
    """
    def __init__(self, account_data: IGAccount, proxy_data: dict = None):
        self.account = account_data
        self.client = Client()
        
        # Configurar Proxy si existe
        if proxy_data:
            proxy_url = f"http://{proxy_data['user']}:{proxy_data['pass']}@{proxy_data['host']}:{proxy_data['port']}"
            self.client.set_proxy(proxy_url)

    def login(self):
        print(f"[API BOT] Intentando login para {self.account.username}...")
        
        # ---------------------------------------------------------
        # ESTRATEGIA 1: Session ID (Cookies Importadas)
        # ---------------------------------------------------------
        if self.account.session_id:
            try:
                print(f"   -> Probando SessionID (Cookie)...")
                self.client.login_by_sessionid(self.account.session_id)
                print(f"   [OK] Login por Cookie exitoso.")
                return True
            except Exception as e:
                print(f"   [WARN] Falló SessionID ({e}). Pasando a estrategia de Password...")
                # NO detenemos el script, dejamos que continúe a la Estrategia 2
                
                # Pequeña pausa para no saturar si hubo error 429
                time.sleep(2)

        # ---------------------------------------------------------
        # ESTRATEGIA 2: Contraseña Real (Fallback)
        # ---------------------------------------------------------
        try:
            print(f"   -> Probando con Contraseña...")
            password = self.account.get_password()
            
            # Instagrapi maneja el 2FA y challenges básicos automáticamente aquí
            self.client.login(self.account.username, password)
            
            # Si llegamos aquí, tuvimos éxito.
            # Opcional: Actualizar la session_id en BD para la próxima vez
            try:
                new_session = self.client.sessionid
                if new_session:
                    self.account.session_id = new_session
                    self.account.save()
                    print("   [INFO] SessionID renovado y guardado en DB.")
            except: pass
            
            return True

        except Exception as e:
            print(f"[API ERROR] Login definitivo falló: {e}")
            return False

    def execute(self, post_url, do_like=True, do_comment=False, comment_text=None):
        try:
            # 1. Obtener ID del post
            media_pk = self.client.media_pk_from_url(post_url)
            media_id = self.client.media_id(media_pk)
            
            print(f"   [API] Interactuando con Media ID: {media_id}")

            # 2. LIKE
            if do_like:
                print("   -> Like enviado (API)...")
                self.client.media_like(media_id)
                time.sleep(random.uniform(1.5, 3.5))

            # 3. COMENTARIO
            if do_comment and comment_text:
                print(f"   -> Comentario enviado: '{comment_text}'")
                self.client.media_comment(media_id, comment_text)
                time.sleep(random.uniform(2, 5))

            return True

        except Exception as e:
            print(f"[API ERROR] Falló interacción: {e}")
            return False