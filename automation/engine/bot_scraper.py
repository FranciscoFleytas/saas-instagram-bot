import time
import re
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Importamos la Clase Madre e infraestructura
from .engine_base import BotEngine
from automation.models import Lead

class ScraperBot(BotEngine):
    """
    Motor de Scraping basado en la lógica de 'proxy_selenium.py'
    adaptado a la arquitectura de clases de Django.
    """

    # --- CONFIGURACIÓN DE NICHOS (INTACTA) ---
    NICHE_MAPPING = {
        "Salud & Medicina": ["medico", "doctor", "medic", "surgeon", "cirujano", "dermatologist", "dentist", "dentista", "nutritionist", "nutricionista", "wellness", "bienestar", "mental health", "pediatrician"],
        "Real Estate & Arquitectura": ["real estate", "bienes raices", "realtor", "architect", "arquitecto", "interior design", "property", "broker", "construction"],
        "Negocios & Emprendimiento": ["ceo", "founder", "fundador", "business owner", "entrepreneur", "emprendedor", "consultant", "startup", "director", "manager", "leader"],
        "Marketing & Ventas": ["marketing", "marketer", "sales", "ventas", "closer", "copywriter", "seo", "media buyer", "social media manager", "digital marketing", "ads"],
        "Finanzas & Inversiones": ["investor", "inversor", "trader", "crypto", "financial advisor", "finance", "finanzas", "accountant", "wealth", "bitcoin", "economist"],
        "Educación & Coaching": ["coach", "mentor", "teacher", "profesor", "educator", "trainer", "academy", "speaker", "author"],
        "Creadores & Influencers": ["influencer", "creator", "creador", "podcast", "ugc", "blogger", "youtuber", "content"],
        "Moda & Belleza": ["model", "modelo", "fashion", "moda", "stylist", "makeup", "beauty", "skincare", "salon", "clothing"],
        "Arte & Creatividad": ["photographer", "fotografo", "videographer", "filmmaker", "designer", "artist", "writer", "producer", "music"],
        "Tecnología & Software": ["tech", "saas", "software", "developer", "cto", "engineer", "ingeniero", "ai", "programmer"],
        "Lifestyle, Fitness & Food": ["fitness", "gym", "trainer", "yoga", "chef", "foodie", "travel", "luxury", "lifestyle"]
    }

    def __init__(self, account_data, proxy_data=None, filters=None):
        self.username_input = account_data.username
        try:
            self.password_input = account_data.get_password()
        except Exception as e:
            print(f"Advertencia: No se pudo desencriptar password: {e}")
            self.password_input = None

        # Configuración por defecto si no vienen filtros (Lógica solicitada)
        self.filters = filters if filters else {
            "followers_min": 1000,
            "followers_max": 100000,
            "engagement_min": 0.0,
            "engagement_max": 3.0,
            "posts_min": 15,
            "target_niche": [] # Lista vacía = cualquiera
        }
        
        print(f"[{self.username_input}] Filtros activos: {self.filters}")

        super().__init__(account_data=account_data, proxy_data=proxy_data)

    # --- FUNCIONES DE PARSEO (Idénticas a proxy_selenium.py) ---

    def _parse_social_number(self, text):
        if not text: return 0
        text = str(text).lower().replace(',', '')
        try:
            if 'k' in text:
                return int(float(text.replace('k', '')) * 1000)
            elif 'm' in text:
                return int(float(text.replace('m', '')) * 1000000)
            else:
                clean_num = re.sub(r'[^\d.]', '', text)
                return int(float(clean_num))
        except:
            return 0

    def _get_niche_match(self, description_text):
        if not description_text: return "-"
        desc_lower = description_text.lower()
        for niche_name, keywords in self.NICHE_MAPPING.items():
            for kw in keywords:
                if kw.lower() in desc_lower:
                    return niche_name 
        return "-"

    def _extract_category(self):
        category = "-"
        try:
            elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'x7a106z')]")
            for el in elements:
                text = el.text.strip()
                if text and len(text) < 40 and not any(char.isdigit() for char in text):
                    if "seguido" not in text.lower() and "followed" not in text.lower():
                        category = text
                        break
        except: pass
        return category

    def _calculate_real_engagement(self, followers):
        """
        Lógica exacta de proxy_selenium.py
        """
        try:
            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/p/')]")))
            except: return 0.0

            posts_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
            if len(posts_links) < 4: return 0.0 

            # 4to Post (Estrategia para evitar posts fijados)
            target_link = posts_links[3]
            self.driver.execute_script("arguments[0].click();", target_link)
            
            content_text = ""
            try:
                wait = WebDriverWait(self.driver, 5)
                # Selectores ampliados para el modal
                modal_element = wait.until(EC.presence_of_element_located(
                    (By.XPATH, "//div[contains(@class, '_ae2s')] | //ul[contains(@class, '_a9ym')] | //div[@role='dialog']")
                ))
                content_text = modal_element.get_attribute("innerText").lower()
            except:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                return 0.0

            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            
            likes = 0
            comments = 0
            
            # Regex robusto (Inglés/Español/Francés)
            match_std = re.search(r'([\d.,kkm]+)\s*(?:likes|me gusta|j’aime)', content_text)
            match_hidden_partial = re.search(r'(?:y|and)\s+([\d.,kkm]+)\s+(?:personas|others)', content_text)

            if match_std:
                likes = self._parse_social_number(match_std.group(1))
            elif match_hidden_partial:
                likes = self._parse_social_number(match_hidden_partial.group(1))

            c_match = re.search(r'([\d.,kkm]+)\s*(?:comments|comentarios)', content_text)
            if c_match: 
                comments = self._parse_social_number(c_match.group(1))

            # --- LÓGICA DE COMENTARIOS OCULTOS ---
            if likes == 0 and ("otras personas" in content_text or "others" in content_text):
                return "Comentarios Ocultos"
            
            total = likes + comments
            if followers == 0: return 0.0
            
            engagement_rate = (total / followers) * 100
            return round(engagement_rate, 2)

        except Exception as e:
            # Asegurar escape si falla
            try: ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            except: pass
            return 0.0

    def _analyze_profile_visual(self, current_username):
        """
        Implementación de analyze_profile_visual de proxy_selenium.py
        AHORA CON VARIABLES DINÁMICAS.
        """
        try:
            wait = WebDriverWait(self.driver, 4) 
            if "accounts/login" in self.driver.current_url: 
                print(f"[ERROR] Redirigido a Login: @{current_username}")
                return None
            
            # 1. Estrategia Meta Tag (La más fiable según tu script)
            try:
                meta_element = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']")))
                meta_content = meta_element.get_attribute("content").lower()
            except: 
                print(f"[Lead Descartado] @{current_username} | No meta tag")
                return None

            followers = 0
            posts = 0
            
            f_match = re.search(r'([0-9\.,km]+)\s*(followers|seguidores)', meta_content)
            p_match = re.search(r'([0-9\.,km]+)\s*(posts|publicaciones)', meta_content)

            if f_match: followers = self._parse_social_number(f_match.group(1))
            if p_match: posts = self._parse_social_number(p_match.group(1))

            # --- VARIABLES DINÁMICAS DESDE self.filters ---
            min_f = self.filters.get('followers_min', 1000)
            max_f = self.filters.get('followers_max', 100000)
            min_p = self.filters.get('posts_min', 15)
            target_niches = self.filters.get('target_niche', [])
            
            # --- Filtros Dinámicos ---
            
            # 1. Seguidores
            if not (min_f <= followers <= max_f): 
                print(f"[Lead Descartado] @{current_username} | Followers: {followers} (Requerido: {min_f}-{max_f})")
                return None
            
            # 2. Posts
            if posts < min_p: 
                print(f"[Lead Descartado] @{current_username} | Posts: {posts} (Requerido: {min_p})")
                return None
            
            niche = self._get_niche_match(meta_content)
            
            # 3. Nicho (Si el cliente especificó alguno)
            if target_niches and isinstance(target_niches, list):
                if niche not in target_niches:
                    print(f"[Lead Descartado] @{current_username} | Nicho: {niche} (No coincide con {target_niches})")
                    return None

            # --- Cálculo Engagement ---
            engagement = self._calculate_real_engagement(followers)
            category = self._extract_category()
            
            # --- Log y Decisión Dinámica ---
            
            min_eng = self.filters.get('engagement_min', 0.0)
            max_eng = self.filters.get('engagement_max', 3.0)

            # Caso "Oculto" -> Es válido (generalmente se asume bajo/malo o oculto por privacidad)
            if isinstance(engagement, str):
                print(f"   [OK - OCULTO] @{current_username} | F:{followers} | Eng:{engagement}")
                return {
                    "followers": followers, "posts": posts, "category": category, 
                    "niche": niche, "engagement": engagement, "url": self.driver.current_url
                }

            # Caso Numérico
            if isinstance(engagement, (int, float)):
                print(f"   [INFO] @{current_username} | F:{followers} | Eng:{engagement}%")
                
                # Verificación Dinámica del Rango
                if min_eng <= engagement <= max_eng:
                    return {
                        "followers": followers, "posts": posts, "category": category, 
                        "niche": niche, "engagement": engagement, "url": self.driver.current_url
                    }
                else:
                    print(f"   [FILTRO ENGAGEMENT] {engagement}% fuera de rango ({min_eng}-{max_eng}%)")
                    return None

            return None

        except Exception as e:
            print(f"[Error Análisis] {e}")
            return None

    # --- LOOP PRINCIPAL (Idéntico al funcional) ---
    def run_scraping_task(self, target_profile, max_leads=50):
        print(f"--- Iniciando Scraping (Modo proxy_selenium) en @{target_profile} ---")
        
        self.driver.get(f"https://www.instagram.com/{target_profile}/")
        time.sleep(3)
        self.dismiss_popups()

        try:
            self.driver.find_element(By.XPATH, f"//a[contains(@href, 'following')]").click()
            time.sleep(2)
        except:
            print("Lista de seguidores no disponible/privada.")
            return

        dialog_box = self.driver.find_element(By.XPATH, "//div[@role='dialog']//div[@style]")
        leads_saved = 0
        consecutive_fails = 0
        analyzed_cache = set()

        while leads_saved < max_leads:
            users_elements = dialog_box.find_elements(By.TAG_NAME, "a")
            
            new_candidates = []
            for el in users_elements:
                href = el.get_attribute('href')
                if href and '/p/' not in href:
                    u = href.split('/')[-2]
                    if u not in analyzed_cache:
                        new_candidates.append(u)
                        analyzed_cache.add(u)

            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails > 10: break
                try: self.driver.execute_script("arguments[0].scrollIntoView(true);", users_elements[-1])
                except: pass
                time.sleep(1.5)
                continue

            consecutive_fails = 0
            main_window = self.driver.current_window_handle

            for user in new_candidates:
                if Lead.objects.filter(ig_username=user).exists():
                    continue

                try:
                    self.driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(self.driver, 3).until(lambda d: len(d.window_handles) > 1)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
                    self.driver.get(f"https://www.instagram.com/{user}/")
                    
                    # Llamamos a la lógica importada (ahora dinámica)
                    data = self._analyze_profile_visual(current_username=user)
                    
                    if data:
                        Lead.objects.create(
                            ig_username=user,
                            source_account=target_profile,
                            data=data,
                            status='to_contact'
                        )
                        leads_saved += 1
                        print(f"   [GUARDADO] @{user} en Base de Datos.")
                    
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
                    
                    if leads_saved >= max_leads: break
                    time.sleep(random.uniform(1, 2))

                except Exception as e:
                    print(f"Error ciclo: {e}")
                    try:
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(main_window)
                    except: pass