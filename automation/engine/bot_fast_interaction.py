import re
import time
import random
import logging
import os
from typing import Optional, Dict, Tuple

from instagrapi import Client
from django.conf import settings

try:
    from automation.models import SystemLog
except Exception:
    SystemLog = None

logger = logging.getLogger(__name__)

DEBUG_BOT = os.getenv("BOT_DEBUG", "0") == "1"


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


def _sleep(min_s: float, max_s: float) -> None:
    time.sleep(random.uniform(min_s, max_s))


def extract_ig_username(identifier: str) -> str:
    """
    Acepta:
      - @username
      - username
      - https://www.instagram.com/username/
      - instagram.com/username?...
    Devuelve: username
    """
    t = (identifier or "").strip()
    if not t:
        return ""

    t = t.strip().lstrip("@")
    t = t.replace("https://www.instagram.com/", "instagram.com/")
    t = t.replace("http://www.instagram.com/", "instagram.com/")
    t = t.replace("https://instagram.com/", "instagram.com/")
    t = t.replace("http://instagram.com/", "instagram.com/")

    if "instagram.com/" in t:
        m = re.search(r"instagram\.com/([^/?#]+)/?", t)
        if not m:
            return ""
        return (m.group(1) or "").strip().lstrip("@")

    return t


class FastInteractionBot:
    """
    Bot de Interacción Rápida (Enjambre).
    POLÍTICA: Cookie-Only. Jamás usa contraseña.

    Este bot soporta 2 "modos" mutuamente excluyentes:

    1) POST MODE: like/comment sobre un post_url.
       - do_like / do_comment
       - requiere post_url

    2) PROFILE MODE: follow/unfollow sobre un username o profile url.
       - do_follow / do_unfollow
       - requiere target (username o url de perfil)

    Regla: NO mezclar FOLLOW con LIKE/COMMENT.
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

    def log(self, msg, level="info"):
        print(f"[{level.upper()}] {msg}")
        if SystemLog:
            try:
                SystemLog.objects.create(level=level, message=msg)
            except Exception:
                logger.debug("No se pudo registrar SystemLog.")

        # Extra debug a logger (solo si BOT_DEBUG=1)
        if DEBUG_BOT:
            getattr(logger, level if hasattr(logger, level) else "info")(msg)

    # ---------------------------
    # Auth (cookie-only)
    # ---------------------------
    def login(self) -> bool:
        self.log(f"️ Verificando identidad de {self.account.username}...", "info")

        if not getattr(self.account, "session_id", None):
            self.log(" [ABORT] Cuenta sin SessionID. Omitiendo.", "error")
            return False

        try:
            self.log("-> Inyectando SessionID...", "info")
            self.client.login_by_sessionid(self.account.session_id)
            self.log(" Sesión activa y validada.", "success")
            return True
        except Exception as e:
            self.log(f" [FAIL] Cookie caducada o inválida: {e}", "error")
            self.log("-> Se omite esta cuenta para protegerla.", "warn")
            return False

    # ---------------------------
    # Public API (runner)
    # ---------------------------
    def run(
        self,
        target: str,
        *,
        do_like: bool = False,
        do_comment: bool = False,
        comment_text: Optional[str] = None,
        do_follow: bool = False,
        do_unfollow: bool = False,
        check_friendship: bool = True,
    ) -> bool:
        """
        Punto de entrada unificado para el ejecutor de tasks.
        """
        if DEBUG_BOT:
            self.log(
                f"[DEBUG] run() account=@{getattr(self.account, 'username', '?')} "
                f"target='{target}' do_like={do_like} do_comment={do_comment} "
                f"do_follow={do_follow} do_unfollow={do_unfollow} "
                f"check_friendship={check_friendship} comment_text_len={len((comment_text or ''))}",
                "info",
            )

        # Validación combos
        post_mode = bool(do_like or do_comment)
        profile_mode = bool(do_follow or do_unfollow)

        if post_mode and profile_mode:
            self.log(" Config inválida: no mezcles FOLLOW/UNFOLLOW con LIKE/COMMENT.", "error")
            return False

        if do_follow and do_unfollow:
            self.log(" Config inválida: no puedes hacer FOLLOW y UNFOLLOW a la vez.", "error")
            return False

        if post_mode:
            if do_comment and not (comment_text or "").strip():
                self.log(" Config inválida: do_comment=True pero comment_text vacío.", "error")
                return False
            if DEBUG_BOT:
                self.log("[DEBUG] Entrando a POST MODE (execute_post)", "info")
            return self.execute_post(target, do_like=do_like, do_comment=do_comment, comment_text=comment_text)

        if profile_mode:
            if DEBUG_BOT:
                self.log("[DEBUG] Entrando a PROFILE MODE (follow/unfollow)", "info")

            username = extract_ig_username(target)

            if DEBUG_BOT:
                self.log(f"[DEBUG] extract_ig_username('{target}') => '{username}'", "info")

            if not username:
                self.log(f" No pude extraer username desde target='{target}'", "error")
                return False

            if do_follow:
                if DEBUG_BOT:
                    self.log(f"[DEBUG] Dispatch -> follow_user(@{username})", "info")
                return self.follow_user(username, check_friendship=check_friendship)

            if do_unfollow:
                if DEBUG_BOT:
                    self.log(f"[DEBUG] Dispatch -> unfollow_user(@{username})", "info")
                return self.unfollow_user(username, check_friendship=check_friendship)

        self.log(" Config inválida: no se seleccionó ninguna acción.", "error")
        return False

    # ---------------------------
    # POST MODE (like/comment)
    # ---------------------------
    def _resolve_media_id(self, post_url: str) -> Optional[str]:
        try:
            if DEBUG_BOT:
                self.log(f"[DEBUG] Resolviendo media_id desde URL: {post_url}", "info")
            media_pk = self.client.media_pk_from_url(post_url)
            media_id = self.client.media_id(media_pk)
            if DEBUG_BOT:
                self.log(f"[DEBUG] media_pk={media_pk} media_id={media_id}", "info")
            return media_id
        except Exception as e:
            self.log(f"️ No se pudo resolver el post: {e}", "error")
            return None

    def execute_post(self, post_url: str, do_like: bool = True, do_comment: bool = False, comment_text: Optional[str] = None) -> bool:
        """
        Ejecuta acciones sobre un post.
        """
        try:
            if DEBUG_BOT:
                self.log(
                    f"[DEBUG] execute_post() url='{post_url}' do_like={do_like} do_comment={do_comment} "
                    f"comment_text_len={len((comment_text or ''))}",
                    "info",
                )

            media_id = self._resolve_media_id(post_url)
            if not media_id:
                if DEBUG_BOT:
                    self.log("[DEBUG] execute_post() abort: media_id=None", "warn")
                return False

            _sleep(1.0, 2.0)

            # LIKE
            if do_like:
                try:
                    if DEBUG_BOT:
                        self.log(f"[DEBUG] media_like(media_id={media_id})", "info")
                    self.client.media_like(media_id)
                    self.log(f"️ Like enviado por {self.account.username}", "success")
                    _sleep(1.0, 3.0)
                except Exception as e:
                    self.log(f"️ Falló Like: {e}", "warn")

            # COMMENT
            if do_comment and comment_text:
                try:
                    if DEBUG_BOT:
                        self.log(f"[DEBUG] media_comment(media_id={media_id}) text='{comment_text[:50]}'...", "info")
                    self.client.media_comment(media_id, comment_text)
                    self.log(f" Comentario enviado: '{comment_text}'", "success")
                except Exception as e:
                    self.log(f"️ Falló Comentario: {e}", "error")
                    return False

            if DEBUG_BOT:
                self.log("[DEBUG] execute_post() done => True", "info")
            return True

        except Exception as e:
            self.log(f" Error Crítico en Ejecución (POST): {e}", "error")
            return False

    # ---------------------------
    # PROFILE MODE (follow/unfollow)
    # ---------------------------
    def _resolve_user_id(self, target_username: str) -> int:
        """
        Resuelve user_id (pk) evitando GQL:
        1) endpoint privado usernameinfo
        2) fallback search_users
        """
        username = (target_username or "").strip().lstrip("@")
        if not username:
            raise ValueError("target_username vacío")

        if DEBUG_BOT:
            self.log(f"[DEBUG] _resolve_user_id() username='@{username}'", "info")
            self.log(f"[DEBUG] private_request users/{username}/usernameinfo/", "info")

        # Intento 1: endpoint privado (evita GQL)
        try:
            data = self.client.private_request(f"users/{username}/usernameinfo/")
            user_id = int(data["user"]["pk"])
            if DEBUG_BOT:
                self.log(f"[DEBUG] usernameinfo OK @{username} -> user_id={user_id}", "info")
            return user_id
        except Exception as e1:
            self.log(f"️ No pude resolver user_id por usernameinfo: {e1}", "warn")

        # Intento 2: búsqueda
        if DEBUG_BOT:
            self.log(f"[DEBUG] fallback search_users('{username}', amount=10)", "info")
        try:
            results = self.client.search_users(username, amount=10)
            for u in results:
                if getattr(u, "username", "").lower() == username.lower():
                    user_id = int(getattr(u, "pk"))
                    if DEBUG_BOT:
                        self.log(f"[DEBUG] search_users match @{username} -> user_id={user_id}", "info")
                    return user_id
        except Exception as e2:
            self.log(f"️ No pude resolver user_id por search_users: {e2}", "warn")

        raise RuntimeError(f"No se pudo resolver user_id para @{username}")

    def _friendship_flags(self, user_id: int) -> Tuple[bool, bool]:
        """
        Devuelve (following, outgoing_request) en forma segura.
        """
        if DEBUG_BOT:
            self.log(f"[DEBUG] user_friendship(user_id={user_id})", "info")

        fr = self.client.user_friendship(user_id)
        if isinstance(fr, dict):
            following = bool(fr.get("following"))
            outgoing = bool(fr.get("outgoing_request"))
            if DEBUG_BOT:
                self.log(f"[DEBUG] friendship(dict) following={following} outgoing_request={outgoing}", "info")
            return following, outgoing

        following = bool(getattr(fr, "following", False))
        outgoing = bool(getattr(fr, "outgoing_request", False))
        if DEBUG_BOT:
            self.log(f"[DEBUG] friendship(obj) following={following} outgoing_request={outgoing}", "info")
        return following, outgoing

    def follow_user(self, target_username: str, check_friendship: bool = True) -> bool:
        try:
            username = (target_username or "").strip().lstrip("@")
            if not username:
                self.log(" target_username vacío", "error")
                return False

            if DEBUG_BOT:
                self.log(f"[DEBUG] follow_user() username='@{username}' check_friendship={check_friendship}", "info")

            user_id = self._resolve_user_id(username)

            _sleep(1.0, 2.0)

            if check_friendship:
                try:
                    following, outgoing = self._friendship_flags(user_id)
                    if following or outgoing:
                        self.log(f" Ya estaba siguiendo / solicitado: @{username}", "success")
                        return True
                except Exception as e:
                    self.log(f"️ No pude validar friendship: {e}", "warn")

            try:
                if DEBUG_BOT:
                    self.log(f"[DEBUG] user_follow(user_id={user_id})", "info")
                self.client.user_follow(user_id)
                self.log(f" Follow enviado a @{username} por {self.account.username}", "success")
                _sleep(1.0, 3.0)
                return True
            except Exception as e:
                self.log(f"️ Falló Follow a @{username}: {e}", "error")
                return False

        except Exception as e:
            self.log(f" Error crítico en follow_user(@{target_username}): {e}", "error")
            return False

    def unfollow_user(self, target_username: str, check_friendship: bool = True) -> bool:
        try:
            username = (target_username or "").strip().lstrip("@")
            if not username:
                self.log(" target_username vacío", "error")
                return False

            if DEBUG_BOT:
                self.log(f"[DEBUG] unfollow_user() username='@{username}' check_friendship={check_friendship}", "info")

            user_id = self._resolve_user_id(username)

            _sleep(1.0, 2.0)

            if check_friendship:
                try:
                    following, outgoing = self._friendship_flags(user_id)
                    if not following and not outgoing:
                        self.log(f" Ya no seguía a @{username}", "success")
                        return True
                except Exception as e:
                    self.log(f"️ No pude validar friendship: {e}", "warn")

            try:
                if DEBUG_BOT:
                    self.log(f"[DEBUG] user_unfollow(user_id={user_id})", "info")
                self.client.user_unfollow(user_id)
                self.log(f" Unfollow enviado a @{username} por {self.account.username}", "success")
                _sleep(1.0, 3.0)
                return True
            except Exception as e:
                self.log(f"️ Falló Unfollow a @{username}: {e}", "error")
                return False

        except Exception as e:
            self.log(f" Error crítico en unfollow_user(@{target_username}): {e}", "error")
            return False
