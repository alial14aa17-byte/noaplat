# nōa Premium Operations — v0.2

**Mobile-first internal operations app** for nōa. Arabic RTL, responsive desktop and iPhone-sized layouts, red premium dashboard, real API, role-based login, PostgreSQL support.

## What works in this package
- Owner login bootstrap, signed session cookies, hashed passwords, four account roles: owner/admin/assistant/trader.
- Owner can create users, products and expenses; admin can create products and orders; assistant and trader can create orders; trader only sees own orders.
- Create and list products, orders, status updates, expenses, audit log, operational metrics.
- Dashboard with real seven-day order activity and status breakdown (not fake data), latest orders, quick actions, revenue/profit estimates for authorized roles.
- Mobile-first premium RTL UI, bottom navigation, touch-sized controls, modal bottom sheets, PWA manifest.
- Railway configuration with PostgreSQL or local SQLite for development.

## Deploy to Railway
1. Upload the contents of this folder to a **private GitHub repository**.
2. Railway → New Project → Deploy from GitHub repo.
3. Add a PostgreSQL service. Set `DATABASE_URL` in the app service using a **variable reference** to PostgreSQL `DATABASE_URL`.
4. Set `OWNER_EMAIL`, `OWNER_PASSWORD` (12+ chars), `SESSION_SECRET` (32+ random chars), `HTTPS_ONLY=true`.
5. Railway builds the Python app using `requirements.txt` and starts using `railway.json`.
6. Open Railway → Networking → Generate Domain. Attach your custom domain later if desired.
7. Login with the owner credentials. First owner is created only if the users table is empty.

**Do not** upload `.env` or passwords to GitHub. Use Railway Variables. Do not expose a production app with weak credentials.

## Run locally
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
export OWNER_EMAIL=owner@example.com
export OWNER_PASSWORD='replace-with-strong-password'
export SESSION_SECRET='replace-with-a-long-random-string-of-at-least-32-characters'
uvicorn app:app --reload
```
Visit http://127.0.0.1:8000

## Important production limitations
**This is an upgraded runnable foundation, not a completed 170-feature ERP.** It is not yet safe to rely on as the sole source of truth for live inventory or financial settlements. In particular, the following are **not implemented**: image/DTF file upload and durable object storage, purchasing and suppliers, automatic inventory movements, trader settlement ledger, advanced permissions, invite flow, Telegram synchronization, Iraq governorate heatmap, invoice printing, backups/restore, migrations, CSRF protection, login rate limiting, MFA, automated end-to-end tests. These need implementation and security review before live production use.

Revenue currently counts **delivered** orders; costs and profit are preliminary and exclude several settlement scenarios. There are no demo/fake orders. Product imagery is intentionally represented by neutral placeholders until real product assets are uploaded.

## Recommended mobile testing
Test at 320px, 375px, 390px, 430px widths and 768px tablet, plus desktop. Test Safari iOS and Chrome Android, form keyboard behavior, RTL, horizontal scrolling, and access controls.

## إصلاح تسجيل دخول المالك (v0.3)
- عند تشغيل التطبيق تتم مزامنة حساب المالك الموجود مع `OWNER_EMAIL` و `OWNER_PASSWORD` من Railway، حتى لو كان الحساب قد أُنشئ مسبقاً.
- لا تُخزَّن بيانات الدخول في الكود أو ملف ZIP.
- اضبط `OWNER_EMAIL` و `OWNER_PASSWORD` داخل Railway Variables، ثم انشر النسخة الجديدة.
- استخدم كلمة مرور طويلة وفريدة بعد اختبار الدخول، ولا تعرض قيمتها في الصور.
- إذا ظهر تعارض بريد إلكتروني مع حساب آخر، يلزم فحص قاعدة البيانات قبل تعديل الحسابات.

## NOA Premium v0.4 — تحديث من نفس ملف v0.3
- **ليس مشروع v7**؛ هذه النسخة مبنية على ZIP `noa-premium-login-fixed-v0.3(2).zip`.
- تحسينات Safari: منع التكبير التلقائي لحقل الإدخال (font-size 16px)، منع التمرير الأفقي، تكييف النوافذ.
- رفع صور متعددة مع الطلب (JPG/PNG/WEBP، حد 12MB للصورة، 20 صورة للطلب). الصور تتطلب **Railway Volume دائم**.
- إنشاء المنتجات مقتصر على Owner على الخادم والواجهة، ولا يتم إظهار سعر الخام أو المبيعات للأدمن.
- الأدمن يرى عمولته 1,500 دينار لكل طلب أنشأه وحالته الحالية `تم التسليم`؛ الرجوع/الإلغاء يلغي احتسابها. **لم تُنفذ بعد كشوف صرف العمولات أو التسويات التاريخية**.
- فواتير مصروفات باسم وتصنيف (ملابس، دي تي اف، ترويج، خسائر أخرى، مشتريات، سحب خاص) وملاحظات وصورة وصل.
- نسخ احتياطي ZIP (JSON + صور) واسترداد بواسطة Owner فقط، مع معاينة وتأكيد. **الاسترداد يستبدل البيانات الحالية بالكامل**. اختبره على نسخة تجريبية قبل الإنتاج.

### Railway Variables
- `DATABASE_URL` = ربط PostgreSQL (ضروري للحفظ المستمر).
- `SESSION_SECRET` = قيمة عشوائية 32 حرفاً على الأقل.
- `OWNER_EMAIL` و `OWNER_PASSWORD` = بيانات المالك من Variables فقط، لا تضعها في الكود.
- `UPLOAD_DIR=/data/noa_uploads` مع Volume مربوط على `/data` في خدمة web؛ بدون Volume الصور والنسخ المرفوعة قد تختفي عند إعادة النشر.
- `HTTPS_ONLY=true` عند التشغيل على نطاق HTTPS.

### احتياطات التشغيل
1. نزّل نسخة من قاعدة البيانات الحالية قبل استبدال الكود. إذا كان التخزين الحالي SQLite داخل Railway بدون Volume فقد يكون غير دائم.
2. انسخ محتويات ZIP إلى جذر GitHub المرتبط بـ Railway.
3. أضف Volume، واضبط متغيرات البيئة، ثم Deploy.
4. اختبر بحسابات Owner وAdmin منفصلة؛ تأكد أن Admin لا يرى أسعار البيع أو الخام أو المبيعات.
5. اختبر رفع الصور وتحديث الحالة، ونسخ ZIP واسترداده في **بيئة اختبار منفصلة**.
6. لا ترفع نسخ ZIP الاحتياطية إلى مستودع GitHub، فهي تحتوي معلومات حساسة وكلمات مرور مجزأة.

### حدود النسخة
- لم يتم اختبار نشرها فعلياً على Railway أو Safari الحقيقي في هذه الجلسة.
- لم يتم بناء سجل دفعات الأدمن أو كشف محاسبة نهائي؛ العمولة هنا محسوبة حسب الحالة الحالية فقط.
- رفع الصور يتم بعد إنشاء الطلب؛ إذا فشل الرفع يبقى الطلب محفوظاً ويمكن معالجة الصور لاحقاً.
- نسخ ZIP والاسترداد ليسا بديلاً عن نسخ PostgreSQL المجدولة أو الاختبارات الدورية لاسترجاع الكوارث.
