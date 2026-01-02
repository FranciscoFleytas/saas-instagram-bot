import time
import random
import logging
from instagrapi import Client
from automation.models import Lead

logger = logging.getLogger(__name__)

class FastScraperBot:
    """
    Versión optimizada de 'proxy_selenium.py' usando API Privada.
    Velocidad estimada: 10x más rápido que Selenium.
    """

    # Copiamos tus filtros exactos de proxy_selenium.py
    NICHE_MAPPING = {
        "Salud & Medicina": ["medico", "doctor", "cirujano", "dentist", "nutricionista", "wellness"],
        "Real Estate": ["real estate", "bienes raices", "realtor", "arquitecto", "broker"],
        "Negocios": ["ceo", "founder", "fundador", "entrepreneur", "consultant", "director"],
        "Marketing": ["marketing", "ventas", "closer", "copywriter", "seo", "agency"],
        # ... (puedes agregar el resto de tu lista aquí)
    }

    def __init__(self, account_data, proxy_data=None):
        self.account = account_data
        self.client = Client()
        
        # Configuración de Proxy
        if proxy_data:
            proxy_url = f"http://{proxy_data.username}:{proxy_data.password}@{proxy_data.ip_address}:{proxy_data.port}"
            self.client.set_proxy(proxy_url)

        # Filtros (Los mismos de tu script)
        self.MIN_FOLLOWERS = 1000
        self.MAX_FOLLOWERS = 100000
        self.MIN_POSTS = 50 # Bajamos un poco para ser flexibles
        self.MAX_ENGAGEMENT = 3.0

    def login(self):
        print(f"[FAST SCRAPER] Logueando {self.account.username}...")
        try:
            # Intentamos login con password
            self.client.login(self.account.username, self.account.get_password())
            return True
        except Exception as e:
            print(f"Error Login: {e}")
            return False

    def _calculate_engagement(self, user_id, followers):
        """Reemplaza la lógica visual de leer likes con regex"""
        try:
            # Traemos los últimos 4 posts (sin cargar imágenes)
            medias = self.client.user_medias(user_id, amount=4)
            if not medias: return 0.0

            total_interactions = 0
            for m in medias:
                total_interactions += m.like_count + m.comment_count
            
            # Promedio por post
            avg_interactions = total_interactions / len(medias)
            
            if followers == 0: return 0.0
            
            # Rate = (Interacciones Promedio / Seguidores) * 100
            rate = (avg_interactions / followers) * 100
            return round(rate, 2)
        except:
            return 0.0

    def _check_niche(self, bio_text):
        """Tu lógica de NICHE_MAPPING portada"""
        if not bio_text: return "-"
        bio_lower = bio_text.lower()
        for niche, keywords in self.NICHE_MAPPING.items():
            for kw in keywords:
                if kw in bio_lower:
                    return niche
        return "-"

    def run(self, target_username, max_leads=50):
        print(f"--- Iniciando Extracción Rápida en @{target_username} ---")
        
        try:
            # 1. Obtener ID del objetivo
            target_id = self.client.user_id_from_username(target_username)
            
            # 2. Obtener lista de seguidores (Instagrapi paginará solo)
            # Pedimos el doble de lo necesario porque muchos se filtrarán
            candidates = self.client.user_followers(target_id, amount=max_leads * 3)
            
            print(f"   Candidatos obtenidos: {len(candidates)} (Analizando...)")
            
            leads_saved = 0
            
            # 3. Análisis Rápido (Sin abrir pestañas)
            for user_short in candidates.values():
                if leads_saved >= max_leads: break

                # Pausa de seguridad (Clave para no ser baneado en modo API)
                time.sleep(random.uniform(2, 4)) 

                try:
                    # Obtenemos info completa del usuario (1 petición API vs Cargar toda la web)
                    info = self.client.user_info(user_short.pk)
                    
                    # A. Filtros Básicos
                    if info.is_private: continue
                    if not (self.MIN_FOLLOWERS <= info.follower_count <= self.MAX_FOLLOWERS): continue
                    if info.media_count < self.MIN_POSTS: continue

                    # B. Filtro de Nicho (Keyword en Bio)
                    niche = self._check_niche(info.biography)
                    if niche == "-": continue # Si no es del nicho, descarta

                    # C. Filtro de Engagement
                    eng_rate = self._calculate_engagement(info.pk, info.follower_count)
                    if eng_rate > self.MAX_ENGAGEMENT: continue # Demasiado famoso/viral

                    # D. Guardar Lead
                    print(f"   [MATCH] @{info.username} | Nicho: {niche} | Eng: {eng_rate}%")
                    
                    Lead.objects.create(
                        ig_username=info.username,
                        source_account=target_username,
                        data={
                            "followers": info.follower_count,
                            "niche": niche,
                            "engagement": eng_rate,
                            "bio": info.biography
                        },
                        status='to_contact'
                    )
                    leads_saved += 1

                except Exception as e:
                    print(f"   Error analizando {user_short.username}: {e}")
                    time.sleep(10) # Pausa larga si hay error

            return f"SUCCESS: {leads_saved} leads extracted"

        except Exception as e:
            return f"CRITICAL ERROR: {str(e)}"