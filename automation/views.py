import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required

# Importamos Modelos
from .models import IGAccount, Lead

# Importamos las Tareas de Celery
from .tasks import task_run_scraping, task_run_outreach, task_run_comment

# ==============================================================================
# VISTA 1: INICIAR SCRAPING
# ==============================================================================
@csrf_exempt
@login_required
def start_scraping_view(request):
    """
    Endpoint para iniciar el Scraper.
    Payload: { "account_id": 1, "target_profile": "cliente_objetivo", "max_leads": 50 }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            account_id = data.get('account_id')
            target_profile = data.get('target_profile')
            max_leads = int(data.get('max_leads', 50))
            
            if not account_id or not target_profile:
                return JsonResponse({"status": "error", "message": "Faltan datos obligatorios"}, status=400)

            # Verificar cuenta
            try:
                account = IGAccount.objects.get(id=account_id)
            except IGAccount.DoesNotExist:
                return JsonResponse({"status": "error", "message": "Cuenta IG no encontrada"}, status=404)

            # Lanzar Tarea
            task_run_scraping.delay(account_id, target_profile, max_leads)

            return JsonResponse({
                "status": "success", 
                "message": f"Bot iniciado. Buscando {max_leads} leads de @{target_profile}."
            })

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)


# ==============================================================================
# VISTA 2: INICIAR OUTREACH (Envío de DM)
# ==============================================================================
@csrf_exempt
@login_required
def start_outreach_view(request):
    """
    Endpoint para enviar un DM a un Lead específico.
    Payload: { "account_id": 1, "lead_id": 450 }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            account_id = data.get('account_id')
            lead_id = data.get('lead_id')

            if not account_id or not lead_id:
                return JsonResponse({"status": "error", "message": "Faltan datos (account_id o lead_id)"}, status=400)

            # Validaciones rápidas de existencia
            if not IGAccount.objects.filter(id=account_id).exists():
                 return JsonResponse({"status": "error", "message": "Cuenta IG no existe"}, status=404)
            
            if not Lead.objects.filter(id=lead_id).exists():
                 return JsonResponse({"status": "error", "message": "Lead no existe"}, status=404)

            # Lanzar Tarea de Outreach
            task_run_outreach.delay(account_id, lead_id)

            return JsonResponse({
                "status": "success", 
                "message": f"Bot de Outreach activado para el Lead ID {lead_id}."
            })

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)


# ==============================================================================
# VISTA 3: INICIAR COMENTARIO (Engagement)
# ==============================================================================
@csrf_exempt
@login_required
def start_comment_view(request):
    """
    Endpoint para dejar un comentario en un post.
    Payload: { "account_id": 1, "post_url": "https://inst...", "custom_instruction": "Sé amable" }
    """
    if request.method == "POST":
        try:
            data = json.loads(request.body)
            account_id = data.get('account_id')
            post_url = data.get('post_url')
            custom_instruction = data.get('custom_instruction', None) # Opcional

            if not account_id or not post_url:
                return JsonResponse({"status": "error", "message": "Faltan datos (account_id o post_url)"}, status=400)

            if not IGAccount.objects.filter(id=account_id).exists():
                 return JsonResponse({"status": "error", "message": "Cuenta IG no existe"}, status=404)

            # Lanzar Tarea de Comentario
            task_run_comment.delay(account_id, post_url, custom_instruction)

            return JsonResponse({
                "status": "success", 
                "message": f"Bot de Comentarios iniciado para el post."
            })

        except Exception as e:
            return JsonResponse({"status": "error", "message": str(e)}, status=500)

    return JsonResponse({"status": "error", "message": "Método no permitido"}, status=405)