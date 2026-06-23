import frappe
from frappe.utils import nowdate, cint


# --- 1) تحديث آخر طلب أُنشئ ---
@frappe.whitelist(allow_guest=True)
def update_last_application_status(payment_method=None):
    """يعدّل حالة آخر Journal_Application تم إنشاؤه إلى (مدفوع/قيد المراجعة)
    ويحدّث طريقة الدفع حسب اختيار المستخدم.
    """
    DOCTYPE = "Journal_Application"

    last = frappe.db.get_list(
        DOCTYPE,
        fields=["name"],
        order_by="creation desc",
        limit=1,
        ignore_permissions=True,
    )
    if not last:
        frappe.throw("طلب تقديم الفهرسة غير موجود", frappe.DoesNotExistError)

    app_name = last[0]["name"]
    doc = frappe.get_doc(DOCTYPE, app_name)

    # الحالات الأساسية
    doc.payment_status = "مدفوع (تجريبي)"
    doc.application_status = "قيد المراجعة"

    if not getattr(doc, "transaction_id", None):
        doc.transaction_id = frappe.generate_hash(length=10)

    # نحفظ تغييرات الحالة
    doc.save(ignore_permissions=True)

    # ✅ هنا نجبر تحديث حقل طريقة الدفع مباشرة في قاعدة البيانات
    if payment_method:
        frappe.db.set_value(
            DOCTYPE,
            app_name,
            "payment_method",   # اسم الحقل كما في الـ DocType
            payment_method,
            update_modified=True,  # يحدّث تاريخ التعديل
        )

    frappe.db.commit()

    return {
        "status": "success",
        "application_id": app_name,
        "payment_method": payment_method,
    }


# --- 2) هوك: إنشاء/تحديث مجلة عند قبول الطلب ---
def create_journal_on_acceptance(doc, method):
    """
    يُستدعى عند حفظ Journal_Application (يجب ربطه في hooks.py).
    إذا كانت حالة الطلب 'مقبول' ينشئ/يحدّث Journal_Dtp ويربطه بالطلب ثم يعيّن الطلب 'تم الفهرسة'.
    """
    APP_DTYPE = "Journal_Application"
    JRNL_DTYPE = "Journal_Dtp"

    if doc.doctype != APP_DTYPE:
        return

    if doc.application_status != "مقبول":
        return

    # تحصين ضد التكرار: نفس الطلب مُعالَج مسبقًا
    existing = frappe.db.exists(JRNL_DTYPE, {"application_reference": doc.name})
    if existing:
        frappe.msgprint(f"تم تسجيل المجلة لطلب رقم {doc.name} مسبقاً.")
        return

    # تحصين آخر: نفس السجل كان 'مقبول' قبل الحفظ السابق
    before = doc.get_doc_before_save()
    if before and before.application_status == "مقبول":
        return

    try:
        # إن وُجدت مجلّة بنفس الاسم حدّثها، وإلا أنشئ جديدة
        same_name = frappe.db.exists(JRNL_DTYPE, {"journal_name": doc.journal_name})
        if same_name:
            j = frappe.get_doc(JRNL_DTYPE, same_name)
            created_new = False
        else:
            j = frappe.new_doc(JRNL_DTYPE)
            j.journal_name = doc.journal_name
            created_new = True

        # نسخ/تحديث الحقول
        j.print_issn            = doc.print_issn
        j.online_issn           = doc.online_issn
        j.institution           = doc.institution         # Link -> Institution_Dtp
        j.specialization        = doc.specialization      # Select (نفس خيارات الدوكتايب)
        j.language              = doc.language            # Select
        j.index_status          = doc.application_status  # هنا ستكون "مقبول"
        j.publishing_frequency  = doc.publishing_frequency
        j.impact_factor         = doc.impact_factor
        j.journal_url           = doc.journal_url
        j.founding_year         = doc.founding_year
        j.application_reference = doc.name
        j.indexing_date         = nowdate()

        if created_new:
            j.insert(ignore_permissions=True)
        else:
            j.save(ignore_permissions=True)

        # بعدها: حوّلي حالة الطلب إلى "تم الفهرسة"
        frappe.db.set_value(APP_DTYPE, doc.name, "application_status", "تم الفهرسة", update_modified=False)
        frappe.db.commit()

        frappe.msgprint(f"تمت الفهرسة بنجاح. سجل المجلة رقم {j.name} تم {'إنشاؤه' if created_new else 'تحديثه'}.")

    except Exception:
        frappe.log_error(title="Journal Creation Error", message=frappe.get_traceback())
        frappe.throw("حدث خطأ في عملية الفهرسة. راجعي الـ Error Log.")


# # --- 3) API عامة: إرجاع قائمة مجلات للواجهة العامة مع بحث/ترقيم ---
# @frappe.whitelist(allow_guest=True)
# def get_journals_public_list(page=1, search_term=None, specialization_filter=None):
#     """
#     تعيد Journals (Journal_Dtp) للعرض العام مع بحث وتصفّح.
#     - search_term: يُطبَّق على journal_name و institution (الاسم النصي المخزن)
#     - specialization_filter: يطبّق فلتر دقيق على specialization
#     """
#     DOCTYPE = "Journal_Dtp"

