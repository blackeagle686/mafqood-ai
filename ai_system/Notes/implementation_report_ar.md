# تقرير تنفيذ نظام استخراج بصمات الوجوه وقاعدة البيانات الشعاعية (جاهز للإنتاج)

يقدم هذا التقرير استعراضًا للمرحلة النهائية من تنفيذ خط معالجة الصور (CV Pipeline)، ومعالجة المهام في الخلفية، ونقاط اتصال البرمجية (API) لنظام "مفقود" للذكاء الاصطناعي.

## 🏗️ نظرة عامة على الهيكلية التقنية

تم تصميم النظام باتباع بنية هندسية نظيفة تعتمد على الواجهات (Interfaces) لضمان سهولة الصيانة والتوسع. يتم إدارة النماذج كأنماط "Singleton" لتحسين استهلاك الذاكرة، وهو أمر حيوي في بيئات الإنتاج التي تحتوي على عمال (Workers) متعددين.

````carousel
```python
# app/core/cv_pipeline.py
# --- تصميم معتمد على الواجهات ---
class FaceCVPipeline:
    def __init__(self):
        self.detector = RetinaFaceDetector() # دقة عالية في الكشف
        self.cropper = OpenCVCropper()       # قص صور موحد
        self.embedder = InsightFaceEmbedder() # استخراج بصمة (512 أبعاد)

    def process_image(self, image_path: str):
        # تدفق كامل: كشف -> قص -> استخراج بصمة
        # يتضمن معالجة قوية للأخطاء وتحميل النماذج بنمط Singleton
```
<!-- slide -->
```python
# app/db/vector_db.py
# --- تخزين شعاعي مستمر ---
class VectorDB:
    def __init__(self):
        self.client = chromadb.PersistentClient(path="./chroma_db")
        self.collection = self.client.get_or_create_collection("face_embeddings")

    def upsert(self, ids, embeddings, metadatas):
        # إدخال دفعي فعال مع استخدام تشابه جيب التمام (Cosine Similarity)
```
<!-- slide -->
```python
# app/tasks/cv_tasks.py
# --- معالجة المهام في الخلفية ---
@shared_task(bind=True, max_retries=3)
def process_image_task(self, image_path: str, metadata: dict = None):
    # تنفيذ خط المعالجة بشكل غير متزامن
    # تخزين النتائج في VectorDB تلقائيًا
    # منطق إعادة محاولة قوي لضمان استقرار النظام في الإنتاج
```
<!-- slide -->
```python
# app/api/endpoints/cv.py
# --- نقاط اتصال FastAPI ---
@router.post("/process")
async def process_image(file: UploadFile):
    # غير متزامن: يرسل المهمة لـ Celery ويعيد id المهمة
    
@router.post("/search")
async def search_face(file: UploadFile):
    # متزامن: نتائج فورية لطلبات البحث من المستخدم
```
````

## 📄 ملفات التنفيذ الرئيسية

### 1. [خط المعالجة الأساسي (CV Core)](file:///c:/Users/The_Last_King/OneDrive/Documents/Projects/GD_project/mafqood/ai_system/app/core/cv_pipeline.py)
يحتوي هذا الملف على المنسق `FaceCVPipeline` ومحمل النماذج `FaceModelLoader`. يتولى الكشف عبر RetinaFace واستخراج الميزات عبر InsightFace.

### 2. [مغلف قاعدة بيانات المتجهات (Vector DB)](file:///c:/Users/The_Last_King/OneDrive/Documents/Projects/GD_project/mafqood/ai_system/app/db/vector_db.py)
مغلف نظيف حول ChromaDB يدير المجموعات المستمرة ويوفر عمليات إدخال وبحث عالية المستوى.

### 3. [مهام سيلري (Celery Tasks)](file:///c:/Users/The_Last_King/OneDrive/Documents/Projects/GD_project/mafqood/ai_system/app/tasks/cv_tasks.py)
يعرف مهمة `process_image_task`. تم تصميم هذه المهمة لتكون موثوقة للغاية، مع دعم إعادة المحاولة وتسجيل العمليات للمراقبة في بيئة الإنتاج.

### 4. [نقاط اتصال الـ API](file:///c:/Users/The_Last_King/OneDrive/Documents/Projects/GD_project/mafqood/ai_system/app/api/endpoints/cv.py)
يسجل مسارات `/cv/process` و `/cv/search` و `/cv/health` ، مما يسمح بالوصول الخارجي لقدرات نظام الذكاء الاصطناعي.

## 🚀 النشر والتوسع

- **التوسع الديناميكي**: النظام مصمم ليعمل مع خاصية `--autoscale=10,3` في Celery.
- **كفاءة الموارد**: نمط الـ Singleton يمنع تحميل النماذج الكبيرة في الذاكرة بشكل متكرر عند فتح مهام جديدة.
- **جاهزية الـ GPU**: قابل للتكوين عبر `CV_CTX_ID` في ملف الإعدادات للتبديل بين المعالج العادي (CPU) ومعالج الرسوميات (GPU).

---
*تم إنشاء التقرير لنظام "مفقود" للذكاء الاصطناعي.*
