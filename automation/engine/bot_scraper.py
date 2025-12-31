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

    # --- CONFIGURACIÓN DE NICHOS (Copiada del script funcional) ---
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

    def __init__(self, account_data, proxy_data=None):
        self.username_input = account_data.username
        try:
            self.password_input = account_data.get_password()
        except Exception as e:
            print(f"Advertencia: No se pudo desencriptar password: {e}")
            self.password_input = None

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

            # --- Filtros de tu script original ---
            if not (1000 <= followers <= 100000): # MIN_FOLLOWERS / MAX_FOLLOWERS_CAP
                print(f"[Lead Descartado] @{current_username} | Followers: {followers} (Fuera de rango)")
                return None
            
            if posts < 50: # MIN_POSTS (Ajustado)
                print(f"[Lead Descartado] @{current_username} | Posts: {posts} (Muy pocos)")
                return None
            
            # --- Cálculo ---
            engagement = self._calculate_real_engagement(followers)
            category = self._extract_category()
            niche = self._get_niche_match(meta_content)
            
            # --- Log y Decisión ---
            
            # Caso "Oculto" -> Es válido
            if isinstance(engagement, str):
                print(f"   [OK - OCULTO] @{current_username} | F:{followers} | Eng:{engagement}")
                return {
                    "followers": followers, "posts": posts, "category": category, 
                    "niche": niche, "engagement": engagement, "url": self.driver.current_url
                }

            # Caso Numérico
            if isinstance(engagement, (int, float)):
                print(f"   [INFO] @{current_username} | F:{followers} | Eng:{engagement}%")
                
                # --- CAMBIO DE LÓGICA: BUSCAMOS ENGAGEMENT BAJO ---
                # Guardamos si es MENOR a 3.0% y MAYOR a 0.0% (opcional, para evitar cuentas 100% muertas)
                if 0.0 <= engagement < 3.0: 
                    return {
                        "followers": followers, "posts": posts, "category": category, 
                        "niche": niche, "engagement": engagement, "url": self.driver.current_url
                    }
                else:
                    print(f"   [ALTO ENGAGEMENT] {engagement}% (Descartado por ser muy bueno)")
                    return None

            return None

        except Exception as e:
            print(f"[Error Análisis] {e}")
            return None

    # --- LOOP PRINCIPAL ---
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
                    
                    # Llamamos a la lógica importada
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