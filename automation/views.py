from django.shortcuts import render
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import IGAccount, Lead
from .serializers import IGAccountSerializer, LeadSerializer
from .tasks import task_run_comment, task_run_scraping, task_run_outreach

# 1. VISTA FRONTEND
def dashboard_view(request):
    test_account_id = '11816414-0378-459c-af3a-fac0ee101944' # Tu ID Real
    context = {'account_id': test_account_id}
    return render(request, 'dashboard.html', context)

# 2. API: CONFIGURACIÓN CUENTA
class AccountConfigView(generics.RetrieveUpdateAPIView):
    queryset = IGAccount.objects.all()
    serializer_class = IGAccountSerializer
    lookup_field = 'id'

# En automation/views.py

class LeadListView(generics.ListAPIView):
    """
    HOTFIX: Devuelve los últimos 50 leads SIN filtrar por cuenta 
    para evitar errores de base de datos mientras probamos.
    """
    serializer_class = LeadSerializer

    def get_queryset(self):
        # ANTES (Causaba error 500 si no existe la relación):
        # account_id = self.kwargs['pk']
        # return Lead.objects.filter(account_id=account_id).order_by('-created_at')[:50]
        
        # AHORA (Para pruebas inmediatas):
        return Lead.objects.all().order_by('-created_at')[:50]

# 3. API: TRIGGER COMENTARIOS (Ya existía)
@api_view(['POST'])
def trigger_bot_interaction(request, pk):
    try:
        account = IGAccount.objects.get(id=pk)
        post_url = request.data.get('post_url')
        persona = request.data.get('user_persona')
        focus = request.data.get('focus_selection')
        
        if not post_url: return Response({"error": "Falta post_url"}, status=400)

        task_id = task_run_comment.delay(
            account_id=str(account.id), post_url=post_url, do_comment=True,
            user_persona=persona, focus_selection=focus
        )
        return Response({"status": "Bot Comentarios iniciado", "task_id": str(task_id)})
    except IGAccount.DoesNotExist: return Response({"error": "Cuenta no encontrada"}, status=404)

# --- NUEVO: TRIGGER SCRAPING ---
@api_view(['POST'])
def trigger_bot_scraping(request, pk):
    """Inicia la búsqueda de leads en un perfil objetivo"""
    try:
        target_username = request.data.get('target_username')
        amount = int(request.data.get('amount', 10))
        
        if not target_username: return Response({"error": "Falta target_username"}, status=400)

        # Llama a la tarea existente en tasks.py
        task_id = task_run_scraping.delay(
            account_id=str(pk),
            target_username=target_username,
            max_leads=amount
        )
        return Response({"status": "Scraping iniciado", "task_id": str(task_id)})
    except Exception as e: return Response({"error": str(e)}, status=500)

# --- NUEVO: TRIGGER OUTREACH (DM) ---
@api_view(['POST'])
def trigger_bot_outreach(request, pk):
    """Envía un DM a un Lead específico"""
    try:
        lead_id = request.data.get('lead_id')
        if not lead_id: return Response({"error": "Falta lead_id"}, status=400)

        # Llama a la tarea existente en tasks.py
        task_id = task_run_outreach.delay(
            account_id=str(pk),
            lead_id=lead_id
        )
        return Response({"status": "Outreach iniciado", "task_id": str(task_id)})
    except Exception as e: return Response({"error": str(e)}, status=500)