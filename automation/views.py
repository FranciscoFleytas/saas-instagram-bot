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

# 1. VISTA FRONTEND
def dashboard_view(request):
    # Intentamos obtener la primera cuenta activa, si no hay, usamos un ID placeholder
    account = IGAccount.objects.first()
    account_id = account.id if account else 'sin-cuenta-activa'
    context = {'account_id': account_id}
    return render(request, 'dashboard.html', context)

# 2. API: CONFIGURACIÓN CUENTA (Esta era la que faltaba)
class AccountConfigView(generics.RetrieveUpdateAPIView):
    queryset = IGAccount.objects.all()
    serializer_class = IGAccountSerializer
    lookup_field = 'id'

# 3. API: LISTA DE LEADS (CON FILTROS Y PAGINACIÓN TIPO NOTION)
class LeadListView(generics.ListAPIView):
    serializer_class = LeadSerializer

    def get_queryset(self):
        # 1. Base Query
        queryset = Lead.objects.all().order_by('-created_at')

        # 2. Filtrado: Búsqueda de Texto
        search_query = self.request.query_params.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(ig_username__icontains=search_query) | 
                Q(data__bio__icontains=search_query) |
                Q(full_name__icontains=search_query)
            )

        # 3. Filtrado: Estado
        status_filter = self.request.query_params.get('status', '')
        if status_filter and status_filter != 'all':
            queryset = queryset.filter(status=status_filter)

        # 4. Filtrado: Nicho
        niche_filter = self.request.query_params.get('niche', '')
        if niche_filter and niche_filter != 'all':
            queryset = queryset.filter(data__niche__icontains=niche_filter)

        return queryset

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        
        # 5. Paginación
        page_number = request.query_params.get('page', 1)
        page_size = 10 
        paginator = Paginator(queryset, page_size)

        try:
            page_obj = paginator.page(page_number)
        except Exception:
            page_obj = paginator.page(1)

        serializer = self.get_serializer(page_obj.object_list, many=True)
        
        return Response({
            'count': paginator.count,
            'total_pages': paginator.num_pages,
            'current_page': int(page_number),
            'results': serializer.data
        })

# 4. API: LOGS DEL SISTEMA
@api_view(['GET'])
def get_system_logs(request):
    """Devuelve los últimos 50 logs para la terminal"""
    logs = SystemLog.objects.all().order_by('-created_at')[:50]
    data = [{
        'time': log.created_at.strftime('%H:%M:%S'),
        'level': log.level,
        'message': log.message
    } for log in reversed(logs)]
    return JsonResponse({'logs': data})

# 5. API: DISPARADORES DE BOTS (TRIGGERS)

@api_view(['POST'])
def trigger_bot_interaction(request, pk):
    try:
        account = IGAccount.objects.get(id=pk)
        post_url = request.data.get('post_url')
        persona = request.data.get('user_persona')
        user_prompt = request.data.get('user_prompt')
        use_fast_mode = request.data.get('use_fast_mode', True)
        
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

@api_view(['POST'])
def trigger_bot_scraping(request, pk):
    try:
        target_username = request.data.get('target_username')
        amount = int(request.data.get('amount', 10))
        use_fast_mode = request.data.get('use_fast_mode', True) # Default a True
        
        if not target_username: return Response({"error": "Falta target_username"}, status=400)

        task_id = task_run_scraping.delay(
            account_id=str(pk),
            target_username=target_username,
            max_leads=amount
            # Nota: task_run_scraping usa FastScraperBot por defecto, no necesita param use_fast_mode
        )
        return Response({"status": "Scraping iniciado", "task_id": str(task_id)})
    except Exception as e: return Response({"error": str(e)}, status=500)

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