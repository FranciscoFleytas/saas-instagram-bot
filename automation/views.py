from django.shortcuts import render

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import api_view

from .models import IGAccount
from .serializers import IGAccountSerializer
from .tasks import task_run_comment

# --- VISTAS DEL FRONTEND (HTML) ---

def dashboard_view(request):
    """Renderiza el Dashboard Overview"""
    # Intentamos obtener la primera cuenta activa para el contexto inicial
    account = IGAccount.objects.first()
    account_id = account.id if account else 'sin-cuenta-activa'
    
    # Podrías pasar datos reales aquí si lo deseas, pero por ahora el HTML usa placeholders
    context = {'account_id': account_id}
    return render(request, 'dashboard.html', context)

def bot_control_view(request):
    """Renderiza la vista de Control de Bots / Interacción Automática"""
    account = IGAccount.objects.first()
    account_id = account.id if account else 'sin-cuenta-activa'
    context = {'account_id': account_id}
    return render(request, 'bot_control.html', context)

def extraction_view(request):
    """Renderiza la herramienta de Extracción de Audiencia"""
    account = IGAccount.objects.first()
    account_id = account.id if account else 'sin-cuenta-activa'
    context = {'account_id': account_id}
    return render(request, 'extraction.html', context)


# --- VISTAS DE API & FUNCIONALIDAD ---

class AccountConfigView(generics.RetrieveUpdateAPIView):
    queryset = IGAccount.objects.all()
    serializer_class = IGAccountSerializer
    lookup_field = 'id'

@api_view(['POST'])
def trigger_bot_interaction(request, pk):
    try:
        # Lógica para iniciar interacción (comentarios/likes)
        target_url = request.data.get('target_url')
        if not target_url:
            return Response({"error": "Falta target_url"}, status=400)

        task_id = task_run_comment.delay(account_id=str(pk), post_url=target_url, comment_text="Great post!")
        return Response({"status": "Bot Interacción iniciado", "task_id": str(task_id)})
    except IGAccount.DoesNotExist: 
        return Response({"error": "Cuenta no encontrada"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)
