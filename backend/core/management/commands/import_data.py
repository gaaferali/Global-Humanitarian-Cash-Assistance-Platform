import csv
import uuid
from decimal import Decimal
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import Beneficiary, Household, Program, Tenant
from core.services import run_deduplication_check

class Command(BaseCommand):
    help = 'مسار بيانات تلقائي (Data Pipeline) لاستيراد المستفيدين من ملفات CSV وتشغيل محركات الفحص فوراً'

    def add_arguments(self, parser):
        parser.add_argument('csv_file', type=str, help='مسار ملف الـ CSV المراد استيراده')

    def handle(self, *args, **options):
        csv_file_path = options['csv_file']
        self.stdout.write(self.style.WARNING(f"جاري قراءة الملف واستيراد البيانات من: {csv_file_path}..."))

        # جلب افتراضي للـ Tenant والـ Program والمستخدم لغرض العرض والتجربة
        tenant = Tenant.objects.first()
        program = Program.objects.first()
        User = get_user_model()
        admin_user = User.objects.first()

        if not tenant or not program:
            self.stdout.write(self.style.ERROR("خطأ: يجب توفر Tenant و Program في القاعدة أولاً!"))
            return

        imported_count = 0
        duplicates_flagged = 0

        try:
            with open(csv_file_path, mode='r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    # 1. إنشاء Household افتراضي أو ربطه
                    household, _ = Household.objects.get_or_create(
                        tenant=tenant,
                        program=program,
                        defaults={"status": "ACTIVE"}
                    )

                    # 2. إنشاء المستفيد الجديد مع رقم فريد تلقائي (number)
                    beneficiary = Beneficiary.objects.create(
                        household=household,
                        number=str(uuid.uuid4())[:8],  # رقم فريد لتفادي قيود الداتابيز
                        national_id_hash=row['national_id_hash'],
                        phone_last4=row['phone_last4'],
                        status="ACTIVE",
                        created_by=admin_user
                    )
                    imported_count += 1

                    # 3. التشغيل الفوري لمحرك كشف التكرار (AI Pipeline Integration)
                    is_duplicate = run_deduplication_check(beneficiary)
                    if is_duplicate:
                        duplicates_flagged += 1

            self.stdout.write(self.style.SUCCESS(
                f" تم بنجاح استيراد {imported_count} مستفيد، وتم رصد وتوليد تنبيهات لـ {duplicates_flagged} حالة تكرار محتملة أوتوماتيكياً!"
            ))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f" حدث خطأ أثناء معالجة مسار البيانات: {str(e)}"))