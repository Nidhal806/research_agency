import frappe
from frappe.utils import nowdate, cint

# --- 2) هوك: إنشاء/تحديث مجلة عند قبول الطلب ---
import frappe
from frappe.utils import nowdate, now_datetime

def create_journal_on_acceptance(doc, method):
    """
    يُستدعى عند حفظ Journal_Application.
    عند انتقال حالة الطلب إلى (مقبول):
    - ينشئ أو يحدّث Journal_Dtp
    - يثبت اسم الجهة الناشرة كنص
    - يربط المجلة بالطلب
    - يحوّل حالة الطلب إلى (تم الفهرسة)
    """

    APP_DTYPE = "Journal_Application"
    JRNL_DTYPE = "Journal_Dtp"

    # تحصين أساسي
    if doc.doctype != APP_DTYPE:
        return

    if doc.application_status != "مقبول":
        return

    # تحصين ضد التكرار: الطلب مُعالج مسبقًا
    existing = frappe.db.exists(JRNL_DTYPE, {
        "application_reference": doc.name
    })
    if existing:
        return

    # تحصين: كان مقبولًا قبل هذا الحفظ
    before = doc.get_doc_before_save()
    if before and before.application_status == "مقبول":
        return

    try:
        # إنشاء أو تحديث المجلة
        same_name = frappe.db.exists(
            JRNL_DTYPE,
            {"journal_name": doc.journal_name}
        )

        if same_name:
            j = frappe.get_doc(JRNL_DTYPE, same_name)
            created_new = False
        else:
            j = frappe.new_doc(JRNL_DTYPE)
            j.journal_name = doc.journal_name
            created_new = True

        # نسخ الحقول من الطلب
        j.print_issn            = doc.print_issn
        j.online_issn           = doc.online_issn
        j.institution           = doc.institution            # Link
        j.specialization        = doc.specialization
        j.language              = doc.language
        j.index_status          = doc.application_status     # "مقبول"
        j.publishing_frequency  = doc.publishing_frequency
        j.impact_factor         = doc.impact_factor
        j.journal_url           = doc.journal_url
        j.founding_year         = doc.founding_year
        j.application_reference = doc.name
        j.indexing_date         = nowdate()

        # ✅ تثبيت اسم الجهة الناشرة كنص داخل المجلة
        inst_name = frappe.db.get_value(
            "Institution_Dtp",
            doc.institution,
            "institution_name"
        )
        j.institution_name = inst_name

        # حفظ المجلة
        if created_new:
            j.insert(ignore_permissions=True)
        else:
            j.save(ignore_permissions=True)

        # تثبيت الأثر داخل الطلب
        frappe.db.set_value(
            APP_DTYPE,
            doc.name,
            {
                "indexed_on": now_datetime(),
                "indexed_journal": j.name,
                "indexed_by": frappe.session.user,
            },
            update_modified=False
        )

        # تحويل حالة الطلب إلى (تم الفهرسة)
        frappe.db.set_value(
            APP_DTYPE,
            doc.name,
            "application_status",
            "تم الفهرسة",
            update_modified=False
        )

        frappe.db.commit()

    except Exception:
        frappe.log_error(
            title="Journal Creation Error",
            message=frappe.get_traceback()
        )
        frappe.throw("حدث خطأ في عملية الفهرسة. راجعي سجل الأخطاء.")



# --- 3) API عامة: إرجاع قائمة مجلات للواجهة العامة مع بحث/ترقيم ---
@frappe.whitelist(allow_guest=True)
def get_journals_public_list(
    page=1,
    page_size=20,
    search_term=None,
    specialization_filter=None,
    institution_filter=None
):
    from frappe.utils import cint

    page = cint(page) or 1
    page_size = cint(page_size) or 20
    start_at = (page - 1) * page_size

    # --------------------------------------------------
    # 1️⃣ المجلّات التي لديها مقالات فقط
    # --------------------------------------------------
    journals_with_articles = frappe.get_all(
        "Article_Metadata_Dtp",
        fields=["journal"],
        group_by="journal",
        pluck="journal"
    )

    if not journals_with_articles:
        return {
            "status": "ok",
            "page": page,
            "page_size": page_size,
            "total_count": 0,
            "journals": [],
        }

    # --------------------------------------------------
    # 2️⃣ الفلاتر الأساسية
    # --------------------------------------------------
    filters = {
        "name": ["in", journals_with_articles]
    }

    if specialization_filter and specialization_filter != "الكل":
        filters["specialization"] = specialization_filter

    if institution_filter:
        filters["institution_name"] = ["like", f"%{institution_filter}%"]

    # --------------------------------------------------
    # 3️⃣ البحث العام
    # --------------------------------------------------
    or_filters = None
    if search_term:
        like = f"%{search_term}%"
        or_filters = [
            ["journal_name", "like", like],
            ["institution_name", "like", like],
        ]

    # --------------------------------------------------
    # 4️⃣ جلب النتائج
    # --------------------------------------------------
    journals = frappe.get_all(
        "Journal_Dtp",
        fields=[
            "name",
            "journal_name",
            "print_issn",
            "online_issn",
            "institution_name",
            "specialization",
            "language",
            "publishing_frequency",
            "journal_url",
            "impact_factor",
        ],
        filters=filters,
        or_filters=or_filters,
        order_by="ifnull(impact_factor,0) desc, journal_name asc",
        limit_start=start_at,
        limit_page_length=page_size,
    )

    # --------------------------------------------------
    # 5️⃣ حساب عدد المقالات لكل مجلة
    # --------------------------------------------------
    for j in journals:
        j["article_count"] = frappe.db.count(
            "Article_Metadata_Dtp",
            {"journal": j["name"]}
        )

    # --------------------------------------------------
    # 6️⃣ العدد الكلي
    # --------------------------------------------------
    if or_filters:
        total_count = len(
            frappe.get_all(
                "Journal_Dtp",
                filters=filters,
                or_filters=or_filters,
                pluck="name"
            )
        )
    else:
        total_count = frappe.db.count("Journal_Dtp", filters=filters)

    return {
        "status": "ok",
        "page": page,
        "page_size": page_size,
        "total_count": total_count,
        "journals": journals,
    }
  


from frappe.utils import format_datetime

