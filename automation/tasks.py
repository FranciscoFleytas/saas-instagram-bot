from celery import shared_task
from django.utils import timezone
import logging

# Importamos los Modelos para leer credenciales de la DB
from automation.models import IGAccount, Lead

# Importamos nuestros Motores de Bots (Engine)
from automation.engine.bot_scraper import ScraperBot
from automation.engine.bot_outreach import OutreachBot
from automation.engine.bot_comment import CommentBot

# Configuración de Logging para ver errores en la terminal de Celery
logger = logging.getLogger(__name__)

# ==============================================================================
# TAREA 1: SCRAPING (Búsqueda de Clientes)
# ==============================================================================
@shared_task(bind=True)
def task_run_scraping(self, account_id, target_username, max_leads=50):
    """
    Ejecuta el ScraperBot en segundo plano.
    """
    bot = None
    try:
        logger.info(f"[TASK] Iniciando Scraping con Cuenta ID: {account_id}")
        
        # 1. Obtener Credenciales de la DB
        account = IGAccount.objects.get(id=account_id)
        
        # 2. Inicializar Bot (Pasa la cuenta y el objeto Proxy asociado)
        bot = ScraperBot(account_data=account, proxy_data=account.proxy)
        
        # 3. Ciclo de Vida del Bot
        bot.start_driver()      # Abre Chrome
        bot.login()             # Inicia Sesión
        bot.run_scraping_task(target_profile=target_username, max_leads=max_leads)
        
        logger.info(f"[TASK] Scraping finalizado exitosamente.")
        return "SUCCESS"

    except IGAccount.DoesNotExist:
        logger.error("La cuenta especificada no existe.")
        return "ERROR_ACCOUNT_NOT_FOUND"
    except Exception as e:
        logger.error(f"[TASK ERROR] Fallo en scraping: {str(e)}")
        # Aquí podrías actualizar el estado de la cuenta a 'error' en la DB
        return f"ERROR: {str(e)}"
    finally:
        # 4. Limpieza obligatoria (Cerrar Chrome y borrar temporales)
        if bot:
            bot.close()

# ==============================================================================
# TAREA 2: OUTREACH (Envío de DMs en Frío)
# ==============================================================================
@shared_task(bind=True)
def task_run_outreach(self, account_id, lead_id):
    """
    Envía un DM personalizado a un Lead específico usando IA.
    """
    bot = None
    try:
        logger.info(f"[TASK] Iniciando Outreach para Lead ID: {lead_id}")
        
        account = IGAccount.objects.get(id=account_id)
        # Verificamos que el Lead exista
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return "LEAD_NOT_FOUND"

        # Instanciar Bot de Outreach
        bot = OutreachBot(account_data=account, proxy_data=account.proxy)
        
        bot.start_driver()
        bot.login()
        
        # Ejecutar lógica de envío
        success = bot.send_dm_to_lead(lead_id=lead.id)
        
        if success:
            return f"DM_SENT_TO_{lead.ig_username}"
        else:
            return "DM_FAILED"

    except Exception as e:
        logger.error(f"[TASK ERROR] Fallo en Outreach: {str(e)}")
        return f"ERROR: {str(e)}"
    finally:
        if bot: bot.close()

# ==============================================================================
# TAREA 3: ENGAGEMENT (Comentarios con Visión Artificial)
# ==============================================================================
@shared_task(bind=True)
def task_run_comment(self, account_id, post_url, custom_instruction=None):
    """
    Deja un comentario inteligente en un post específico.
    """
    bot = None
    try:
        logger.info(f"[TASK] Iniciando Comentario en: {post_url}")
        
        account = IGAccount.objects.get(id=account_id)
        bot = CommentBot(account_data=account, proxy_data=account.proxy)
        
        bot.start_driver()
        bot.login()
        
        success = bot.execute_comment(post_url) # El método interno ya maneja la IA
        
        return "COMMENT_POSTED" if success else "COMMENT_FAILED"

    except Exception as e:
        logger.error(f"[TASK ERROR] Fallo en Comentarios: {str(e)}")
        return f"ERROR: {str(e)}"
    finally:
        if bot: bot.close()