#     page = cint(page) or 1
#     page_size = 10
#     start_at = (page - 1) * page_size

#     fields = [
#         "name",
#         "journal_name",
#         "print_issn",
#         "online_issn",
#         "institution",
#         "specialization",
#         "language",
#         "publishing_frequency",
#         "journal_url",
#         "impact_factor",
#     ]

#     filters = {}
#     if specialization_filter:
#         filters["specialization"] = specialization_filter

#     or_filters = None
#     if search_term:
#         like = f"%{search_term}%"
#         or_filters = [
#             ["journal_name", "like", like],
#             ["institution_name", "like", like],
#         ]

#     # النتائج (مرتّبة حسب التأثير تنازليًا ثم الاسم)
#     journals = frappe.get_all(
#         DOCTYPE,
#         fields=fields,
#         filters=filters,
#         or_filters=or_filters,
#         limit_start=start_at,
#         limit_page_length=page_size,
#         order_by="ifnull(impact_factor, 0) desc, journal_name asc",
#     )

#     # العدّ الكلي (لو فيه search_term نعد بنفس or_filters لضبط الترقيم)
#     if or_filters:
#         total_count = len(
#             frappe.get_all(
#                 DOCTYPE,
#                 filters=filters,
#                 or_filters=or_filters,
#                 pluck="name",
#             )
#         )
#     else:
#         total_count = frappe.db.count(DOCTYPE, filters=filters)
        
#     # استبدال معرّف الجهة بالاسم النصّي قبل الإرجاع (عرض فقط)
#     for j in journals:
#         inst_id = j.get("institution")
#         if inst_id:
#             inst_name = frappe.db.get_value("Institution_Dtp", inst_id, "institution_name")
#             if inst_name:
#                 j["institution"] = inst_name

#     return {
#     "status": "ok",
#     "page": page,
#     "page_size": page_size,
#     "total_count": total_count,
#     "journals": journals,
#     }


# --- 3) API عامة: إرجاع قائمة مجلات للواجهة العامة مع بحث/ترقيم ---
@frappe.whitelist(allow_guest=True)
def get_journals_public_list(page=1, search_term=None, specialization_filter=None):
    """
    تعيد Journals (Journal_Dtp) للعرض العام مع بحث وتصفّح.
    - search_term: يُطبَّق على journal_name وأسماء الجهات عبر Institution_Dtp
    - specialization_filter: يطبّق فلتر دقيق على specialization
    """
    DOCTYPE = "Journal_Dtp"

    page = cint(page) or 1
    page_size = 10
    start_at = (page - 1) * page_size

    fields = [
        "name",
        "journal_name",
        "print_issn",
        "online_issn",
        "institution",            # هذا هو الـ Link (ID)
        "specialization",
        "language",
        "publishing_frequency",
        "journal_url",
        "impact_factor",
    ]

    filters = {}
    if specialization_filter:
        filters["specialization"] = specialization_filter

    # ------ بناء شروط البحث بشكل صحيح ------
    or_filters = None
    if search_term:
        like = f"%{search_term}%"

        # 1) ابحث عن المجلات بالاسم
        or_filters = [["journal_name", "like", like]]

        # 2) ابحث عن الجهات بالاسم في Institution_Dtp ثم فلتر Journal_Dtp.institution بها
        inst_ids = frappe.get_all(
            "Institution_Dtp",
            filters=[["institution_name", "like", like]],
            pluck="name",
        )
        if inst_ids:
            or_filters.append(["institution", "in", inst_ids])

    # النتائج (مرتّبة حسب التأثير تنازليًا ثم الاسم)
    journals = frappe.get_all(
        DOCTYPE,
        fields=fields,
        filters=filters,
        or_filters=or_filters,
        limit_start=start_at,
        limit_page_length=page_size,
        order_by="ifnull(impact_factor, 0) desc, journal_name asc",
    )

    # العدّ الكلي (طابقي نفس منطق or_filters)
    if or_filters:
        total_count = len(
            frappe.get_all(
                DOCTYPE,
                filters=filters,
                or_filters=or_filters,
                pluck="name",
            )
        )
    else:
        total_count = frappe.db.count(DOCTYPE, filters=filters)

    # ------ استبدال معرّف الجهة بالاسم للعرض فقط ------
    # اجمع IDs الظاهرة ثم هاتِ الأسماء دفعة واحدة (أسرع من get_value داخل لوب)
    inst_ids_in_result = list({j["institution"] for j in journals if j.get("institution")})
    name_map = {}
    if inst_ids_in_result:
        rows = frappe.get_all(
            "Institution_Dtp",
            filters=[["name", "in", inst_ids_in_result]],
            fields=["name", "institution_name"],
        )
        name_map = {r["name"]: (r.get("institution_name") or r["name"]) for r in rows}

    for j in journals:
        inst_id = j.get("institution")
        if inst_id:
            j["institution"] = name_map.get(inst_id, inst_id)  # fallback للـID لو ما وُجد اسم

    return {
        "status": "ok",
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "journals": journals,
    }
