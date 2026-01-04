from celery import shared_task
import logging
import random
import google.generativeai as genai
import time
from django.conf import settings

# Importamos los Modelos
from automation.models import IGAccount, Agency

# Configuración
logger = logging.getLogger(__name__)

def generate_api_comment(user_prompt, user_persona):
    """
    Genera un comentario usando Gemini para el Modo API.
    """
    try:
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel('gemini-2.5-flash')

        persona_str = f"IDENTITY: {user_persona}" if user_persona else "IDENTITY: Expert Social Media User."
        instruction = f"INSTRUCTION: {user_prompt}" if user_prompt else "INSTRUCTION: Write a positive, short engagement comment."

        prompt = f"""
        ROLE: Social Media Bot.
        TASK: Write a SHORT Instagram comment (max 1 sentence).
        {persona_str}
        {instruction}
        CONSTRAINTS: Natural language, NO hashtags, match language.
        """
        
        response = model.generate_content(prompt)
        return response.text.strip().replace('"', '')
    except Exception as e:
        logger.error(f"[AI ERROR] Falló generación: {e}")
        return "Great post! 🔥"

# ==============================================================================
# ==============================================================================
# TAREA: ENGAGEMENT (MODO ENJAMBRE / SWARM)
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
                farm_accounts = IGAccount.objects.filter(agency=pool_agency, status='active')
                
                if not farm_accounts.exists():
                    return "ERROR_NO_FARM_ACCOUNTS"
                
                logger.info(f"[SWARM] Se detectaron {farm_accounts.count()} cuentas listas.")

            except Agency.DoesNotExist:
                return "ERROR_NO_POOL_AGENCY"

            success_count = 0
            fail_count = 0
            
            from automation.engine.bot_fast_interaction import FastInteractionBot

            # BUCLE DE ATAQUE (Una por una)
            for farm_acc in farm_accounts:
                try:
                    logger.info(f"[SWARM] ➡️ Turno de: {farm_acc.username}")
                    
                    bot = FastInteractionBot(farm_acc, proxy_data=None)
                    
                    if not bot.login():
                        logger.warning(f"   [SKIP] Falló login de {farm_acc.username}")
                        fail_count += 1
                        continue

                    # Generar Comentario ÚNICO
                    comment_text = None
                    if do_comment:
                        comment_text = generate_api_comment(user_prompt, user_persona)
                        time.sleep(1) # Pausa para Gemini

                    # Ejecutar Acción
                    if bot.execute(post_url, do_like, do_comment, comment_text):
                        success_count += 1
                        logger.info(f"   ✅ {farm_acc.username} completó la misión.")
                    else:
                        fail_count += 1
                    
                    # Pausa humana
                    delay = random.randint(5, 10)
                    logger.info(f"   ⏸️ Esperando {delay}s...")
                    time.sleep(delay)

                except Exception as inner_e:
                    logger.error(f"   [ERROR] Bot {farm_acc.username} crasheó: {inner_e}")
                    fail_count += 1

            return f"SWARM_REPORT: ✅ {success_count} Exitosos | ❌ {fail_count} Fallidos"

        # --- CAMINO B: MODO VISUAL (Selenium) ---
        else:
            logger.info(f"[TASK] Usando MODO VISUAL (Selenium) para {post_url}")
            client_account = IGAccount.objects.get(id=account_id)
            
            from automation.engine.bot_comment import CommentBot 
            bot = CommentBot(account_data=client_account, proxy_data=None)
            
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
