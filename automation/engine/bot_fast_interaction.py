import time
import random
import logging
from instagrapi import Client
from automation.models import SystemLog

logger = logging.getLogger(__name__)

class FastInteractionBot:
    """
    Bot de Interacción Rápida (Enjambre).
    POLÍTICA: Cookie-Only. Jamás usa contraseña.
    """

    def __init__(self, account, proxy_data=None):
        self.account = account
        self.client = Client()
        
        # Configuración de Proxy
        if proxy_data:
            proxy_url = f"http://{proxy_data['user']}:{proxy_data['pass']}@{proxy_data['host']}:{proxy_data['port']}"
            self.client.set_proxy(proxy_url)

    def log(self, msg, level='info'):
        """Escribe en la terminal y en la base de datos"""
        print(f"[{level.upper()}] {msg}")
        try:
            SystemLog.objects.create(level=level, message=msg)
        except: pass

    def login(self):
        self.log(f"🛡️ Verificando identidad de {self.account.username}...", 'info')
        
        # 1. Validación Previa
        if not self.account.session_id:
            self.log(f"❌ [ABORT] Cuenta sin SessionID. Omitiendo.", 'error')
            return False

        # 2. Intento ÚNICO por Cookie
        try:
            self.log("-> Inyectando SessionID...", 'info')
            self.client.login_by_sessionid(self.account.session_id)
            self.log("✅ Sesión activa y validada.", 'success')
            return True
        except Exception as e:
            # Si falla la cookie, NO usamos contraseña. Reportamos y morimos.
            self.log(f"💀 [FAIL] Cookie caducada o inválida: {e}", 'error')
            self.log("-> Se omite esta cuenta para protegerla.", 'warn')
            return False

    def execute(self, post_url, do_like=True, do_comment=False, comment_text=None):
        try:
            # 1. Obtener Media ID (Usando API Móvil v1 para evitar errores de GQL)
            try:
                media_pk = self.client.media_pk_from_url(post_url)
                media_id = self.client.media_id(media_pk)
            except Exception as e:
                self.log(f"⚠️ No se pudo resolver el post: {e}", 'error')
                return False

            # Pausa humana táctica
            time.sleep(random.uniform(1, 2))

            # 2. LIKE
            if do_like:
                try:
                    self.client.media_like(media_id)
                    self.log(f"❤️ Like enviado por {self.account.username}", 'success')
                    time.sleep(random.uniform(1, 3))
                except Exception as e:
                    self.log(f"⚠️ Falló Like: {e}", 'warn')

            # 3. COMMENT
            if do_comment and comment_text:
                try:
                    self.client.media_comment(media_id, comment_text)
                    self.log(f"💬 Comentario enviado: '{comment_text}'", 'success')
                except Exception as e:
                    self.log(f"⚠️ Falló Comentario: {e}", 'error')
                    # Si falla comentario por SPAM, devuelve False para que no cuente como éxito
                    return False

            return True

        except Exception as e:
            self.log(f"🔥 Error Crítico en Ejecución: {e}", 'error')
            return False