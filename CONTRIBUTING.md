# 👥 دليل عمل الفريق والمساهمة في المشروع (Team Contribution & Workspace Guide)

مرحباً بك في فريق عمل وتطوير **Oracle EBS R12 MCP Studio**.  
يوضح هذا الدليل كيفية إعداد بيئة العمل الموحدة (Workspace)، واستنساخ المشروع، والعمل بالتنسيق مع أعضاء الفريق.

---

## ⚡ البدء السريع في 3 خطوات (Quick Setup)

### 1. استنساخ المستودع (Clone Repository)
```bash
git clone https://github.com/Yousef200188/oracle-ebs-mcp.git
cd oracle-ebs-mcp
```

### 2. فتح بيئة العمل الموحدة (Open Workspace)
* في **VS Code** أو **Cursor** أو **Antigravity IDE**:
  * افتح القائمة `File -> Open Workspace from File...`
  * اختر ملف: `oracle-ebs-mcp.code-workspace`
* سيتم تلقائياً تفعيل الإعدادات، مسارات بايثون، ومهام التشغيل الجاهزة.

### 3. إعداد البيئة الافتراضية والمتغيرات
```bash
# إنشاء وتفعيل البيئة الافتراضية
python -m venv .venv

# Windows
.\.venv\Scripts\activate

# Linux / Mac
source .venv/bin/activate

# تثبيت الحزم
pip install -r requirements.txt

# تجهيز ملف الإعدادات
copy .env.example .env   # On Windows
# أو cp .env.example .env على Linux
```

---

## 🛠️ أزرار التشغيل المباشر من الـ IDE (Press F5)

تم تجهيز إعدادات `launch.json` لتتمكن من تشغيل أي جزء بضغطة زر أو بالضغط على **F5**:

| التكوين (Configuration) | الوظيفة |
| :--- | :--- |
| 🚀 **Start EBS Studio Web UI** | تشغيل خادم وبوابة الاستوديو على المنفذ `8855` |
| ⚡ **Start FastMCP Server** | تشغيل خادم الـ MCP الموجه لنماذج الذكاء الاصطناعي (Claude / Cursor) |
| 🧪 **Run Pytest Test Suite** | تنفيذ حزمة الاختبارات الآلية بالكامل |
| 📄 **Build Arabic Word Doc** | إعادة توليد ملف التوثيق المكتبي بالصور تلقائياً |

---

## ☁️ العمل السحابي بدون تثبيت (GitHub Codespaces)
يمكن لأي عضو في الفريق العمل على المشروع مباشرة من متصفح الويب دون الحاجة لتثبيت أي برنامج محلياً:
1. ادخل على رابط المستودع: [https://github.com/Yousef200188/oracle-ebs-mcp](https://github.com/Yousef200188/oracle-ebs-mcp)
2. اضغط على الزر الأخضر **Code** -> اختر تبويب **Codespaces** -> اضغط **Create codespace on main**.
3. ستفتح بيئة VS Code كاملة في المتصفح مع تثبيت الحزم وتجهيز منفذ الاستوديو `8855` تلقائياً!

---

## 🔀 دورة حياة العمل وإدارة الفروع (Git Workflow)

1. **لا تقم بالرفع المباشر على `main` مطلقاً**.
2. أنشئ فرعاً جديداً لميزتك (Feature Branch):
   ```bash
   git checkout -b feature/your-feature-name
   ```
3. اكتب الكود واختبره محلياً:
   ```bash
   python run_tests.py
   ```
4. قم بعمل Commit و Push لفرعك:
   ```bash
   git add .
   git commit -m "feat: describe your change"
   git push -u origin feature/your-feature-name
   ```
5. افتح **Pull Request (PR)** على GitHub لطلب المراجعة والدمج.
