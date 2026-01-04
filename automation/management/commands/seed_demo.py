from django.core.management.base import BaseCommand
from django.utils import timezone

from automation.models import Agency, IGAccount, InteractionCampaign, InteractionTask


class Command(BaseCommand):
    help = "Crea datos de demostración para InteractionCampaign/InteractionTask."

    def handle(self, *args, **options):
        agency, _ = Agency.objects.get_or_create(
            name="Demo Agency",
            defaults={
                "plan_level": "demo",
                "is_active": True,
                "created_at": timezone.now(),
            },
        )

        accounts_data = ["demo_account_1", "demo_account_2"]
        accounts = []
        for username in accounts_data:
            account, _ = IGAccount.objects.get_or_create(
                username=username,
                agency=agency,
                defaults={
                    "status": "ACTIVE",
                    "session_id": "",
                    "created_at": timezone.now(),
                },
            )
            accounts.append(account)

        campaign, _ = InteractionCampaign.objects.get_or_create(
            agency=agency,
            name="Demo Campaign",
            defaults={
                "action": "COMMENT",
                "status": "QUEUED",
                "target_url": "https://www.instagram.com/p/XXXX/",
                "bot_count": len(accounts),
                "post_urls": ["https://www.instagram.com/p/XXXX/"],
                "comment_mode": "MANUAL",
                "manual_comments": "🔥 Excelente post!",
            },
        )

        created_tasks = []
        for account in accounts:
            for url in campaign.post_urls:
                task, created = InteractionTask.objects.get_or_create(
                    campaign=campaign,
                    agency=agency,
                    ig_account=account,
                    action="COMMENT",
                    post_url=url,
                    defaults={
                        "comment_text": "🔥 Excelente post!",
                        "status": "PENDING",
                    },
                )
                if created:
                    created_tasks.append(task)

        self.stdout.write(self.style.SUCCESS("Seed de demo listo."))
        self.stdout.write(f"Agency ID: {agency.id}")
        self.stdout.write("Accounts:")
        for acc in accounts:
            self.stdout.write(f" - {acc.username} ({acc.id}) | pega session_id reales en 'session_id' o session_id")
        self.stdout.write(f"Campaign ID: {campaign.id}")
        self.stdout.write("Tasks creadas:")
        for task in created_tasks:
            self.stdout.write(f" - {task.id} -> {task.post_url}")
        self.stdout.write("Recuerda actualizar la URL real y las session_id antes de correr 'python manage.py run_worker'.")