@frappe.whitelist(allow_guest=True)
def get_application_public_status(application_id: str):
    if not application_id:
        return {"application_id": None}

    row = frappe.db.get_value(
        "Journal_Application",
        application_id,
        ["name", "application_status", "payment_status", "payment_method", "creation", "modified",
         "indexed_on", "indexed_journal", "indexed_by"],
        as_dict=True
    )

    if not row:
        return {"application_id": None}

    # ✅ مؤسساتي: تاريخ الفهرسة من الطلب نفسه
    indexing_date = row.get("indexed_on")

    # fallback اختياري: لو indexed_on فارغ لكن عندنا مرجع مجلة
    if not indexing_date and row.get("indexed_journal"):
        indexing_date = frappe.db.get_value("Journal_Dtp", row["indexed_journal"], "indexing_date")

    return {
        "application_id": row.get("name"),
        "application_status": row.get("application_status"),
        "payment_status": row.get("payment_status"),
        "payment_method": row.get("payment_method"),
        "created_on": format_datetime(row.get("creation")) if row.get("creation") else None,
        "modified_on": format_datetime(row.get("modified")) if row.get("modified") else None,
        "indexing_date": format_datetime(indexing_date) if indexing_date else None,
        "indexed_journal": row.get("indexed_journal"),
        "indexed_by": row.get("indexed_by"),
    }

@frappe.whitelist(allow_guest=True)
def update_application_status(application_id, payment_method=None):
    DOCTYPE = "Journal_Application"

    if not application_id:
        frappe.throw("رقم الطلب مطلوب")

    if not frappe.db.exists(DOCTYPE, application_id):
        frappe.throw("رقم الطلب غير موجود", frappe.DoesNotExistError)

    doc = frappe.get_doc(DOCTYPE, application_id)

    # ✅ حماية من تكرار الدفع
    if (doc.payment_status or "").strip() == "مدفوع (تجريبي)":
        return {
            "status": "already_paid",
            "application_id": doc.name,
            "payment_method": doc.payment_method,
        }

    # تحديث حالات الدفع
    doc.payment_status = "مدفوع (تجريبي)"
    doc.application_status = "قيد المراجعة"

    if payment_method:
        doc.payment_method = payment_method

    if not getattr(doc, "transaction_id", None):
        doc.transaction_id = frappe.generate_hash(length=10)

    doc.save(ignore_permissions=True)
    frappe.db.commit()

    return {
        "status": "success",
        "application_id": doc.name,
        "payment_method": doc.payment_method,
    }


import random, string
from frappe.utils import now_datetime

def _gen_iix():
    yymm = now_datetime().strftime("%y%m")
    rnd  = ''.join(random.choice(string.digits) for _ in range(5))
    return f"IIX-{yymm}-{rnd}"

@frappe.whitelist(allow_guest=True)
def get_new_public_code():
    # جرّبي حتى 10 مرات لتفادي تصادم نادر
    for _ in range(10):
        code = _gen_iix()
        # تأكد غير مستخدم في الحقل
        if not frappe.db.exists("Journal_Application", {"public_code": code}):
            return {"code": code}
    frappe.throw("تعذّر توليد رقم فريد الآن. أعِد المحاولة.")

@frappe.whitelist(allow_guest=True)
def resolve_application_id(application_id: str):
    """يرجع doc.name سواء كان الإدخال public_code (IIX-...) أو الاسم الداخلي."""
    if not application_id:
        return {"name": None}

    # إذا كان بالصيغة العامة IIX-.. نبحث بالـ public_code
    if application_id.startswith("IIX-"):
        name = frappe.db.get_value("Journal_Application", {"public_code": application_id}, "name")
    else:
        # قد يكون أُرسل الاسم الداخلي نفسه
        name = application_id if frappe.db.exists("Journal_Application", application_id) else None

    return {"name": name}


@frappe.whitelist(allow_guest=True)
def get_journal_details_public(journal, page=1, page_size=10, search=None):
    """
    API عامة لصفحة تفاصيل المجلة (Public Journal Details)

    - journal: name (ID) للمجلة
    - page / page_size: ترقيم المقالات
    - search: بحث في عنوان المقال + أسماء المؤلفين
    """

    from frappe.utils import cint

    if not journal:
        frappe.throw("معرّف المجلة مطلوب")

    if not frappe.db.exists("Journal_Dtp", journal):
        frappe.throw("المجلة غير موجودة")

    page = cint(page) or 1
    page_size = cint(page_size) or 10
    start = (page - 1) * page_size

    # ------------------------------------------------------------------
    # 1) بيانات المجلة الأساسية (Snapshot)
    # ------------------------------------------------------------------
    j = frappe.get_doc("Journal_Dtp", journal)

    journal_data = {
        "name": j.name,
        "journal_name": j.journal_name,
        "institution": j.institution_name,          # ✅ نص ثابت
        "print_issn": j.print_issn,
        "online_issn": j.online_issn,
        "specialization": j.specialization,
        "language": j.language,
        "publishing_frequency": j.publishing_frequency,
        "impact_factor": j.impact_factor,
        "founding_year": j.founding_year,
        "indexing_date": j.indexing_date,
        "journal_url": j.journal_url,
    }

    # ------------------------------------------------------------------
    # 2) إحصاءات سريعة
    # ------------------------------------------------------------------
    articles_count = frappe.db.count(
        "Article_Metadata_Dtp",
        {"journal": journal}
    )

    batches_count = frappe.db.count(
        "Journal_Intake_Batch_Dtp",
        {"journal": journal}
    )

    last_intake = frappe.db.get_value(
        "Journal_Intake_Batch_Dtp",
        {"journal": journal},
        "max(intake_date)"
    )

    stats = {
        "articles": articles_count,
        "batches": batches_count,
        "last_intake": last_intake,
    }

    # ------------------------------------------------------------------
    # 3) المؤلفون (تجميع نصي – منهج Scopus)
    # ------------------------------------------------------------------
    authors_rows = frappe.get_all(
        "Article_Metadata_Dtp",
        filters={"journal": journal},
        fields=["authors_text"]
    )

    authors_map = {}
    for r in authors_rows:
        if not r.authors_text:
            continue
        for name in [a.strip() for a in r.authors_text.split("؛")]:
            if not name:
                continue
            authors_map[name] = authors_map.get(name, 0) + 1

    authors_list = [
        {"name": k, "count": v}
        for k, v in sorted(authors_map.items(), key=lambda x: x[0])
    ]

    # ------------------------------------------------------------------
    # 4) المقالات + بحث + Pagination
    # ------------------------------------------------------------------
    filters = {"journal": journal}
    or_filters = []

    if search:
        like = f"%{search}%"
        or_filters = [
            ["article_title", "like", like],
            ["authors_text", "like", like],
        ]

    articles = frappe.get_all(
        "Article_Metadata_Dtp",
        filters=filters,
        or_filters=or_filters if search else None,
        fields=[
            "article_title",
            "authors_text",
            "publication_date",
            "volume",
            "issue",
            "doi",
            "article_url",
        ],
        order_by="publication_date desc",
        limit_start=start,
        limit_page_length=page_size,
    )

    if search:
        total_articles = len(
            frappe.get_all(
                "Article_Metadata_Dtp",
                filters=filters,
                or_filters=or_filters,
                pluck="name"
            )
        )
    else:
        total_articles = articles_count

    # ------------------------------------------------------------------
    # 5) الاستجابة النهائية
    # ------------------------------------------------------------------
    return {
        "journal": journal_data,
        "stats": stats,
        "authors": authors_list,
        "articles": articles,
        "page": page,
        "page_size": page_size,
        "total": total_articles,
    }

