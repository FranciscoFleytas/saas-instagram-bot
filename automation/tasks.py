from celery import shared_task
from django.utils import timezone
import logging
import random
import google.generativeai as genai  # <--- IMPORTANTE: Para la IA
from datetime import timedelta
import time

# Importamos los Modelos
from automation.models import IGAccount, Lead, Agency

# Importamos Motores
from automation.engine.bot_scraper import ScraperBot
from automation.engine.bot_outreach import OutreachBot
from automation.engine.bot_comment import CommentBot

# Configuración de Logging y API Key de Gemini
logger = logging.getLogger(__name__)
# Nota: Idealmente mover esta KEY a settings.py o .env
GENAI_API_KEY = "AIzaSyBNb446tcr2Ol80gmrz0_5ue9M_uO451CA"

# ==============================================================================
# UTILIDADES
# ==============================================================================
def get_proxy_dict(account):
    if hasattr(account, 'proxy') and account.proxy:
        return {
            'host': account.proxy.ip_address,
            'port': account.proxy.port,
            'user': account.proxy.username,
            'pass': account.proxy.password
        }
    return None

def generate_api_comment(user_prompt, user_persona):
    """
    Genera un comentario usando Gemini para el Modo API (sin navegador).
    """
    try:
        genai.configure(api_key=GENAI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        persona_str = f"IDENTITY: {user_persona}" if user_persona else "IDENTITY: Expert Social Media User."
        instruction = f"INSTRUCTION: {user_prompt}" if user_prompt else "INSTRUCTION: Write a positive, short engagement comment."

        prompt = f"""
        ROLE: Social Media Bot.
        TASK: Write a SHORT Instagram comment (max 1 sentence).
        {persona_str}
        {instruction}
        
        CONSTRAINTS:
        1. Natural language.
        2. NO hashtags.
        3. Match the language of the instruction (if Spanish, write in Spanish).
        """
        
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '')
    except Exception as e:
        logger.error(f"[AI ERROR] Falló generación: {e}")
        return "Great post! 🔥" # Fallback seguro

# ==============================================================================
# TAREA 1: SCRAPING (Con Rotación de Pool)
# ==============================================================================
@shared_task(bind=True)
def task_run_scraping(self, account_id, target_username, max_leads=50):
    bot = None
    try:
        logger.info(f"[TASK SCRAPE] Orden recibida de Cuenta ID: {account_id}")
        client_account = IGAccount.objects.get(id=account_id)
        
        # --- ROTACIÓN DE POOL (Protección de Cuenta) ---
        account_to_use = client_account
        try:
            pool_agency = Agency.objects.filter(name="Imported Scrapers Pool").first()
            if pool_agency:
                # Elegir scraper aleatorio
                random_scraper = IGAccount.objects.filter(agency=pool_agency, status='active').order_by('?').first()
                if random_scraper:
                    logger.info(f"[POOL] 🛡️ Usando Scraper: {random_scraper.username}")
                    account_to_use = random_scraper
        except Exception as e:
            logger.error(f"[POOL ERROR] {e}")

        # Ejecución
        proxy_data = get_proxy_dict(account_to_use)
        bot = ScraperBot(account_data=account_to_use, proxy_data=proxy_data, filters=client_account.config.get('filters'))
        
        start_time = timezone.now()
        bot.run_scraping_task(target_profile=target_username, max_leads=max_leads)
        
        # Procesamiento de Leads
        new_leads = Lead.objects.filter(source_account=target_username, created_at__gte=start_time, status='to_contact')
        count = new_leads.count()
        
        # Automation Check
        if client_account.config.get('automation', {}).get('enable_autodm', False) and count > 0:
            current_delay = 10
            for lead in new_leads:
                current_delay += random.randint(15, 45)
                task_run_outreach.apply_async(args=[account_id, lead.id], countdown=current_delay * 60)
            return f"SUCCESS_PREMIUM: {count} leads mined & queued"
            
        return f"SUCCESS: {count} leads mined"

    except Exception as e:
        logger.error(f"[TASK ERROR] {e}")
        return f"ERROR: {e}"
    finally:
        if bot: 
            try: bot.quit()
            except: pass

