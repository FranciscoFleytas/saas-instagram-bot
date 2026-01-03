import time
import random
import logging
from instagrapi import Client
from automation.models import Lead, IGAccount

logger = logging.getLogger(__name__)

class FastScraperBot:
    """
    Versión ESTRICTA (Cookie-Only + API Móvil v1).
    - Evita endpoints Web/GQL que causan bloqueos (KeyError: data).
    - Usa solo endpoints nativos de la APP (v1).
    """

    NICHE_MAPPING = {
        "Salud & Medicina": ["medico", "doctor", "cirujano", "dentist", "nutricionista", "wellness", "salud"],
        "Real Estate": ["real estate", "bienes raices", "realtor", "arquitecto", "broker", "inmobiliaria"],
        "Negocios": ["ceo", "founder", "fundador", "entrepreneur", "consultant", "director", "dueño"],
        "Marketing": ["marketing", "ventas", "closer", "copywriter", "seo", "agency", "agencia"],
        "Coach": ["coach", "mentor", "trainer", "entrenador", "mindset"]
    }

    def __init__(self, account_data: IGAccount, proxy_data: dict = None):
        self.account = account_data
        self.client = Client()
        
        # Configuración de Proxy
        if proxy_data:
            proxy_url = f"http://{proxy_data['user']}:{proxy_data['pass']}@{proxy_data['host']}:{proxy_data['port']}"
            self.client.set_proxy(proxy_url)

        # Filtros
        self.MIN_FOLLOWERS = 100
        self.MAX_FOLLOWERS = 500000
        self.MIN_POSTS = 10
        self.MAX_ENGAGEMENT = 15.0 

    def login(self):
        print(f"[FAST SCRAPER] 🛡️ Verificando sesión para {self.account.username}...")
        
        if not self.account.session_id:
            print(f"   [ABORT] ❌ No hay SessionID configurado. Saltando cuenta por seguridad.")
            return False

        try:
            # Login EXCLUSIVO por Cookie
            print("   -> Inyectando SessionID...")
            self.client.login_by_sessionid(self.account.session_id)
            print("   [OK] Sesión restaurada exitosamente.")
            return True
        except Exception as e:
            print(f"   [FAIL] ❌ La Cookie ha expirado o es inválida: {e}")
            return False

    def _calculate_engagement(self, user_id, followers):
        try:
            # Usar user_medias_v1 para evitar GQL
            medias = self.client.user_medias_v1(user_id, amount=3)
            if not medias: return 0.0

            total_interactions = sum(m.like_count + m.comment_count for m in medias)
            avg = total_interactions / len(medias)
            
            if followers == 0: return 0.0
            return round((avg / followers) * 100, 2)
        except:
            return 0.0

    def _check_niche(self, bio_text):
        if not bio_text: return "-"
        bio_lower = bio_text.lower()
        for niche, keywords in self.NICHE_MAPPING.items():
            for kw in keywords:
                if kw in bio_lower:
                    return niche
        return "-"

    def run(self, target_username, max_leads=50):
        print(f"--- ⚡ API Scraping (Mobile Mode): @{target_username} ---")
        
        try:
            # 1. RESOLUCIÓN DE USUARIO (SOLO V1 - MÓVIL)
            print(f"   Resolviendo ID de @{target_username}...")
            try:
                # user_info_by_username_v1 fuerza el uso de la API nativa
                # Si falla, usamos search_users como respaldo último
                try:
                    target_info = self.client.user_info_by_username_v1(target_username)
                    target_id = target_info.pk
                except Exception:
                    print("   [INFO] Método directo falló, probando búsqueda...")
                    results = self.client.search_users(target_username)
                    if not results: raise Exception("Usuario no encontrado en búsqueda.")
                    target_id = results[0].pk
                    
            except Exception as e:
                raise Exception(f"Fallo crítico resolviendo usuario (API Web bloqueada): {e}")

            # 2. EXTRACCIÓN (SOLO V1 - MÓVIL)
            amount_to_fetch = max_leads * 2
            print(f"   Descargando {amount_to_fetch} seguidores (API v1)...")
            
            # user_followers_v1 devuelve LISTA, no diccionario. Es más estable.
            candidates = self.client.user_followers_v1(target_id, amount=amount_to_fetch)
            
            print(f"   Analizando {len(candidates)} candidatos...")
            leads_saved = 0
            
            for user_short in candidates:
                if leads_saved >= max_leads: break
                
                # Pausa humana aleatoria
                time.sleep(random.uniform(2.0, 4.0))

                try:
                    # Usar user_info_v1 (API Móvil) en vez de user_info (Híbrido/Web)
                    info = self.client.user_info_v1(user_short.pk)
                    
                    # Filtros
                    if info.is_private: continue
                    if not (self.MIN_FOLLOWERS <= info.follower_count <= self.MAX_FOLLOWERS): continue
                    
                    niche = self._check_niche(info.biography)
                    eng_rate = self._calculate_engagement(info.pk, info.follower_count)
                    
                    print(f"   [MATCH] @{info.username} | Nicho: {niche} | Eng: {eng_rate}%")
                    
                    if not Lead.objects.filter(ig_username=info.username).exists():
                        Lead.objects.create(
                            ig_username=info.username,
                            source_account=target_username,
                            full_name=info.full_name,
                            data={
                                "followers": info.follower_count,
                                "niche": niche,
                                "engagement": eng_rate,
                                "bio": info.biography
                            },
                            status='to_contact'
                        )
                        leads_saved += 1
                    else:
                        print(f"   [DUPLICADO] {info.username}")

                except Exception as e:
                    print(f"   [SKIP] Error analizando perfil: {e}")
                    continue

            return f"SUCCESS: {leads_saved} leads extracted"

        except Exception as e:
            return f"CRITICAL ERROR: {str(e)}"