import requests
import xml.etree.ElementTree as ET

@frappe.whitelist()
def oai_list_sets(oai_base_url: str):
    """
    يجلب جميع التخصصات (ListSets) من OAI-PMH
    مثال:
    https://ijs.uobaghdad.edu.iq/index.php/eijs/oai
    """

    if not oai_base_url:
        frappe.throw("OAI Base URL مطلوب")

    url = f"{oai_base_url}?verb=ListSets"

    try:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        frappe.throw(f"فشل الاتصال بـ OAI: {e}")

    # Parse XML
    ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}
    root = ET.fromstring(resp.text)

    sets = []

    for s in root.findall(".//oai:set", ns):
        set_spec = s.find("oai:setSpec", ns)
        set_name = s.find("oai:setName", ns)

        if set_spec is not None and set_name is not None:
            sets.append({
                "setSpec": set_spec.text,   # eijs:Chemistry
                "setName": set_name.text    # Chemistry
            })

    return {
        "status": "ok",
        "count": len(sets),
        "sets": sets
    }


import requests
import xml.etree.ElementTree as ET
import re


@frappe.whitelist()
def oai_list_records_full(oai_base_url: str, set_spec: str):

    if not oai_base_url or not set_spec:
        frappe.throw("OAI Base URL و setSpec مطلوبان")

    ns = {
        "oai": "http://www.openarchives.org/OAI/2.0/",
        "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
        "dc": "http://purl.org/dc/elements/1.1/"
    }

    records = []
    resumption_token = None

    while True:
        if resumption_token:
            url = f"{oai_base_url}?verb=ListRecords&resumptionToken={resumption_token}"
        else:
            url = (
                f"{oai_base_url}"
                f"?verb=ListRecords"
                f"&metadataPrefix=oai_dc"
                f"&set={set_spec}"
            )

        resp = requests.get(url, timeout=60)
        resp.raise_for_status()

        clean_xml = _safe_xml(resp.text)
        root = ET.fromstring(clean_xml)

        for rec in root.findall(".//oai:record", ns):

            header = rec.find("oai:header", ns)
            if header is not None and header.get("status") == "deleted":
                continue

            meta = rec.find(".//oai_dc:dc", ns)
            if meta is None:
                continue

            # -----------------------------
            # 🔹 identifiers
            # -----------------------------
            identifiers = [
                e.text.strip()
                for e in meta.findall("dc:identifier", ns)
                if e.text and e.text.strip()
            ]

            doi = next((i for i in identifiers if i.startswith("10.")), None)

            # 🔥 اختيار الرابط الصحيح (ليس PDF)
            article_url = next(
                (i for i in identifiers if i.startswith("http") and "view" in i),
                None
            ) or next(
                (i for i in identifiers if i.startswith("http")),
                None
            )

            # 🔥 استخراج PDF
            pdf_url = next(
                (i for i in identifiers if i.endswith(".pdf")),
                None
            )

            # -----------------------------
            # 🔹 المصدر
            # -----------------------------
            source_text = meta.findtext("dc:source", default="", namespaces=ns)

            volume = issue = pages = None
            if source_text:
                vol_match = re.search(r"Vol\s+(\d+)", source_text)
                issue_match = re.search(r"No\s+([^\s\(\);]+)", source_text)
                pages_match = re.search(r";\s*([\d\-–]+)$", source_text)

                volume = vol_match.group(1) if vol_match else None
                issue = issue_match.group(1) if issue_match else None
                pages = pages_match.group(1) if pages_match else None

            # -----------------------------
            # 🔹 العنوان
            # -----------------------------
            title = meta.findtext("dc:title", default="", namespaces=ns).strip()
            article_title = title if title else "Untitled Article"

            # -----------------------------
            # 🔹 المؤلفين
            # -----------------------------
            authors = [
                e.text.strip()
                for e in meta.findall("dc:creator", ns)
                if e.text and e.text.strip()
            ]
            authors_text = "؛ ".join(authors) if authors else "غير مذكور"

            # -----------------------------
            # 🔹 التاريخ
            # -----------------------------
            pub_date = meta.findtext("dc:date", default=None, namespaces=ns)
            publication_date = pub_date.strip() if pub_date and pub_date.strip() else None

            # -----------------------------
            # 🔹 keywords + subject
            # -----------------------------
            subjects = [
                e.text.strip()
                for e in meta.findall("dc:subject", ns)
                if e.text and e.text.strip()
            ]

            subject_raw = " | ".join(subjects) if subjects else None
            keywords = "، ".join(subjects) if subjects else None

            # -----------------------------
            # 🔹 abstract
            # -----------------------------
            abstract = meta.findtext("dc:description", default="", namespaces=ns)

            # -----------------------------
            # 🔹 اللغة
            # -----------------------------
            language = meta.findtext("dc:language", default="", namespaces=ns)

            # -----------------------------
            # 🔹 بناء السجل
            # -----------------------------
            record = {
                "journal": None,
                "article_specialization": set_spec,

                "article_title": article_title,
                "authors_text": authors_text,
                "abstract": abstract,
                "publication_date": publication_date,

                "article_url": article_url,
                "doi": doi,
                "pdf_url": pdf_url,

                "volume": volume,
                "issue": issue,
                "pages": pages,

                "language": language,
                "source": source_text,

                # 🔥 الجديد
                "keywords": keywords,
                "subject_raw": subject_raw,
            }

            records.append(record)

        token_el = root.find(".//oai:resumptionToken", ns)
        if token_el is None or not token_el.text:
            break

        resumption_token = token_el.text.strip()

    return {
        "status": "ok",
        "setSpec": set_spec,
        "count": len(records),
        "records": records
    }



def _safe_text(value, max_len):
    if not value:
        return value
    return value[:max_len]