# ==============================================================================
# TAREA 2: OUTREACH
# ==============================================================================
@shared_task(bind=True)
def task_run_outreach(self, account_id, lead_id):
    bot = None
    try:
        account = IGAccount.objects.get(id=account_id)
        lead = Lead.objects.get(id=lead_id)
        
        if lead.status == 'contacted': return "ALREADY_CONTACTED"

        proxy_data = get_proxy_dict(account)
        bot = OutreachBot(account_data=account, proxy_data=proxy_data)
        
        if bot.send_dm_to_lead(lead_id=lead.id):
            return f"DM_SENT_{lead.ig_username}"
        return "DM_FAILED"

    except Exception as e:
        logger.error(f"[OUTREACH ERROR] {e}")
        return f"ERROR: {e}"
    finally:
        if bot: 
            try: bot.quit()
            except: pass

# ==============================================================================
# TAREA 3: ENGAGEMENT (CEREBRO HÍBRIDO + IA)
# ==============================================================================
@shared_task(bind=True)
def task_run_comment(self, account_id, post_url, do_like=True, do_save=False, do_comment=True, 
                     user_persona=None, focus_selection=None, user_prompt=None, use_fast_mode=False):
    bot = None
    try:
        # --- CAMINO A: MODO GRANJA (API + ENJAMBRE) ---
        if use_fast_mode:
            logger.info(f"[TASK] 🚀 Iniciando MODO ENJAMBRE (API) en {post_url}")
            
            # 1. Obtener TODAS las cuentas activas del Pool
            try:
                pool_agency = Agency.objects.get(name="Imported Scrapers Pool")
                # CAMBIO CLAVE: Usamos .all() en lugar de .order_by('?').first()
                farm_accounts = IGAccount.objects.filter(agency=pool_agency, status='active')
                
                if not farm_accounts.exists():
                    return "ERROR_NO_FARM_ACCOUNTS"
                
                logger.info(f"[SWARM] Se detectaron {farm_accounts.count()} cuentas listas para el ataque.")

            except Agency.DoesNotExist:
                return "ERROR_NO_POOL_AGENCY"

            # 2. Bucle de Ejecución (Una por una)
            success_count = 0
            fail_count = 0
            
            # Importar motor API
            from automation.engine.bot_fast_interaction import FastInteractionBot

            for farm_acc in farm_accounts:
                try:
                    logger.info(f"[SWARM] ➡️ Turno de: {farm_acc.username}")
                    
                    # A. Login
                    proxy_data = get_proxy_dict(farm_acc)
                    bot = FastInteractionBot(farm_acc, proxy_data)
                    
                    if not bot.login():
                        logger.warning(f"   [SKIP] Falló login de {farm_acc.username}")
                        fail_count += 1
                        continue

                    # B. Generar Comentario ÚNICO (Para que no digan todos lo mismo)
                    comment_text = None
                    if do_comment:
                        # Generamos una variación nueva cada vez
                        comment_text = generate_api_comment(user_prompt, user_persona)
                        # Pequeña pausa para no saturar la API de Gemini
                        time.sleep(1)

                    # C. Ejecutar Acción
                    if bot.execute(post_url, do_like, do_comment, comment_text):
                        success_count += 1
                        logger.info(f"   ✅ {farm_acc.username} completó la misión.")
                    else:
                        fail_count += 1
                    
                    # D. Pausa entre bots (Para que Instagram no detecte tráfico simultáneo exacto)
                    # Espera entre 5 y 10 segundos entre cada cuenta
                    delay = random.randint(5, 10)
                    logger.info(f"   ⏸️ Esperando {delay}s para el siguiente bot...")
                    time.sleep(delay)

                except Exception as inner_e:
                    logger.error(f"   [ERROR] Bot {farm_acc.username} crasheó: {inner_e}")
                    fail_count += 1

            return f"SWARM_REPORT: ✅ {success_count} Exitosos | ❌ {fail_count} Fallidos"

        # --- CAMINO B: MODO VISUAL (Selenium - Solo 1 cuenta) ---
        else:
            logger.info(f"[TASK] Usando MODO VISUAL (Selenium) para {post_url}")
            client_account = IGAccount.objects.get(id=account_id)
            proxy_data = get_proxy_dict(client_account)
            
            from automation.engine.bot_comment import CommentBot 
            bot = CommentBot(account_data=client_account, proxy_data=proxy_data)
            
            success = bot.execute_interaction(
                post_url=post_url, do_like=do_like, do_save=do_save, do_comment=do_comment,
                user_persona=user_persona, focus_selection=focus_selection, user_prompt=user_prompt
            )
            return "VISUAL_SUCCESS" if success else "VISUAL_FAILED"

    except Exception as e:
        logger.error(f"[TASK ERROR] {e}")
        return f"ERROR: {str(e)}"
    finally:
        if bot and hasattr(bot, 'quit'): 
            try: bot.quit()
            except: pass