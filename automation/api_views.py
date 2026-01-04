import json

from django.db import transaction
from django.http import HttpResponseNotAllowed, JsonResponse
from django.utils.timezone import now
from django.views.decorators.csrf import csrf_exempt

from .models import Agency, IGAccount, InteractionCampaign, InteractionTask


def _json_body(request):
    try:
        return json.loads(request.body.decode("utf-8") or "{}")
    except Exception:
        return {}


@csrf_exempt
def bots_list_create(request):
    if request.method == "GET":
        bots = IGAccount.objects.all().order_by("-created_at")
        data = [
            {
                "id": str(b.id),
                "username": b.username,
                "status": b.status,
                "has_session_id": bool(getattr(b, "session_id", "") or ""),
                "created_at": b.created_at.isoformat() if getattr(b, "created_at", None) else None,
            }
            for b in bots
        ]
        return JsonResponse(data, safe=False)

    if request.method == "POST":
        body = _json_body(request)
        username = (body.get("username") or "").strip()
        status = (body.get("status") or "ACTIVE").strip() or "ACTIVE"
        session_id = (body.get("session_id") or "").strip()

        if not username:
            return JsonResponse({"error": "username is required"}, status=400)

        agency_id = body.get("agency_id")
        agency = None
        if agency_id:
            try:
                agency = Agency.objects.get(id=agency_id)
            except Agency.DoesNotExist:
                return JsonResponse({"error": "agency not found"}, status=404)
        else:
            agency = Agency.objects.first()

        if agency is None:
            return JsonResponse({"error": "No agency available to attach account"}, status=400)

        bot = IGAccount.objects.create(
            agency=agency,
            username=username,
            status=status,
            session_id=session_id,
            created_at=now(),
        )

        return JsonResponse(
            {
                "id": str(bot.id),
                "username": bot.username,
                "status": bot.status,
                "session_id": bot.session_id or "",
            },
            status=201,
        )

    return HttpResponseNotAllowed(["GET", "POST"])


@csrf_exempt
def bots_patch(request, bot_id):
    if request.method != "PATCH":
        return HttpResponseNotAllowed(["PATCH"])

    body = _json_body(request)
    try:
        bot = IGAccount.objects.get(id=bot_id)
    except IGAccount.DoesNotExist:
        return JsonResponse({"error": "Bot not found"}, status=404)

    update_fields = []

    if "status" in body:
        bot.status = (body.get("status") or bot.status).strip() or bot.status
        update_fields.append("status")

    if "session_id" in body:
        bot.session_id = (body.get("session_id") or "").strip()
        update_fields.append("session_id")

    if update_fields:
        bot.save(update_fields=update_fields)

    return JsonResponse(
        {
            "id": str(bot.id),
            "username": bot.username,
            "status": bot.status,
            "session_id": bot.session_id or "",
        }
    )


@csrf_exempt
def campaigns_list_create(request):
    if request.method == "GET":
        campaigns = InteractionCampaign.objects.all().order_by("-created_at")
        data = [
            {
                "id": str(c.id),
                "name": c.name,
                "status": c.status,
                "action": c.action,
                "created_at": c.created_at.isoformat() if c.created_at else None,
            }
            for c in campaigns
        ]
        return JsonResponse(data, safe=False)

    if request.method == "POST":
        body = _json_body(request)
        action = (body.get("action") or "COMMENT").strip().upper()
        post_url = (body.get("post_url") or "").strip()
        comment_text = (body.get("comment_text") or "").strip()
        ig_account_ids = body.get("ig_account_ids") or []

        if action not in ("COMMENT", "LIKE"):
            return JsonResponse({"error": "action must be COMMENT or LIKE"}, status=400)
        if not post_url:
            return JsonResponse({"error": "post_url is required"}, status=400)
        if action == "COMMENT" and not comment_text:
            return JsonResponse({"error": "comment_text is required for COMMENT"}, status=400)
        if not ig_account_ids:
            return JsonResponse({"error": "ig_account_ids is required"}, status=400)

        agency_id = body.get("agency_id")
        agency = None
        if agency_id:
            try:
                agency = Agency.objects.get(id=agency_id)
            except Agency.DoesNotExist:
                return JsonResponse({"error": "agency not found"}, status=404)
        else:
            agency = Agency.objects.first()

        if agency is None:
            return JsonResponse({"error": "No agency available to attach campaign"}, status=400)

        with transaction.atomic():
            campaign = InteractionCampaign.objects.create(
                agency=agency,
                name=body.get("name") or f"Campaign {now().strftime('%Y-%m-%d %H:%M')}",
                status="QUEUED",
                action=action,
                post_urls=[post_url],
            )

            bots = IGAccount.objects.filter(id__in=ig_account_ids)
            if not bots.exists():
                return JsonResponse({"error": "No IG accounts found for ig_account_ids"}, status=400)

            for bot in bots:
                InteractionTask.objects.create(
                    agency=agency,
                    campaign=campaign,
                    ig_account=bot,
                    action=action,
                    post_url=post_url,
                    comment_text=comment_text if action == "COMMENT" else "",
                    status="PENDING",
                )

        return JsonResponse({"id": str(campaign.id)}, status=201)

    return HttpResponseNotAllowed(["GET", "POST"])


def campaigns_detail(request, campaign_id):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    try:
        campaign = InteractionCampaign.objects.get(id=campaign_id)
    except InteractionCampaign.DoesNotExist:
        return JsonResponse({"error": "Campaign not found"}, status=404)

    return JsonResponse(
        {
            "id": str(campaign.id),
            "name": campaign.name,
            "status": campaign.status,
            "action": campaign.action,
            "created_at": campaign.created_at.isoformat() if campaign.created_at else None,
        }
    )


def tasks_list(request):
    if request.method != "GET":
        return HttpResponseNotAllowed(["GET"])

    campaign_id = request.GET.get("campaign_id")
    tasks = InteractionTask.objects.select_related("ig_account").all().order_by("-created_at")
    if campaign_id:
        tasks = tasks.filter(campaign_id=campaign_id)

    data = [
        {
            "id": str(t.id),
            "campaign_id": str(t.campaign_id) if t.campaign_id else None,
            "ig_account_id": str(t.ig_account_id) if t.ig_account_id else None,
            "ig_account_username": t.ig_account.username if t.ig_account_id else None,
            "action": t.action,
            "status": t.status,
            "attempts": t.attempts,
            "result_message": t.result_message,
            "error_code": t.error_code,
        }
        for t in tasks
    ]
    return JsonResponse(data, safe=False)
