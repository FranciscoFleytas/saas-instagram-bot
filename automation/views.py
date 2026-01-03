from django.shortcuts import render
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse

from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import api_view

from .models import IGAccount, Lead, SystemLog
from .serializers import IGAccountSerializer, LeadSerializer
from .tasks import task_run_comment, task_run_scraping, task_run_outreach

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
    return render(request, 'bot_control.html')

def leads_view(request):
    """Renderiza la base de datos de Leads (CRM)"""
    return render(request, 'leads.html')

def extraction_view(request):
    """Renderiza la herramienta de Extracción de Audiencia"""
    return render(request, 'extraction.html')


# --- VISTAS DE API & FUNCIONALIDAD ---

@api_view(['GET'])
def get_system_logs(request):
    """Devuelve los últimos logs del sistema para el frontend"""
    logs = SystemLog.objects.all().order_by('-timestamp')[:50]
    data = [{
        "level": log.level,
        "message": log.message,
        "timestamp": log.timestamp.strftime("%Y-%m-%d %H:%M:%S")
    } for log in logs]
    return Response(data)

class AccountConfigView(generics.RetrieveUpdateAPIView):
    queryset = IGAccount.objects.all()
    serializer_class = IGAccountSerializer
    lookup_field = 'id'

class LeadListView(generics.ListAPIView):
    """API para listar leads con filtros y búsqueda (usada por leads.html via JS si se implementa fetch)"""
    serializer_class = LeadSerializer

    def get_queryset(self):
        queryset = Lead.objects.all().order_by('-created_at')
        search_query = self.request.query_params.get('search', '')
        
        if search_query:
            queryset = queryset.filter(
                Q(username__icontains=search_query) | 
                Q(full_name__icontains=search_query) |
                Q(email__icontains=search_query)
            )
        return queryset

@api_view(['POST'])
def trigger_bot_interaction(request, pk):
    try:
        # Lógica para iniciar interacción (comentarios/likes)
        target_url = request.data.get('target_url')
        if not target_url:
            return Response({"error": "Falta target_url"}, status=400)

        task_id = task_run_comment.delay(account_id=str(pk), media_url=target_url, comment_text="Great post!")
        return Response({"status": "Bot Interacción iniciado", "task_id": str(task_id)})
    except IGAccount.DoesNotExist: 
        return Response({"error": "Cuenta no encontrada"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
def trigger_bot_scraping(request, pk):
    try:
        target_username = request.data.get('target_username')
        amount = int(request.data.get('amount', 10))
        
        if not target_username: 
            return Response({"error": "Falta target_username"}, status=400)

        task_id = task_run_scraping.delay(
            account_id=str(pk),
            target_username=target_username,
            max_leads=amount
        )
        return Response({"status": "Scraping iniciado", "task_id": str(task_id)})
    except Exception as e: 
        return Response({"error": str(e)}, status=500)

@api_view(['POST'])
def trigger_bot_outreach(request, pk):
    try:
        lead_id = request.data.get('lead_id')
        if not lead_id: 
            return Response({"error": "Falta lead_id"}, status=400)

        # Aquí iría la lógica real de outreach
        # task_id = task_run_outreach.delay(...)
        return Response({"status": "Outreach simulado iniciado"}) 
    except Exception as e: 
        return Response({"error": str(e)}, status=500)