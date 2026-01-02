import time
import re
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import StaleElementReferenceException, TimeoutException

# Importamos la infraestructura Django
from .engine_base import BotEngine
from automation.models import Lead

class ScraperBot(BotEngine):
    """
    Motor de Scraping portado EXACTAMENTE desde proxy_selenium.py
    """

    # --- CONFIGURACIÓN DE NICHOS (Copiada de tu archivo) ---
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
        # Filtros por defecto alineados con tu script
        self.filters = filters if filters else {
            "followers_min": 1000,
            "followers_max": 100000,
            "posts_min": 15, # Tu script dice 100, aquí dejamos configurable
            "engagement_max": 3.0
        }
        super().__init__(account_data=account_data, proxy_data=proxy_data)

    # ==============================================================================
    # 1. PARSERS Y UTILIDADES (Lógica exacta de proxy_selenium.py)
    # ==============================================================================

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
        except: return 0

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
                    if "seguido" not in text.lower():
                        category = text
                        break
        except: pass
        return category

    def _calculate_real_engagement(self, followers):
        """
        Retorna float con el % o string 'Comentarios Ocultos'.
        Lógica exacta de tu script.
        """
        try:
            try:
                WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/p/')]")))
            except: return 0.0

            posts_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
            if len(posts_links) < 4: return 0.0 

            # 4to Post
            target_link = posts_links[3]
            self.driver.execute_script("arguments[0].click();", target_link)
            
            content_text = ""
            try:
                wait = WebDriverWait(self.driver, 5)
                # Selectores ampliados para robustez
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
            
            match_std = re.search(r'([\d.,kkm]+)\s*(?:likes|me gusta|j’aime)', content_text)
            match_hidden_partial = re.search(r'(?:y|and)\s+([\d.,kkm]+)\s+(?:personas|others)', content_text)

            if match_std:
                likes = self._parse_social_number(match_std.group(1))
            elif match_hidden_partial:
                likes = self._parse_social_number(match_hidden_partial.group(1))

            c_match = re.search(r'([\d.,kkm]+)\s*(?:comments|comentarios)', content_text)
            if c_match: 
                comments = self._parse_social_number(c_match.group(1))

            # --- LÓGICA CRÍTICA: COMENTARIOS OCULTOS ---
            if likes == 0 and ("otras personas" in content_text or "others" in content_text):
                return "Comentarios Ocultos"
            
            total = likes + comments
            if followers == 0: return 0.0
            
            engagement_rate = (total / followers) * 100
            return round(engagement_rate, 2)

        except:
            try: ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
            except: pass
            return 0.0

    def _analyze_profile_visual(self, current_username):
        """
        Analiza el perfil y decide si guardarlo.
        """
        try:
            wait = WebDriverWait(self.driver, 4) 
            if "accounts/login" in self.driver.current_url: 
                print(f"[ERROR] Redirigido a Login: @{current_username}")
                return None
            
            try:
                meta_element = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']")))
                meta_content = meta_element.get_attribute("content").lower()
            except: 
                print(f"[DESCARTE] @{current_username} (No meta tag)")
                return None

            followers = 0
            posts = 0
            f_match = re.search(r'([0-9\.,km]+)\s*(followers|seguidores)', meta_content)
            p_match = re.search(r'([0-9\.,km]+)\s*(posts|publicaciones)', meta_content)

            if f_match: followers = self._parse_social_number(f_match.group(1))
            if p_match: posts = self._parse_social_number(p_match.group(1))

            # Filtros dinámicos o hardcodeados (como prefieras, aquí uso los del init)
            min_f = self.filters.get('followers_min', 1000)
            max_f = self.filters.get('followers_max', 100000)
            min_p = self.filters.get('posts_min', 10) # Bajé un poco el hard limit para pruebas
            max_eng = self.filters.get('engagement_max', 3.0)

            if not (min_f <= followers <= max_f):
                print(f"[DESCARTE] @{current_username} | F:{followers}")
                return None
            
            if posts < min_p:
                print(f"[DESCARTE] @{current_username} | Posts:{posts}")
                return None
                
            engagement = self._calculate_real_engagement(followers)
            category = self._extract_category()
            niche = self._get_niche_match(meta_content)
            
            # --- DECISIÓN FINAL ---
            
            # 1. Comentarios Ocultos -> SIEMPRE VÁLIDO (Tu lógica)
            if isinstance(engagement, str):
                print(f"   [OK - OCULTO] @{current_username}")
                return {
                    "followers": followers, "posts": posts, "category": category, 
                    "niche": niche, "engagement": engagement, "url": self.driver.current_url
                }

            # 2. Numérico -> Verificar Máximo Engagement (Tu script descarta si es muy alto)
            if isinstance(engagement, (int, float)):
                if engagement >= max_eng:
                    print(f"   [DESCARTE] High Eng: {engagement}%")
                    return None

                print(f"   [OK] @{current_username} | Eng:{engagement}%")
                return {
                    "followers": followers, "posts": posts, "category": category, 
                    "niche": niche, "engagement": engagement, "url": self.driver.current_url
                }

            return None

        except Exception as e:
            print(f"[Error Análisis] {e}")
            return None

    # ==============================================================================
    # 2. BUCLE PRINCIPAL (Adaptado de run_scraper_session)
    # ==============================================================================
    def run_scraping_task(self, target_profile, max_leads=50):
        print(f"--- Iniciando Scraping V5 (Lógica Escritorio) en @{target_profile} ---")
        
        self.driver.get(f"https://www.instagram.com/{target_profile}/")
        time.sleep(3)
        self.dismiss_popups()

        # Abrir lista de seguidos
        try:
            following_link = WebDriverWait(self.driver, 5).until(
                EC.element_to_be_clickable((By.XPATH, f"//a[contains(@href, 'following')]"))
            )
            following_link.click()
            time.sleep(2)
        except:
            print("Lista de seguidores no disponible/privada.")
            return

        leads_saved = 0
        consecutive_fails = 0
        analyzed_cache = set()
        
        try:
            dialog_box = WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, "//div[@role='dialog']")))
        except:
            print("No se encontró el diálogo de seguidores.")
            return

        main_window = self.driver.current_window_handle
        MAX_SCROLL_FAILS = 15

        while leads_saved < max_leads:
            # 1. Recolectar candidatos (Solo Strings, para evitar StaleElements)
            try:
                elements = dialog_box.find_elements(By.TAG_NAME, "a")
            except: break
            
            new_candidates = []
            last_element_found = None

            for elem in elements:
                try:
                    last_element_found = elem
                    href = elem.get_attribute('href')
                    if not href or 'instagram.com/' not in href: continue
                    
                    # Limpieza estricta como en tu script
                    clean_href = href.split('?')[0].rstrip('/')
                    user = clean_href.split('/')[-1]
                    
                    if len(user) < 3: continue
                    if any(x in clean_href for x in ['/p/', '/explore/', '/direct/', target_profile]): continue
                    
                    if user not in analyzed_cache:
                        # Verificar si ya existe en DB para no analizarlo en vano
                        if not Lead.objects.filter(ig_username=user).exists():
                            new_candidates.append(user)
                        analyzed_cache.add(user) 
                except: pass
            
            # 2. Si no hay candidatos nuevos, SCROLL
            if not new_candidates:
                consecutive_fails += 1
                if consecutive_fails >= MAX_SCROLL_FAILS:
                    print("Fin de lista o límite de scrolls.")
                    break
                
                if last_element_found:
                    try: self.driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                    except: pass
                time.sleep(1.5)
                continue

            consecutive_fails = 0
            
            # 3. Procesar candidatos (Abrir Pestaña -> Analizar -> Cerrar)
            for user in new_candidates:
                try:
                    # Abrir nueva pestaña (Método Robusto)
                    self.driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(self.driver, 3).until(lambda d: len(d.window_handles) > 1)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
                    self.driver.get(f"https://www.instagram.com/{user}/")
                    
                    data = self._analyze_profile_visual(current_username=user)
                    
                    # Cerrar pestaña
                    try: self.driver.close()
                    except: pass
                    
                    # Volver a main
                    self.driver.switch_to.window(main_window)
                    
                    if data:
                        Lead.objects.create(
                            ig_username=user,
                            source_account=target_profile,
                            data=data,
                            status='to_contact'
                        )
                        leads_saved += 1
                        print(f"   [DB GUARDADO] Leads: {leads_saved}/{max_leads}")

                    if leads_saved >= max_leads: break
                    time.sleep(random.uniform(1, 2))

                except Exception as e:
                    print(f"Error ciclo usuario {user}: {e}")
                    # Recuperación de emergencia
                    try:
                        while len(self.driver.window_handles) > 1:
                            self.driver.switch_to.window(self.driver.window_handles[-1])
                            self.driver.close()
                        self.driver.switch_to.window(main_window)
                    except: pass

            if last_element_found:
                try: self.driver.execute_script("arguments[0].scrollIntoView(true);", last_element_found)
                except: pass
            
            time.sleep(1)

        print(f"--- Tarea Finalizada. Total Leads: {leads_saved} ---")