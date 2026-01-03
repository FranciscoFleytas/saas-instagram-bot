from django.shortcuts import render
from rest_framework import generics
from rest_framework.response import Response
from rest_framework.decorators import api_view
from .models import IGAccount, Lead
from .serializers import IGAccountSerializer, LeadSerializer
from .tasks import task_run_comment, task_run_scraping, task_run_outreach

# 1. VISTA FRONTEND
def dashboard_view(request):
    # NOTA: Reemplaza esto con lógica dinámica real cuando tengas login
    test_account_id = '11816414-0378-459c-af3a-fac0ee101944' 
    context = {'account_id': test_account_id}
    return render(request, 'dashboard.html', context)

# 2. API: CONFIGURACIÓN CUENTA
class AccountConfigView(generics.RetrieveUpdateAPIView):
    queryset = IGAccount.objects.all()
    serializer_class = IGAccountSerializer
    lookup_field = 'id'

class LeadListView(generics.ListAPIView):
    serializer_class = LeadSerializer
    def get_queryset(self):
        return Lead.objects.all().order_by('-created_at')[:50]

# 3. API: TRIGGER COMENTARIOS
@api_view(['POST'])
def trigger_bot_interaction(request, pk):
    try:
        account = IGAccount.objects.get(id=pk)
        post_url = request.data.get('post_url')
        persona = request.data.get('user_persona')
        user_prompt = request.data.get('user_prompt')
        use_fast_mode = request.data.get('use_fast_mode', False)
        
        do_like = request.data.get('do_like', True)
        do_comment = request.data.get('do_comment', True)
        do_save = request.data.get('do_save', False)
        
        if not post_url: return Response({"error": "Falta post_url"}, status=400)

        task_id = task_run_comment.delay(
            account_id=str(account.id), 
            post_url=post_url, 
            user_persona=persona,
            do_like=do_like,
            do_comment=do_comment,
            do_save=do_save,
            user_prompt=user_prompt,
            use_fast_mode=use_fast_mode
        )
        return Response({"status": "Bot Interacción iniciado", "task_id": str(task_id)})
    except IGAccount.DoesNotExist: 
        return Response({"error": "Cuenta no encontrada"}, status=404)
    except Exception as e:
        return Response({"error": str(e)}, status=500)

# --- TRIGGER SCRAPING (CORREGIDO) ---
@api_view(['POST'])
def trigger_bot_scraping(request, pk):
    try:
        target_username = request.data.get('target_username')
        amount = int(request.data.get('amount', 10))
        
        # --- AQUÍ ESTÁ EL CAMBIO ---
        # Capturamos el parámetro del frontend
        use_fast_mode = request.data.get('use_fast_mode', False) 
        
        if not target_username: return Response({"error": "Falta target_username"}, status=400)

        # Se lo pasamos a la tarea
        task_id = task_run_scraping.delay(
            account_id=str(pk),
            target_username=target_username,
            max_leads=amount,
            use_fast_mode=use_fast_mode # <--- ¡Conectado!
        )
        return Response({"status": "Scraping iniciado", "task_id": str(task_id)})
    except Exception as e: return Response({"error": str(e)}, status=500)

# --- TRIGGER OUTREACH (DM) ---
@api_view(['POST'])
def trigger_bot_outreach(request, pk):
    try:
        lead_id = request.data.get('lead_id')
        if not lead_id: return Response({"error": "Falta lead_id"}, status=400)

        task_id = task_run_outreach.delay(
            account_id=str(pk),
            lead_id=lead_id
        )
        return Response({"status": "Outreach iniciado", "task_id": str(task_id)})
    except Exception as e: return Response({"error": str(e)}, status=500)