def _safe_xml(text: str) -> str:
    """
    ينظف XML من محارف غير صالحة
    """
    if not text:
        return text

    # إزالة محارف التحكم غير المسموحة في XML 1.0
    return ''.join(
        c for c in text
        if (
            c == '\t' or
            c == '\n' or
            c == '\r' or
            ord(c) >= 32
        )
    )



import pandas as pd
from frappe.utils import nowdate
from research_agency.api import oai_list_sets, oai_list_records_full

@frappe.whitelist()
def harvest_oai_to_excel(oai_base_url: str, set_spec: str = None):
    """
    يحصد OAI-PMH → ويولّد Excel فقط
    """

    if not oai_base_url:
        frappe.throw("OAI Base URL مطلوب")

    exported_files = []

    if set_spec:
        sets = [{"setSpec": set_spec}]
    else:
        sets = oai_list_sets(oai_base_url).get("sets", [])
        if not sets:
            frappe.throw("لم يتم العثور على أي تخصصات")

    for s in sets:
        spec = s["setSpec"]

        data = oai_list_records_full(oai_base_url, spec)
        records = data.get("records", [])
        if not records:
            continue

        set_name = s.get("setName") or spec

        for r in records:
            r["harvest_date"] = nowdate()
            r["oai_set_name"] = set_name

        df = pd.DataFrame(records)[[
            "article_title",
            "authors_text",
            "abstract",
            "publication_date",
            "doi",
            "article_url",
            "volume",
            "issue",
            "pages",
            "language",
            "article_specialization",
            "oai_set_name",
            "harvest_date",
            "source"
        ]]

        filename = f"OAI_{spec.replace(':', '_')}_{nowdate()}.xlsx"
        path = f"/private/files/{filename}"
        full = frappe.get_site_path(path.strip("/"))
        df.to_excel(full, index=False)

        exported_files.append({
            "setSpec": spec,
            "articles_count": len(df),
            "file": path
        })

    return {
        "status": "ok",
        "sets_exported": len(exported_files),
        "files": exported_files
    }


import math

def _clean(value):
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    value = str(value).strip()
    return value if value else None


import pandas as pd
from frappe.utils import nowdate
from frappe.model.document import Document


@frappe.whitelist()
def ingest_articles_from_excel(ingestion_doc: str):

    doc = frappe.get_doc("Article_Ingestion_Dtp", ingestion_doc)

    if not doc.metadata_file:
        frappe.throw("ملف الميتاداتا غير مرفق")

    file_doc = frappe.get_doc("File", {"file_url": doc.metadata_file})
    file_path = frappe.get_site_path(file_doc.file_url.strip("/"))

    df = pd.read_excel(file_path)

    if df.empty:
        frappe.throw("ملف Excel لا يحتوي على بيانات")

    # إنشاء Batch
    batch = frappe.new_doc("Journal_Intake_Batch_Dtp")
    batch.journal = doc.journal
    batch.source_setup = doc.source_setup
    batch.intake_date = nowdate()
    batch.batch_status = "مسودة"
    batch.batch_articles_count = 0
    batch.intake_file = doc.metadata_file
    batch.insert(ignore_permissions=True)

    inserted = 0
    skipped = 0

    for _, row in df.iterrows():

        doi = _clean(row.get("doi"))

        # ✅ منع التكرار فقط عند وجود DOI
        if doi and frappe.db.exists("Article_Metadata_Dtp", {"doi": doi}):
            frappe.log_error(
                title="Article Skipped (Duplicate DOI)",
                message=f"DOI already exists: {doi}"
            )
            skipped += 1
            continue

        article = frappe.new_doc("Article_Metadata_Dtp")
        article.journal = doc.journal
        article.intake_batch = batch.name

        article.article_title = _clean(row.get("article_title"))
        article.authors_text = _clean(row.get("authors_text"))
        article.abstract = _clean(row.get("abstract"))
        article.publication_date = _clean(row.get("publication_date"))
        article.doi = doi
        article.article_url = _clean(row.get("article_url"))

        article.volume = _clean(row.get("volume"))
        article.issue = _clean(row.get("issue"))
        article.pages = _clean(row.get("pages"))
        article.article_language = _clean(row.get("language"))
        article.article_specialization = _clean(row.get("article_specialization"))
        # 🔥 الجديد
        article.oai_set_name = _clean(row.get("oai_set_name"))
        article.keywords = _clean(row.get("keywords"))
        article.subject_raw = _clean(row.get("subject_raw"))
        article.pdf_url = _clean(row.get("pdf_url"))
        article.source_text = _clean(row.get("source"))

        article.insert(ignore_permissions=True)
        inserted += 1

    frappe.db.set_value(
        "Journal_Intake_Batch_Dtp",
        batch.name,
        {
            "batch_articles_count": inserted,
            "batch_status": "معتمدة"
        }
    )

    doc.status = "تم الاستيعاب / تم الإدراج"
    doc.ingestion_date = nowdate()
    doc.created_batch = batch.name
    doc.total_articles = inserted
    doc.save(ignore_permissions=True)

    frappe.db.commit()

    return {
        "status": "ok",
        "inserted": inserted,
        "skipped": skipped,
        "batch": batch.name
    }


