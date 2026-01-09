import time
import random
import logging
from typing import Optional, Dict
from instagrapi import Client
from django.conf import settings

try:
    from automation.models import SystemLog
except Exception:
    SystemLog = None

logger = logging.getLogger(__name__)


def build_proxy_url(proxy_data: Optional[Dict[str, str]]) -> Optional[str]:
    """
    Construye una URL de proxy http://user:pass@host:port
    Devuelve None si host o port están ausentes.
    """
    if not proxy_data:
        return None

    host = (proxy_data.get("host") or "").strip()
    port = proxy_data.get("port")
    user = (proxy_data.get("user") or "").strip()
    password = (proxy_data.get("password") or "").strip()

    if not host or not port:
        return None

    try:
        port_str = str(port).strip()
    except Exception:
        return None

    if not port_str:
        return None

    auth = ""
    if user:
        auth = f"{user}:{password}@" if password else f"{user}@"

    return f"http://{auth}{host}:{port_str}"


def _get_default_proxy_data() -> Optional[Dict[str, str]]:
    """
    Devuelve proxy_data desde settings si BRIGHTDATA_PROXY_ENABLED está activo.
    """
    if not getattr(settings, "BRIGHTDATA_PROXY_ENABLED", False):
        return None

    host = (getattr(settings, "BRIGHTDATA_PROXY_HOST", "") or "").strip()
    port = (getattr(settings, "BRIGHTDATA_PROXY_PORT", "") or "").strip()
    user = (getattr(settings, "BRIGHTDATA_PROXY_USER", "") or "").strip()
    password = (getattr(settings, "BRIGHTDATA_PROXY_PASSWORD", "") or "").strip()

    if not host or not port:
        return None

    return {"host": host, "port": port, "user": user, "password": password}


class FastInteractionBot:
    """
    Bot de Interacción Rápida (Enjambre).
    POLÍTICA: Cookie-Only. Jamás usa contraseña.
    """

    def __init__(self, account, proxy_data=None):
        self.account = account
        self.client = Client()
        self.proxy_data = proxy_data or _get_default_proxy_data()
        self.proxy_url = build_proxy_url(self.proxy_data)
        self.requests_proxies = (
            {"http": self.proxy_url, "https": self.proxy_url} if self.proxy_url else None
        )
        proxy_label = "none"
        if self.proxy_data:
            proxy_label = f"{self.proxy_data.get('host')}:{self.proxy_data.get('port')}"

        logger.info(
            "fast_interaction_bot_proxy account=%s proxy=%s",
            getattr(self.account, "username", "?"),
            proxy_label,
        )

        if self.proxy_url:
            try:
                if hasattr(self.client, "set_proxy"):
                    self.client.set_proxy(self.proxy_url)
                else:
                    self.client.proxy = self.proxy_url
                logger.info(
                    "instagrapi_proxy_set account=%s proxy=%s",
                    getattr(self.account, "username", "?"),
                    self.proxy_url,
                )
            except Exception as exc:
                logger.warning(
                    "instagrapi_proxy_failed account=%s proxy=%s error=%s",
                    getattr(self.account, "username", "?"),
                    self.proxy_url,
                    exc,
                )

    def log(self, msg, level='info'):
        """Escribe en la terminal y en la base de datos"""
        print(f"[{level.upper()}] {msg}")
        if SystemLog:
            try:
                SystemLog.objects.create(level=level, message=msg)
            except Exception:
                logger.debug("No se pudo registrar SystemLog; modelo no disponible o error en DB.")

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
        
    #FOLLOW METHODS


    def _resolve_user_id(self, target_username: str) -> int:
        """
        Resuelve el user_id (pk) evitando GQL.
        1) endpoint privado usernameinfo (más estable en instagrapi)
        2) fallback: search_users
        """
        username = (target_username or "").strip().lstrip("@")
        if not username:
            raise ValueError("target_username vacío")

        # Intento 1: endpoint privado (evita GQL)
        try:
            data = self.client.private_request(f"users/{username}/usernameinfo/")
            return int(data["user"]["pk"])
        except Exception as e1:
            self.log(f"⚠️ No pude resolver user_id por usernameinfo: {e1}", "warn")

        # Intento 2: búsqueda (también usa endpoints privados)
        try:
            results = self.client.search_users(username, amount=10)
            for u in results:
                if getattr(u, "username", "").lower() == username.lower():
                    return int(getattr(u, "pk"))
        except Exception as e2:
            self.log(f"⚠️ No pude resolver user_id por search_users: {e2}", "warn")

        raise RuntimeError(f"No se pudo resolver user_id para @{username}")

    def follow_user(self, target_username: str, check_friendship: bool = True) -> bool:
        try:
            username = (target_username or "").strip().lstrip("@")
            if not username:
                self.log("❌ target_username vacío", "error")
                return False

            # Resuelve user_id sin GQL
            user_id = self._resolve_user_id(username)

            # Pausa humana pequeña
            time.sleep(random.uniform(1.0, 2.0))

            # (Opcional) evitar follow duplicado
            if check_friendship:
                try:
                    fr = self.client.user_friendship(user_id)
                    if fr.get("following") or fr.get("outgoing_request"):
                        self.log(f"✅ Ya estaba siguiendo / solicitado: @{username}", "success")
                        return True
                except Exception as e:
                    self.log(f"⚠️ No pude validar friendship: {e}", "warn")

            # Ejecuta follow
            try:
                self.client.user_follow(user_id)
                self.log(f"➕ Follow enviado a @{username} por {self.account.username}", "success")
                time.sleep(random.uniform(1.0, 3.0))
                return True
            except Exception as e:
                self.log(f"⚠️ Falló Follow a @{username}: {e}", "error")
                return False

        except Exception as e:
            self.log(f"🔥 Error crítico en follow_user(@{target_username}): {e}", "error")
            return False    
        
    #UNFOLLOW METHODS

    def unfollow_user(self, target_username: str, check_friendship: bool = True) -> bool:
        try:
            username = (target_username or "").strip().lstrip("@")
            if not username:
                self.log("❌ target_username vacío", "error")
                return False

            # Resuelve user_id sin GQL
            user_id = self._resolve_user_id(username)

            # Pausa humana pequeña
            time.sleep(random.uniform(1.0, 2.0))

            # (Opcional) evitar unfollow duplicado
            if check_friendship:
                try:
                    fr = self.client.user_friendship(user_id)
                    if not fr.get("following"):
                        self.log(f"✅ Ya no seguía a @{username}", "success")
                        return True
                except Exception as e:
                    self.log(f"⚠️ No pude validar friendship: {e}", "warn")

            # Ejecuta unfollow
            try:
                self.client.user_unfollow(user_id)
                self.log(f"➖ Unfollow enviado a @{username} por {self.account.username}", "success")
                time.sleep(random.uniform(1.0, 3.0))
                return True
            except Exception as e:
                self.log(f"⚠️ Falló Unfollow a @{username}: {e}", "error")
                return False

        except Exception as e:
            self.log(f"🔥 Error crítico en unfollow_user(@{target_username}): {e}", "error")
            return False
    
   