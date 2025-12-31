from django.shortcuts import render
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import IGAccount
from .serializers import IGAccountSerializer
from .tasks import task_run_comment

# ==============================================================================
# 1. VISTA FRONTEND (HTML)
# ==============================================================================
def dashboard_view(request):
    """
    Renderiza la plantilla HTML de AdminLTE (dashboard.html).
    Pasamos el ID de la cuenta de prueba en el contexto.
    """
    # ID de tu cuenta real para pruebas (Hardcodeado por ahora)
    test_account_id = '11816414-0378-459c-af3a-fac0ee101944'
    
    context = {
        'account_id': test_account_id
    }
    return render(request, 'dashboard.html', context)

# ==============================================================================
# 2. API: CONFIGURACIÓN DE CUENTA (Lectura/Escritura)
# ==============================================================================
class AccountConfigView(generics.RetrieveUpdateAPIView):
    """
    Permite al Dashboard leer y guardar la 'ai_persona' y 'ai_focus'.
    Endpoint: GET/PUT /api/account/<uuid:id>/config/
    """
    queryset = IGAccount.objects.all()
    serializer_class = IGAccountSerializer
    lookup_field = 'id'

# ==============================================================================
# 3. API: DISPARADOR DEL BOT (Trigger)
# ==============================================================================
@api_view(['POST'])
def trigger_bot_interaction(request, pk):
    """
    Recibe la orden del Dashboard para iniciar el bot.
    Acepta parámetros manuales (URL, Persona, Focus) y los pasa a Celery.
    Endpoint: POST /api/account/<uuid:pk>/start-bot/
    """
    try:
        account = IGAccount.objects.get(id=pk)
        
        # 1. Capturar datos del JSON enviado por el Dashboard
        post_url = request.data.get('post_url')
        persona = request.data.get('user_persona')     # Texto del textarea
        focus = request.data.get('focus_selection')    # Lista de checkboxes
        
        # Validación básica
        if not post_url:
            return Response({"error": "Falta la URL del post (post_url)"}, status=400)

        # 2. Disparar la tarea de Celery con los NUEVOS argumentos
        task_id = task_run_comment.delay(
            account_id=str(account.id),
            post_url=post_url,
            do_comment=True,
            # Pasamos lo que vino del front. 
            # Si vienen vacíos (None), la tarea usará los de la DB.
            user_persona=persona,    
            focus_selection=focus    
        )
        
        return Response({
            "status": "Bot iniciado correctamente", 
            "task_id": str(task_id),
            "debug_info": {
                "persona_sent": persona,
                "focus_sent": focus
            }
        })
        
    except IGAccount.DoesNotExist:
        return Response({"error": "Cuenta no encontrada"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)