@frappe.whitelist(allow_guest=True)
def get_articles_public(
    page=1,
    page_size=20,
    title=None,
    author=None,
    specialization=None,
    journal=None
):
    page = int(page)
    page_size = int(page_size)
    offset = (page - 1) * page_size

    conditions = []
    values = {}

    # 🔹 سياق المجلة (الفرق بين عرض عام وخاص)
    if journal:
        conditions.append("journal = %(journal)s")
        values["journal"] = journal

    # 🔹 عنوان المقال
    if title:
        conditions.append("article_title LIKE %(title)s")
        values["title"] = f"%{title}%"

    # 🔹 اسم المؤلف
    if author:
        conditions.append("authors_text LIKE %(author)s")
        values["author"] = f"%{author}%"

    # 🔹 التخصص
    if specialization and specialization not in ["all", "الكل", "جميع الاختصاصات"]:
        conditions.append("article_specialization = %(specialization)s")
        values["specialization"] = specialization

    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)

    # 🔹 العدد الكلي
    total = frappe.db.sql(f"""
        SELECT COUNT(name)
        FROM `tabArticle_Metadata_Dtp`
        {where_clause}
    """, values)[0][0]

    # 🔹 جلب المقالات
    articles = frappe.db.sql(f"""
        SELECT
            article_title,
            authors_text,
            abstract,
            publication_date,
            journal_name_display AS journal_name,
            article_url,
            doi,
            volume,
            issue,
            pages,
            article_specialization,
            article_language
        FROM `tabArticle_Metadata_Dtp`
        {where_clause}
        ORDER BY publication_date DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, {
        **values,
        "limit": page_size,
        "offset": offset
    }, as_dict=True)

    return {
        "articles": articles,
        "page": page,
        "page_size": page_size,
        "total": total
    }


@frappe.whitelist(allow_guest=True)
def get_article_specializations_public():
    rows = frappe.db.sql("""
        SELECT DISTINCT article_specialization
        FROM `tabArticle_Metadata_Dtp`
        WHERE article_specialization IS NOT NULL
          AND article_specialization != ''
        ORDER BY article_specialization ASC
    """, as_dict=True)

    specializations = ["الكل"] + [r["article_specialization"] for r in rows]

    return {
        "specializations": specializations
    }


@frappe.whitelist(allow_guest=True)
def get_journal_public_info(journal):
    if not journal:
        return None

    doc = frappe.db.get_value(
        "Journal_Dtp",
        journal,
        ["journal_name"],
        as_dict=True
    )

    if not doc:
        return None

    return {
        "journal_name": doc.journal_name
    }


@frappe.whitelist(allow_guest=True)
def get_journal_specializations_public():
    """
    يرجع قائمة تخصصات المجلات المفهرسة بدون تكرار
    """

    rows = frappe.get_all(
        "Journal_Dtp",
        fields=["specialization"],
        filters={"specialization": ["is", "set"]},
        distinct=True
    )

    specializations = sorted(
        list({r.specialization.strip() for r in rows if r.specialization})
    )

    return {
        "status": "ok",
        "specializations": specializations
    }



@frappe.whitelist(allow_guest=True)
def get_platform_stats():

    # 1️⃣ عدد المقالات
    articles_count = frappe.db.count("Article_Metadata_Dtp")

    # 2️⃣ عدد المجلات (Distinct)
    journals = frappe.db.sql("""
        SELECT COUNT(DISTINCT journal) as total
        FROM `tabArticle_Metadata_Dtp`
        WHERE journal IS NOT NULL
    """, as_dict=True)

    journals_count = journals[0].total if journals else 0

    # 3️⃣ عدد الباحثين الفريدين
    authors_raw = frappe.db.sql("""
        SELECT authors_text
        FROM `tabArticle_Metadata_Dtp`
        WHERE authors_text IS NOT NULL
    """, as_dict=True)

    unique_authors = set()

    for row in authors_raw:
        if row.authors_text:
            # يدعم الفاصلة العربية والانكليزية
            authors = row.authors_text.replace(",", "؛").split("؛")
            for author in authors:
                cleaned = author.strip()
                if cleaned:
                    unique_authors.add(cleaned)

    authors_count = len(unique_authors)

    return {
        "journals": journals_count,
        "articles": articles_count,
        "authors": authors_count
    }


import pandas as pd
import requests
import xml.etree.ElementTree as ET
import time
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


@frappe.whitelist()
def analyze_oai_excel(file_url: str):

    file_doc = frappe.get_doc("File", {"file_url": file_url})
    file_path = frappe.get_site_path(file_doc.file_url.strip("/"))

    df = pd.read_excel(file_path)

    results = []

    ns = {"oai": "http://www.openarchives.org/OAI/2.0/"}

    # 🔥 Session + Retry
    session = requests.Session()
    retries = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[500, 502, 503, 504]
    )
    session.mount("http://", HTTPAdapter(max_retries=retries))
    session.mount("https://", HTTPAdapter(max_retries=retries))

    for i, row in df.iterrows():

        print(f"Processing {i+1}/{len(df)}: {row.get('Journal')}")

        oai_url = str(row.get("OAI Endpoint", "")).strip()
        base = oai_url.split("?")[0]

        harvest_url = f"{base}?verb=ListRecords&metadataPrefix=oai_dc"

        deleted = 0
        status = "ERROR"
        found_valid = False
        total_records = 0

        try:
            resumption_token = None

            while True:

                if resumption_token:
                    url = f"{base}?verb=ListRecords&resumptionToken={resumption_token}"
                else:
                    url = harvest_url

                resp = session.get(url, timeout=(5, 15))

                if resp.status_code != 200:
                    status = "ERROR"
                    break

                root = ET.fromstring(resp.text)

                # 🔥 استخراج العدد الحقيقي
                token_el = root.find(".//oai:resumptionToken", ns)
                if token_el is not None:
                    total_records = int(token_el.attrib.get("completeListSize", 0))

                for rec in root.findall(".//oai:record", ns):

                    header = rec.find("oai:header", ns)

                    if header is not None and header.get("status") == "deleted":
                        deleted += 1
                        continue

                    meta = rec.find(".//oai:metadata", ns)

                    if meta is not None:
                        found_valid = True
                        break

                # 🔥 إذا وجدنا بيانات → نوقف فوراً
                if found_valid:
                    break

                # 🔥 الانتقال للصفحة التالية
                if token_el is None or not token_el.text:
                    break

                resumption_token = token_el.text.strip()

            # 🔥 تحديد الحالة النهائية
            if found_valid:
                status = "OK"
            elif deleted > 0:
                status = "DELETED_ONLY"
            else:
                status = "EMPTY"

        except Exception as e:
            print(f"Error with {base}: {e}")
            status = "ERROR"

        new_row = row.to_dict()
        new_row["oai_base_url"] = base
        new_row["harvest_url"] = harvest_url
        new_row["status"] = status
        new_row["deleted_records_checked"] = deleted
        new_row["total_records"] = total_records
        new_row["ready_for_harvest"] = 1 if status == "OK" else 0

        results.append(new_row)

        # 🔥 حماية السيرفر
        time.sleep(1)

    out_df = pd.DataFrame(results)

    filename = "oai_journals_analyzed.xlsx"
    path = f"/private/files/{filename}"
    full = frappe.get_site_path(path.strip("/"))

    out_df.to_excel(full, index=False)

    return {
        "status": "ok",
        "file": path,
        "rows": len(out_df)
    }

import frappe
import pandas as pd
from frappe.utils import nowdate
from research_agency.api import oai_list_sets, oai_list_records_full
@frappe.whitelist()
def harvest_oai_to_single_excel(oai_base_url: str, journal: str):

    if not oai_base_url:
        frappe.throw("OAI Base URL مطلوب")

    # --------------------------------------------------
    # 1️⃣ جلب جميع sets
    # --------------------------------------------------
    sets = oai_list_sets(oai_base_url).get("sets", [])
    if not sets:
        frappe.throw("لم يتم العثور على أي تخصصات")

    # --------------------------------------------------
    # 2️⃣ تحديد set الرئيسي (ALL)
    # --------------------------------------------------
    main_set = sets[0]  # عادة الأول هو ALL
    main_spec = main_set["setSpec"]

    print(f"[MAIN SET] {main_spec}")

    # --------------------------------------------------
    # 3️⃣ جلب جميع المقالات من MAIN فقط
    # --------------------------------------------------
    main_data = oai_list_records_full(oai_base_url, main_spec)
    main_records = main_data.get("records", [])

    if not main_records:
        frappe.throw("لا توجد بيانات في MAIN SET")

    # --------------------------------------------------
    # 4️⃣ بناء mapping للتخصص من باقي sets
    # --------------------------------------------------
    spec_map = {}

    for s in sets[1:]:
        spec = s["setSpec"]
        name = s["setName"]

        print(f"[CLASSIFY] {spec}")

        try:
            data = oai_list_records_full(oai_base_url, spec)
            records = data.get("records", [])

            for r in records:
                url = r.get("article_url")

                if not url:
                    continue

                # إذا المقال موجود مسبقاً لا نعيد كتابته
                if url not in spec_map:
                    spec_map[url] = {
                        "spec": spec,
                        "name": name
                    }

        except Exception as e:
            print(f"Error in set {spec}: {e}")

    # --------------------------------------------------
    # 5️⃣ دمج التخصص مع MAIN DATA
    # --------------------------------------------------
    final_records = []

    for r in main_records:

        url = r.get("article_url")

        if url in spec_map:
            r["article_specialization"] = spec_map[url]["spec"]
            r["oai_set_name"] = spec_map[url]["name"]
        else:
            r["article_specialization"] = "General"
            r["oai_set_name"] = "General"

        r["journal"] = journal
        r["harvest_date"] = nowdate()

        final_records.append(r)

    # --------------------------------------------------
    # 6️⃣ تحويل إلى DataFrame
    # --------------------------------------------------
    df = pd.DataFrame(final_records)

    # --------------------------------------------------
    # 7️⃣ إزالة التكرار (احتياطي)
    # --------------------------------------------------
    if "doi" in df.columns and df["doi"].notnull().any():
        df = df.drop_duplicates(subset=["doi"], keep="first")
    else:
        df = df.drop_duplicates(subset=["article_url"], keep="first")

    # --------------------------------------------------
    # 8️⃣ ترتيب الأعمدة
    # --------------------------------------------------
    df = df[[
    "article_title",
    "authors_text",
    "abstract",
    "publication_date",
    "doi",
    "article_url",
    "pdf_url",            # 🔥 جديد
    "volume",
    "issue",
    "pages",
    "language",
    "article_specialization",
    "oai_set_name",
    "keywords",           # 🔥 جديد
    "subject_raw",        # 🔥 جديد
    "harvest_date",
    "source"
    ]]

    # --------------------------------------------------
    # 9️⃣ حفظ الملف
    # --------------------------------------------------
    filename = f"OAI_FULL_{journal}_{nowdate()}.xlsx"
    path = f"/private/files/{filename}"
    full = frappe.get_site_path(path.strip("/"))

    df.to_excel(full, index=False)

    return {
        "status": "ok",
        "records": len(df),
        "classified": len(spec_map),
        "file": path
    }


import frappe
import pandas as pd
from frappe.utils import nowdate


# --------------------------------------------------
# 🔹 Normalize اسم المؤسسة
# --------------------------------------------------
def normalize_institution_name(name):
    if not name:
        return None

    name = str(name).strip()

    # تحسينات بسيطة (نكدر نطورها لاحقًا)
    name = name.replace("University", "جامعة")
    name = name.replace("university", "جامعة")
    name = name.replace("College", "كلية")
    name = name.replace("Institute", "معهد")

    return name.strip()


# --------------------------------------------------
# 🔹 Ensure Institution
# --------------------------------------------------
def ensure_institution_exists(inst_name):

    inst_name = normalize_institution_name(inst_name)

    if not inst_name:
        inst_name = "جهة غير معروفة"

    # 🔍 بحث مباشر
    existing = frappe.db.exists("Institution_Dtp", inst_name)
    if existing:
        return existing

    # 🔍 بحث تقريبي
    similar = frappe.db.sql("""
        SELECT name
        FROM `tabInstitution_Dtp`
        WHERE institution_name LIKE %(name)s
        LIMIT 1
    """, {"name": f"%{inst_name}%"})

    if similar:
        return similar[0][0]

    # 🧠 تحديد النوع
    lower = inst_name.lower()

    if "جامعة" in inst_name or "university" in lower:
        inst_type = "جامعة"
    elif "كلية" in inst_name or "college" in lower:
        inst_type = "جامعة"
    elif "معهد" in inst_name or "institute" in lower:
        inst_type = "معهد"
    else:
        inst_type = "مركز بحثي"

    # 🏗 إنشاء مؤسسة جديدة
    doc = frappe.new_doc("Institution_Dtp")
    doc.institution_name = inst_name
    doc.type = inst_type
    doc.country = "العراق"

    doc.insert(ignore_permissions=True)

    return doc.name


import frappe
import pandas as pd
from frappe.utils import nowdate


# --------------------------------------------------
# 🔹 Normalize اسم المؤسسة
# --------------------------------------------------
def normalize_institution_name(name):
    if not name:
        return "جهة غير معروفة"

    name = str(name).strip()

    # توحيد بسيط
    name = name.replace("University", "جامعة")
    name = name.replace("university", "جامعة")
    name = name.replace("College", "كلية")
    name = name.replace("Institute", "معهد")

    return name.strip()


# --------------------------------------------------
# 🔹 Prepare Journals Excel
# --------------------------------------------------
@frappe.whitelist()
def prepare_journals_excel(file_url):

    # 🔹 قراءة الملف
    file_path = frappe.get_site_path(file_url.strip("/"))
    df = pd.read_excel(file_path)

    prepared_rows = []

    for _, row in df.iterrows():

        # -----------------------------
        # 🔹 اسم المجلة
        # -----------------------------
        journal_name = str(row.get("Journal", "")).strip()
        if not journal_name:
            continue

        # -----------------------------
        # 🔹 المؤسسة (تنظيف)
        # -----------------------------
        institution_name = normalize_institution_name(
            row.get("Publisher")
        )

        # -----------------------------
        # 🔹 بناء السجل
        # -----------------------------
        prepared_rows.append({
            "journal_name": journal_name,
            "institution_name": institution_name,

            # 🔥 قيم مؤقتة (تُعدل لاحقًا)
            "specialization": "علمي",
            "language": "كلاهما",

            "journal_url": row.get("Journal Website"),
            "oai_base_url": row.get("oai_base_url"),

            # 🔥 للتحكم والمتابعة
            "status": "READY",
            "needs_review": 1
        })

    # -----------------------------
    # 🔹 تحويل DataFrame
    # -----------------------------
    new_df = pd.DataFrame(prepared_rows)

    # -----------------------------
    # 🔹 حذف التكرار (مهم)
    # -----------------------------
    new_df.drop_duplicates(subset=["journal_name"], inplace=True)

    # -----------------------------
    # 🔹 حفظ الملف
    # -----------------------------
    filename = f"prepared_journals_{nowdate()}.xlsx"
    file_url = f"/private/files/{filename}"
    full_path = frappe.get_site_path(file_url.strip("/"))

    new_df.to_excel(full_path, index=False)

    # -----------------------------
    # 🔹 النتيجة
    # -----------------------------
    return {
        "status": "ok",
        "records": len(new_df),
        "file": file_url
    }


@frappe.whitelist(allow_guest=True)
def get_articles_v2(filters=None, page=1, page_size=20):
    import json

    if isinstance(filters, str):
        filters = json.loads(filters)

    page = int(page)
    page_size = int(page_size)
    offset = (page - 1) * page_size

    conditions = []
    values = {}

    # 🔥 specialization (MULTI SELECT)
    if filters.get("specializations"):
        specs = filters["specializations"]
        conditions.append(f"article_specialization IN %(specs)s")
        values["specs"] = tuple(specs)

    # 🔥 year filter
    if filters.get("years"):
        years = filters["years"]
        conditions.append(f"YEAR(publication_date) IN %(years)s")
        values["years"] = tuple(years)

    # 🔥 journal
    if filters.get("journal"):
        conditions.append("journal = %(journal)s")
        values["journal"] = filters["journal"]

    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""

    # count
    total = frappe.db.sql(f"""
        SELECT COUNT(name)
        FROM `tabArticle_Metadata_Dtp`
        {where_clause}
    """, values)[0][0]

    # data
    articles = frappe.db.sql(f"""
        SELECT
            article_title,
            authors_text,
            abstract,
            publication_date,
            journal_name_display AS journal_name,
            article_url,
            doi,
            volume,
            issue,
            pages
        FROM `tabArticle_Metadata_Dtp`
        {where_clause}
        ORDER BY publication_date DESC
        LIMIT %(limit)s OFFSET %(offset)s
    """, {
        **values,
        "limit": page_size,
        "offset": offset
    }, as_dict=True)

    return {
        "articles": articles,
        "total": total
    }


@frappe.whitelist(allow_guest=True)
def get_filters_data():

    raw = frappe.db.sql("""
        SELECT article_specialization, COUNT(*) as count
        FROM `tabArticle_Metadata_Dtp`
        GROUP BY article_specialization
    """, as_dict=True)

    cleaned = {}

    for r in raw:
        val = r["article_specialization"] or ""
        
        # 🔥 استخراج الجزء بعد :
        if ":" in val:
            val = val.split(":")[-1]

        val = val.strip()

        if not val:
            continue

        if val not in cleaned:
            cleaned[val] = 0

        cleaned[val] += r["count"]

    specs = [{"name": k, "count": v} for k, v in cleaned.items()]

    years = frappe.db.sql("""
        SELECT YEAR(publication_date) as name, COUNT(*) as count
        FROM `tabArticle_Metadata_Dtp`
        GROUP BY YEAR(publication_date)
        ORDER BY name DESC
    """, as_dict=True)

    return {
        "specializations": specs,
        "years": years
    }

@frappe.whitelist(allow_guest=True)
def get_filters_normalized():

    data = get_filters_data()

    raw_specs = data.get("specializations", [])
    years = data.get("years", [])

    subjects = {}
    doc_types = {}

    for item in raw_specs:
        name = item.get("name") or ""
        count = item.get("count") or 0

        # =====================================================
        # 🔹 Document Types (نهائي ومحسن)
        # =====================================================
        n = (name or "").lower().strip()

        # استخراج الجزء بعد :
        code = n.split(":")[-1] if ":" in n else n

        # تنظيف
        code = code.replace("+", " ").strip()

        # =========================
        # SMART DETECTION (محسن)
        # =========================

        if code in ["art"] or "article" in code or "original" in code:
            dt_key = "Article"

        elif code in ["rev"] or "review" in code:
            dt_key = "Review"

        elif "conf" in code:
            dt_key = "Conference"

        elif "case" in code:
            dt_key = "Case Study"

        elif "editor" in code or code == "ed":
            dt_key = "Editorial"

        else:
            dt_key = "Other"

        doc_types[dt_key] = doc_types.get(dt_key, 0) + count


        # =====================================================
        # 🔹 Subjects (نهائي ومحسن)
        # =====================================================

        if any(x in n for x in ["med", "medical", "surg", "gyno", "patho"]):
            sub_key = "طب"

        elif any(x in n for x in [
            "eng", "engineering", "civil", "mechanical", "electrical"
        ]):
            sub_key = "هندسة"

        elif any(x in n for x in [
            "computer", "c.s", "ai", "ml", "nlp", "it"
        ]):
            sub_key = "علوم الحاسوب"

        elif any(x in n for x in ["math", "stat"]):
            sub_key = "رياضيات"

        elif any(x in n for x in ["phy", "physics"]):
            sub_key = "فيزياء"

        elif any(x in n for x in ["chem", "chemistry"]):
            sub_key = "كيمياء"

        elif any(x in n for x in ["bio", "biology"]):
            sub_key = "علوم حياتية"

        elif any(x in n for x in ["geo", "earth"]):
            sub_key = "علوم الأرض"

        elif "athar" in n:
            sub_key = "آثار"

        elif any(x in n for x in ["tarykh", "history"]):
            sub_key = "تاريخ"

        elif any(x in n for x in ["qanwn", "law"]):
            sub_key = "قانون"

        else:
            sub_key = "أخرى"

        subjects[sub_key] = subjects.get(sub_key, 0) + count


    return {
        "subjects": [{"name": k, "count": v} for k, v in subjects.items()],
        "doc_types": [{"name": k, "count": v} for k, v in doc_types.items()],
        "years": years
    }


@frappe.whitelist(allow_guest=True)
def get_articles_public_v2(
    page=1,
    page_size=20,
    title=None,
    author=None,
    specialization=None,
    subjects=None,
    doc_types=None,
    years=None
):
    import frappe
    from frappe.utils import cint

    page = cint(page) or 1
    page_size = cint(page_size) or 20
    start = (page - 1) * page_size

    conditions = []
    values = {}

    # =========================
    # 🔹 Filters القديمة
    # =========================
    if title:
        conditions.append("article_title LIKE %(title)s")
        values["title"] = f"%{title}%"

    if author:
        conditions.append("authors_text LIKE %(author)s")
        values["author"] = f"%{author}%"

    if specialization:
        conditions.append("article_specialization LIKE %(specialization)s")
        values["specialization"] = f"%{specialization}%"

    # =========================
    # 🔹 Years
    # =========================
    if years:
        years_list = [int(y) for y in years.split(",") if y.isdigit()]

        if years_list:
            conditions.append("YEAR(publication_date) IN %(years)s")
            values["years"] = tuple(years_list)

    # =========================
    # 🔹 Doc Types (ذكية 🔥)
    # =========================
    if doc_types:
        doc_list = doc_types.split(",")

        doc_conditions = []

        for d in doc_list:

            if d == "Article":
                doc_conditions.append("article_specialization LIKE '%%ART%%'")

            elif d == "Review":
                doc_conditions.append("article_specialization LIKE '%%REV%%'")

            elif d == "Conference":
                doc_conditions.append("article_specialization LIKE '%%CONF%%'")

            elif d == "Case Study":
                doc_conditions.append("article_specialization LIKE '%%CASE%%'")

            elif d == "Editorial":
                doc_conditions.append("article_specialization LIKE '%%:ED%%'")

            elif d == "Other":
                doc_conditions.append("""
                    article_specialization NOT LIKE '%%ART%%' AND
                    article_specialization NOT LIKE '%%REV%%' AND
                    article_specialization NOT LIKE '%%CONF%%' AND
                    article_specialization NOT LIKE '%%CASE%%' AND
                    article_specialization NOT LIKE '%%ED%%'
                """)

        if doc_conditions:
            conditions.append("(" + " OR ".join(doc_conditions) + ")")

    # =========================
    # 🔹 Subjects (مبدئياً بسيط)
    # =========================
    if subjects:
        sub_list = subjects.split(",")

        sub_conditions = []

        for s in sub_list:

            if s == "طب":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%med%%'")

            elif s == "هندسة":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%eng%%'")

            elif s == "علوم الحاسوب":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%computer%%'")

            elif s == "رياضيات":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%math%%'")

            elif s == "فيزياء":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%phy%%'")

            elif s == "كيمياء":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%chem%%'")

            elif s == "علوم حياتية":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%bio%%'")

            elif s == "علوم الأرض":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%geo%%'")

            elif s == "قانون":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%law%%'")

            elif s == "تاريخ":
                sub_conditions.append("LOWER(IFNULL(subject_raw, '')) LIKE '%%history%%'")

            elif s == "آثار":
                sub_conditions.append("""
                    LOWER(IFNULL(subject_raw, '')) LIKE '%%athar%%'
                    OR LOWER(IFNULL(subject_raw, '')) LIKE '%%archae%%'
                    OR LOWER(IFNULL(subject_raw, '')) LIKE '%%heritage%%'
                    OR LOWER(IFNULL(subject_raw, '')) LIKE '%%antiqu%%'
                    OR LOWER(IFNULL(article_specialization, '')) LIKE '%%athar%%'
                """)

            elif s == "أخرى":
                sub_conditions.append("""
                    LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%med%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%eng%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%computer%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%math%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%phy%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%chem%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%bio%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%geo%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%law%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%history%%'
                    AND LOWER(IFNULL(subject_raw,'')) NOT LIKE '%%athar%%'
                """)

        if sub_conditions:
            conditions.append("(" + " OR ".join(sub_conditions) + ")")

    # =========================
    # WHERE
    # =========================
    where_clause = ""
    if conditions:
        where_clause = "WHERE " + " AND ".join(conditions)


    # =========================
    # Query (articles)
    # =========================
    query = f"""
        SELECT *
        FROM `tabArticle_Metadata_Dtp`
        {where_clause}
        ORDER BY publication_date DESC
        LIMIT %(start)s, %(page_size)s
    """

    values["start"] = start
    values["page_size"] = page_size

    data = frappe.db.sql(query, values, as_dict=True)


    # =========================
    # Count (pagination)
    # =========================
    count_query = f"""
        SELECT COUNT(*) as total
        FROM `tabArticle_Metadata_Dtp`
        {where_clause}
    """

    total = frappe.db.sql(count_query, values, as_dict=True)[0]["total"]


    # =========================
    # 🔥 Subjects Counts (تصحيح مهم)
    # =========================
    subjects_counts = frappe.db.sql(f"""
        SELECT subject, COUNT(*) as count FROM (
            SELECT
                CASE
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%athar%%' THEN 'آثار'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%history%%' THEN 'تاريخ'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%law%%' THEN 'قانون'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%computer%%' THEN 'علوم الحاسوب'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%bio%%' THEN 'علوم حياتية'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%chem%%' THEN 'كيمياء'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%geo%%' THEN 'علوم الأرض'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%math%%' THEN 'رياضيات'
                    WHEN LOWER(IFNULL(subject_raw,'')) LIKE '%%phy%%' THEN 'فيزياء'
                    ELSE 'أخرى'
                END as subject
            FROM `tabArticle_Metadata_Dtp`
            {where_clause}
        ) t
        GROUP BY subject
    """, values, as_dict=True)


    # =========================
    # 🔥 Doc Types Counts (تصحيح مهم)
    # =========================
    doc_types_counts = frappe.db.sql(f"""
        SELECT doc_type, COUNT(*) as count FROM (
            SELECT
                CASE
                    WHEN article_specialization LIKE '%%ART%%' THEN 'Article'
                    WHEN article_specialization LIKE '%%REV%%' THEN 'Review'
                    WHEN article_specialization LIKE '%%CONF%%' THEN 'Conference'
                    WHEN article_specialization LIKE '%%CASE%%' THEN 'Case Study'
                    WHEN article_specialization LIKE '%%ED%%' THEN 'Editorial'
                    ELSE 'Other'
                END as doc_type
            FROM `tabArticle_Metadata_Dtp`
            {where_clause}
        ) t
        GROUP BY doc_type
    """, values, as_dict=True)


    # =========================
    # RETURN
    # =========================
    return {
        "articles": data,
        "page": page,
        "page_size": page_size,
        "total": total,
        "subjects": subjects_counts,
        "doc_types": doc_types_counts
    }