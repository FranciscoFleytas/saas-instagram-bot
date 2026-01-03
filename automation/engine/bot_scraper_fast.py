import time
import random
import logging
from datetime import timedelta
from django.utils import timezone
from django.db.models import Q
from instagrapi import Client
from instagrapi.exceptions import (
    LoginRequired, ChallengeRequired, FeedbackRequired, 
    PleaseWaitFewMinutes, RateLimitError
)
from automation.models import Lead, IGAccount, SystemLog

logger = logging.getLogger(__name__)

class FastScraperBot:
    """
    Motor de Scraping Híbrido V4 (Persistencia de Enfriamiento).
    - Respeta tiempos de descanso entre ejecuciones distintas.
    - Evita quemar cuentas guardando su 'last_used' en base de datos.
    """

    NICHE_MAPPING = {
        "Salud & Medicina": ["medico", "doctor", "cirujano", "dentist", "nutricionista", "wellness", "salud"],
        "Real Estate": ["real estate", "bienes raices", "realtor", "arquitecto", "broker", "inmobiliaria"],
        "Negocios": ["ceo", "founder", "fundador", "entrepreneur", "consultant", "director", "dueño"],
        "Marketing": ["marketing", "ventas", "closer", "copywriter", "seo", "agency", "agencia"],
        "Coach": ["coach", "mentor", "trainer", "entrenador", "mindset"]
    }

    def __init__(self, initial_account_id=None):
        self.client = Client()
        self.current_account = None
        
        # --- CONFIGURACIÓN DE SEGURIDAD ---
        self.SAFETY_LIMIT_PER_ACCOUNT = 100  # Leads por sesión antes de rotar
        self.COOLDOWN_MINUTES = 30           # Tiempo mínimo de descanso entre usos
        self.current_account_usage = 0

        self.MIN_FOLLOWERS = 100
        self.MAX_FOLLOWERS = 500000
        self.MAX_CONSECUTIVE_EMPTY_BATCHES = 15

        if initial_account_id:
            try:
                self.current_account = IGAccount.objects.get(id=initial_account_id)
            except IGAccount.DoesNotExist:
                pass

    def log(self, msg, level='info'):
        print(f"[{level.upper()}] {msg}")
        try:
            SystemLog.objects.create(level=level, message=msg)
        except: pass 

    def _mark_account_as_used(self):
        """Guarda la hora actual en la BD para iniciar el enfriamiento"""
        if self.current_account:
            self.current_account.last_used = timezone.now()
            self.current_account.save()
            self.log(f"🧊 Cuenta {self.current_account.username} entra en enfriamiento ({self.COOLDOWN_MINUTES} min).", 'info')

    def _get_next_account(self):
        """
        Busca una cuenta activa que YA haya cumplido su tiempo de enfriamiento.
        """
        # 1. Si estábamos usando una, la marcamos como "usada ahora mismo"
        self._mark_account_as_used()

        # 2. Calcular el umbral de tiempo (ej: Ahora - 30 min)
        threshold = timezone.now() - timedelta(minutes=self.COOLDOWN_MINUTES)

        # 3. Filtrar candidatos:
        # - Status Active
        # - last_used es NULL (nunca usada) O last_used es anterior al umbral (ya descansó)
        candidates = IGAccount.objects.filter(status='active').filter(
            Q(last_used__isnull=True) | Q(last_used__lte=threshold)
        ).order_by('last_used') # Priorizar las que llevan más tiempo descansando

        if candidates.exists():
            # Tomamos la primera (la que más ha descansado)
            new_acc = candidates.first()
            
            old_name = self.current_account.username if self.current_account else 'Inicio'
            self.log(f"🔄 Rotación: {old_name} -> {new_acc.username} (Disponible)", 'warn')
            
            self.current_account = new_acc
            self.current_account_usage = 0 # Reiniciar contador local
            return True
        else:
            # Si no hay nadie listo, verificamos cuánto falta para la próxima
            next_available = IGAccount.objects.filter(status='active').order_by('last_used').last()
            wait_msg = "Indefinido"
            if next_available and next_available.last_used:
                free_time = next_available.last_used + timedelta(minutes=self.COOLDOWN_MINUTES)
                wait_seconds = (free_time - timezone.now()).total_seconds()
                if wait_seconds > 0:
                    wait_msg = f"{int(wait_seconds)} segundos"
            
            self.log(f"⏳ TODAS las cuentas están en enfriamiento. Próxima disponible en: {wait_msg}", 'error')
            
            # Opción A: Esperar un poco y reintentar (Recursivo con cuidado)
            # Opción B: Fallar para no bloquear el worker indefinidamente
            return False

    def login(self):
        """Autenticación segura con gestión de enfriamiento"""
        attempts = 0
        while attempts < 3: # Evitar bucles infinitos si todo falla
            if not self.current_account:
                if not self._get_next_account(): return False

            self.log(f"Autenticando: {self.current_account.username}...", 'info')
            
            if not self.current_account.session_id:
                self.log(f"Cuenta sin SessionID. Descartando.", 'warn')
                # La marcamos usada para que no vuelva a salir inmediatamente
                self._mark_account_as_used()
                self.current_account = None 
                continue

            try:
                self.client.login_by_sessionid(self.current_account.session_id)
                return True
            except Exception as e:
                self.log(f"Fallo Login ({e}). Rotando.", 'error')
                self._mark_account_as_used() # Marcar cooldown para no reintentar ya
                self.current_account = None
                attempts += 1
        
        return False

    def _calculate_engagement(self, user_id, followers):
        try:
            all_medias = self.client.user_medias_v1(user_id, amount=6)
            if len(all_medias) <= 3: target = all_medias
            else: target = all_medias[3:]

            if not target: return 0.0
            total = sum(m.like_count + m.comment_count for m in target)
            avg = total / len(target)
            return round((avg / followers) * 100, 2) if followers > 0 else 0.0
        except: return 0.0

    def _check_niche(self, bio_text):
        if not bio_text: return "-"
        bio_lower = bio_text.lower()
        for niche, kws in self.NICHE_MAPPING.items():
            if any(kw in bio_text.lower() for kw in kws): return niche
        return "-"

    def run(self, target_username, max_leads=50):
        self.log(f"⚡ Iniciando Scraping (Persistente): @{target_username}", 'warn')
        
        if not self.login():
            return "FAILED: Sin cuentas disponibles (Pool en enfriamiento)."

        leads_collected = 0
        consecutive_empty_batches = 0
        next_max_id = "" 
        target_id = None

        while leads_collected < max_leads:
            
            # 1. ROTACIÓN PREVENTIVA (Seguridad)
            if self.current_account_usage >= self.SAFETY_LIMIT_PER_ACCOUNT:
                self.log(f"Límite de seguridad alcanzado ({self.current_account_usage}). Rotando...", 'warn')
                if not self._get_next_account() or not self.login():
                    # Si no hay nadie más, guardamos estado y salimos
                    self._mark_account_as_used()
                    return f"PARTIAL SUCCESS: {leads_collected} leads (Pool agotado)."

            # 2. RESOLVER OBJETIVO
            if not target_id:
                try:
                    target_info = self.client.user_info_by_username_v1(target_username)
                    target_id = target_info.pk
                except Exception as e:
                    self.log(f"Error resolviendo objetivo. Rotando...", 'error')
                    if self._get_next_account() and self.login(): continue
                    else: return "FAILED: Objetivo inaccesible."

            # 3. EXTRACCIÓN
            try:
                users_chunk, next_max_id = self.client.user_followers_v1_chunk(
                    target_id, 
                    max_id=next_max_id, 
                    amount=40
                )

                if not users_chunk:
                    self.log("Fin de la lista de seguidores.", 'warn')
                    break

                batch_valid_leads = 0
                
                for user_short in users_chunk:
                    if leads_collected >= max_leads: break
                    
                    if Lead.objects.filter(ig_username=user_short.username).exists():
                        continue

                    time.sleep(random.uniform(3.0, 6.0))

                    try:
                        info = self.client.user_info_v1(user_short.pk)
                        self.current_account_usage += 1 
                        
                        if info.is_private: continue
                        if not (self.MIN_FOLLOWERS <= info.follower_count <= self.MAX_FOLLOWERS): continue
                        
                        niche = self._check_niche(info.biography)
                        eng_rate = self._calculate_engagement(info.pk, info.follower_count)
                        
                        self.log(f"@{info.username} | Eng: {eng_rate}%", 'info')

                        Lead.objects.create(
                            ig_username=info.username,
                            source_account=target_username,
                            data={
                                "full_name": info.full_name,
                                "followers": info.follower_count,
                                "niche": niche,
                                "engagement": eng_rate,
                                "bio": info.biography
                            },
                            status='to_contact'
                        )
                        leads_collected += 1
                        batch_valid_leads += 1
                        self.log(f"[GUARDADO] {leads_collected}/{max_leads}", 'success')
                        consecutive_empty_batches = 0 

                    except (LoginRequired, ChallengeRequired, RateLimitError, FeedbackRequired) as e:
                        self.log(f"Bloqueo ({e}). Rotando.", 'error')
                        if self._get_next_account() and self.login(): break 
                        else: return "FAILED: Enjambre agotado."
                    except Exception: continue

                if batch_valid_leads == 0:
                    consecutive_empty_batches += 1
                    if consecutive_empty_batches >= self.MAX_CONSECUTIVE_EMPTY_BATCHES:
                        self.log("Demasiados lotes vacíos. Deteniendo.", 'warn')
                        break
                
                if not next_max_id: break
                time.sleep(random.uniform(6, 12))

            except Exception as e:
                self.log(f"Error en lote: {e}. Rotando...", 'error')
                if self._get_next_account() and self.login(): continue
                else: return "FAILED: Error crítico."
        
        # AL FINALIZAR: Marcamos la última cuenta usada para que descanse
        self._mark_account_as_used()
        return f"SUCCESS: {leads_collected} leads"