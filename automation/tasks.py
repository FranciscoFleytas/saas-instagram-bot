from celery import shared_task
from django.utils import timezone
import logging
import random
from datetime import timedelta

# Importamos los Modelos para leer credenciales de la DB
from automation.models import IGAccount, Lead

# Importamos nuestros Motores de Bots (Engine)
from automation.engine.bot_scraper import ScraperBot
from automation.engine.bot_outreach import OutreachBot
from automation.engine.bot_comment import CommentBot

# Configuración de Logging
logger = logging.getLogger(__name__)

# ==============================================================================
# TAREA 1: SCRAPING + ORQUESTADOR 
# ==============================================================================
@shared_task(bind=True)
def task_run_scraping(self, account_id, target_username, max_leads=50):
    """
    1. Ejecuta el ScraperBot con los filtros del usuario.
    2. Al finalizar, verifica si el usuario tiene activado 'enable_autodm' (Premium).
    3. Si es Premium: Agenda automáticamente el Outreach con retraso (Goteo).
    4. Si es Básico: Solo guarda los leads y termina.
    """
    bot = None
    try:
        logger.info(f"[TASK SCRAPE] Iniciando Pipeline para Cuenta ID: {account_id}")
        
        # 1. Obtener Cuenta y Configuraciones
        account = IGAccount.objects.get(id=account_id)
        
        # A. Filtros de Búsqueda (Para el Scraper)
        user_filters = account.config.get('filters', None)
        
        # B. Configuración de Automatización (El Interruptor Premium)
        # Por defecto es FALSE. Solo si el cliente pagó y lo activó será True.
        automation_config = account.config.get('automation', {})
        enable_autodm = automation_config.get('enable_autodm', False)

        # 2. Inicializar y Ejecutar Scraper
        bot = ScraperBot(
            account_data=account, 
            proxy_data=account.proxy,
            filters=user_filters
        )
        
        bot.start_driver()
        bot.login()
        
        # Guardamos la hora de inicio para identificar los leads nuevos de ESTA sesión
        start_time = timezone.now()
        
        bot.run_scraping_task(target_profile=target_username, max_leads=max_leads)
        
        # 3. Lógica Post-Scraping (El Cerebro del SaaS)
        
        # Buscamos los leads que se crearon en esta ejecución
        new_leads = Lead.objects.filter(
            source_account=target_username,
            created_at__gte=start_time,
            status='to_contact'
        )
        count = new_leads.count()
        logger.info(f"[RESUMEN] Se guardaron {count} leads nuevos.")

        # 4. Decisión según Plan (Basic vs Premium)
        if enable_autodm and count > 0:
            logger.info(f"[PLAN PREMIUM] 'enable_autodm' ACTIVADO. Agendando mensajes...")
            
            # Goteo Inteligente: No enviamos todo ya. Empezamos en 10 min.
            current_delay_minutes = 10 
            
            for lead in new_leads:
                # Añadimos un intervalo aleatorio entre 15 y 45 minutos por lead
                # para que parezca comportamiento humano y evitar bloqueos.
                interval = random.randint(15, 45)
                current_delay_minutes += interval
                
                # Agendamos la Tarea 2 (Outreach) para el futuro
                task_run_outreach.apply_async(
                    args=[account_id, lead.id],
                    countdown=current_delay_minutes * 60 # Celery usa segundos
                )
                
                logger.info(f" -> Outreach agendado para @{lead.ig_username} en {current_delay_minutes} min.")
                
            return f"SUCCESS_PREMIUM: {count} leads queued for drip outreach"
            
        else:
            # Plan Básico o Interruptor Apagado
            logger.info(f"[PLAN BASIC] 'enable_autodm' DESACTIVADO. Leads listos para revisión manual.")
            return f"SUCCESS_BASIC: {count} leads saved (no outreach)"

    except IGAccount.DoesNotExist:
        logger.error("La cuenta especificada no existe.")
        return "ERROR_ACCOUNT"
    except Exception as e:
        logger.error(f"[TASK ERROR] Fallo en scraping: {str(e)}")
        return f"ERROR: {str(e)}"
    finally:
        if bot: bot.close()

# ==============================================================================
# TAREA 2: OUTREACH (Ejecución Individual)
# ==============================================================================
@shared_task(bind=True)
def task_run_outreach(self, account_id, lead_id):
    """
    Envía un DM personalizado. Esta tarea es llamada por el Scraper (Premium) 
    o manualmente por el usuario (Basic).
    """
    bot = None
    try:
        logger.info(f"[TASK OUTREACH] Ejecutando para Lead ID: {lead_id}")
        
        account = IGAccount.objects.get(id=account_id)
        try:
            lead = Lead.objects.get(id=lead_id)
        except Lead.DoesNotExist:
            return "LEAD_NOT_FOUND"

        # Seguridad: Verificar si ya fue contactado para no duplicar
        if lead.status == 'contacted':
            logger.warning(f"Lead {lead.ig_username} ya tiene status 'contacted'. Cancelando envío.")
            return "ALREADY_CONTACTED"

        # Instanciar Bot de Outreach
        bot = OutreachBot(account_data=account, proxy_data=account.proxy)
        
        bot.start_driver()
        bot.login()
        
        # Ejecutar lógica de envío (bot_outreach.py se encarga de Gemini y Selenium)
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
# TAREA 3: ENGAGEMENT 
# ==============================================================================
# ==============================================================================
# TAREA 3: ENGAGEMENT (Actualizada)
# ==============================================================================
@shared_task(bind=True)
def task_run_comment(self, account_id, post_url, do_like=True, do_save=False, do_comment=True, 
                     user_persona=None, focus_selection=None, user_prompt=None): # <--- AQUÍ FALTABA
    """
    Realiza interacciones en un post. Soporta prompt personalizado.
    """
    bot = None
    try:
        logger.info(f"[TASK] Interacción en {post_url} (Like={do_like}, Save={do_save}, Cmt={do_comment})")
        
        account = IGAccount.objects.get(id=account_id)
        # Importamos aquí para evitar ciclos
        from automation.engine.bot_comment import CommentBot 
        bot = CommentBot(account_data=account, proxy_data=account.proxy)
        
        # Ya no usamos start_driver/login manuales porque BotEngine lo hace en el __init__
        # pero si tu logica actual los requiere explicitamente, déjalos.
        # Asumiendo tu bot_comment.py actual, execute_interaction maneja la navegación.
        
        success = bot.execute_interaction(
            post_url=post_url,
            do_like=do_like,
            do_save=do_save,
            do_comment=do_comment,
            user_persona=user_persona,
            focus_selection=focus_selection,
            user_prompt=user_prompt  # <--- SE LO PASAMOS AL BOT
        )
        
        return "INTERACTION_SUCCESS" if success else "INTERACTION_FAILED"

    except Exception as e:
        logger.error(f"[TASK ERROR] Fallo en interacción: {str(e)}")
        return f"ERROR: {str(e)}"
    finally:
        if bot: 
            try: bot.quit()
            except: pass