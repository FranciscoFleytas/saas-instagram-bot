import time
import re
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# Importamos la Clase Madre
from .engine_base import BotEngine
# Importamos el Modelo de Django para guardar los leads
from automation.models import Lead

class ScraperBot(BotEngine):
    """
    Motor de Scraping: Hereda la capacidad de navegar de BotEngine
    e implementa la lógica de análisis de perfiles de proxy_selenium.py
    """

    NICHE_MAPPING = {
        "Salud": ["medico", "doctor", "surgeon", "dentist", "nutritionist", "wellness"],
        "Real Estate": ["real estate", "realtor", "architect", "property", "broker"],
        "Negocios": ["ceo", "founder", "owner", "entrepreneur", "startup"],
        "Marketing": ["marketing", "sales", "seo", "media buyer", "ads"],
        "Tech": ["tech", "software", "developer", "engineer", "ai", "saas"]
    }

    # --- UTILIDADES DE PARSEO (Tu lógica original) ---
    def _parse_social_number(self, text):
        if not text: return 0
        text = str(text).lower().replace(',', '')
        try:
            if 'k' in text: return int(float(text.replace('k', '')) * 1000)
            elif 'm' in text: return int(float(text.replace('m', '')) * 1000000)
            else: return int(float(re.sub(r'[^\d.]', '', text)))
        except: return 0

    def _get_niche_match(self, description_text):
        if not description_text: return "-"
        desc_lower = description_text.lower()
        for niche_name, keywords in self.NICHE_MAPPING.items():
            for kw in keywords:
                if kw.lower() in desc_lower: return niche_name
        return "-"

    def _extract_category(self):
        category = "-"
        try:
            elements = self.driver.find_elements(By.XPATH, "//div[contains(@class, 'x7a106z')]")
            for el in elements:
                text = el.text.strip()
                if text and len(text) < 40 and not any(char.isdigit() for char in text):
                    if "followed" not in text.lower():
                        category = text
                        break
        except: pass
        return category

    def _calculate_real_engagement(self, followers):
        """Tu lógica exacta de cálculo de engagement + detección de ocultos"""
        try:
            posts_links = self.driver.find_elements(By.XPATH, "//a[contains(@href, '/p/')]")
            if len(posts_links) < 4: return 0.0

            # Analizamos el 4to post
            target_link = posts_links[3]
            self.driver.execute_script("arguments[0].click();", target_link)
            
            wait = WebDriverWait(self.driver, 5)
            try:
                modal = wait.until(EC.presence_of_element_located((By.XPATH, "//div[contains(@class, '_ae2s')] | //ul[contains(@class, '_a9ym')]")))
                content_text = modal.get_attribute("innerText").lower()
            except:
                ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()
                return 0.0

            ActionChains(self.driver).send_keys(Keys.ESCAPE).perform()

            # Regex parsing
            likes = 0
            comments = 0
            
            match_std = re.search(r'([\d.,kkm]+)\s*(?:likes|me gusta)', content_text)
            if match_std: likes = self._parse_social_number(match_std.group(1))

            c_match = re.search(r'([\d.,kkm]+)\s*(?:comments|comentarios)', content_text)
            if c_match: comments = self._parse_social_number(c_match.group(1))

            # Detección de likes ocultos
            if likes == 0 and ("others" in content_text or "otras personas" in content_text):
                return "Hidden"

            if followers == 0: return 0.0
            return round(((likes + comments) / followers) * 100, 2)

        except: return 0.0

    def _analyze_profile_visual(self):
        """Abre perfil, extrae meta data y calcula métricas"""
        try:
            wait = WebDriverWait(self.driver, 4)
            if "login" in self.driver.current_url: return None

            try:
                meta = wait.until(EC.presence_of_element_located((By.XPATH, "//meta[@name='description']"))).get_attribute("content")
            except: return None

            followers = 0
            posts = 0
            
            f_match = re.search(r'([0-9\.,km]+)\s*(followers|seguidores)', meta)
            p_match = re.search(r'([0-9\.,km]+)\s*(posts|publicaciones)', meta)

            if f_match: followers = self._parse_social_number(f_match.group(1))
            if p_match: posts = self._parse_social_number(p_match.group(1))

            # Filtros duros (Hardcoded de tu script original)
            if not (1000 <= followers <= 100000): return None
            if posts < 50: return None

            engagement = self._calculate_real_engagement(followers)
            category = self._extract_category()
            niche = self._get_niche_match(meta)

            # Filtro de engagement
            is_valid = False
            if isinstance(engagement, str) and engagement == "Hidden":
                is_valid = True
            elif isinstance(engagement, (int, float)) and engagement < 3.0: # Umbral de tu script
                is_valid = True

            if is_valid:
                return {
                    "followers": followers,
                    "posts": posts,
                    "category": category,
                    "niche": niche,
                    "engagement": engagement
                }
            return None

        except: return None

    # --- LOOP PRINCIPAL (Reemplaza al Main) ---
    def run_scraping_task(self, target_profile, max_leads=50):
        """Ejecuta el ciclo de scraping sobre un objetivo"""
        print(f"--- Iniciando Scraping en @{target_profile} ---")
        
        self.driver.get(f"https://www.instagram.com/{target_profile}/")
        time.sleep(3)
        self.dismiss_popups()

        # Abrir lista de seguidores
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
                # Scroll
                try: self.driver.execute_script("arguments[0].scrollIntoView(true);", users_elements[-1])
                except: pass
                time.sleep(1.5)
                continue

            consecutive_fails = 0
            main_window = self.driver.current_window_handle

            for user in new_candidates:
                # Verificamos si ya existe en la DB para no gastar recursos
                if Lead.objects.filter(ig_username=user).exists():
                    continue

                try:
                    # Tu lógica de window.open (Preservada)
                    self.driver.execute_script("window.open('about:blank', '_blank');")
                    WebDriverWait(self.driver, 3).until(lambda d: len(d.window_handles) > 1)
                    self.driver.switch_to.window(self.driver.window_handles[-1])
                    
                    self.driver.get(f"https://www.instagram.com/{user}/")
                    
                    data = self._analyze_profile_visual()
                    
                    if data:
                        # --- GUARDADO EN POSTGRESQL (SaaS) ---
                        Lead.objects.create(
                            ig_username=user,
                            source_account=target_profile,
                            data=data, # JSON Field
                            status='to_contact'
                        )
                        leads_saved += 1
                        print(f"[Lead Nuevo] {user} | Eng: {data['engagement']}")
                    
                    self.driver.close()
                    self.driver.switch_to.window(main_window)
                    
                    if leads_saved >= max_leads: break
                    time.sleep(random.uniform(1, 2))

                except Exception as e:
                    print(f"Error analizando {user}: {e}")
                    if len(self.driver.window_handles) > 1:
                        self.driver.close()
                        self.driver.switch_to.window(main_window)