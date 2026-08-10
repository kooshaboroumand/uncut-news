# آنکات (UNCUT) – خبرخوان خودکار فیلم و سریال

سایت یک‌صفحه‌ای که **هر ۱ ساعت** به صورت کاملاً خودکار از منابع معتبر سینمایی (Deadline, Variety, Hollywood Reporter, The Wrap, IndieWire) اخبار مهم و رسمی را می‌گیرد، فیلتر می‌کند، ترجمه می‌کند و روی سایت قرار می‌دهد.

---

## مراحل دیپلوی روی Netlify (یک‌بار برای همیشه)

### ۱. ساخت ریپازیتوری گیت‌هاب
1. برو به [github.com/new](https://github.com/new)
2. نام ریپو را مثلاً `uncut-news` بگذار
3. Public انتخاب کن و Create repository بزن

### ۲. آپلود فایل‌ها
فایل‌های داخل این پوشه را به ریپوی گیت‌هاب خودت push کن:

```
uncut-auto/
├── index.html
├── news.json
├── scripts/
│   └── fetch_news.py
└── .github/
    └── workflows/
        └── update-news.yml
```

اگر با Git آشنا نیستی:
- فایل‌ها را Zip کن
- در صفحه ریپو روی **uploading an existing file** کلیک کن و همه را آپلود کن.

### ۳. اتصال به Netlify
1. برو به [app.netlify.com](https://app.netlify.com) و وارد شو
2. **Add new site** → **Import an existing project**
3. GitHub را انتخاب کن و ریپوی `uncut-news` را پیدا کن
4. تنظیمات:
   - **Build command**: خالی بگذار (چون استاتیک است)
   - **Publish directory**: `/` (ریشه)
5. Deploy site بزن

بعد از چند ثانیه سایت بالا می‌آید.

### ۴. فعال‌سازی آپدیت خودکار
- به ریپوی گیت‌هاب برو → تب **Actions**
- ورک‌فلو `Update Uncut News` را ببین
- اگر اولین بار است، ممکن است نیاز به فعال‌سازی Actions داشته باشی (دکمه Enable)

از این لحظه به بعد:
- هر ۱ ساعت یک‌بار اسکریپت اجرا می‌شود
- اخبار جدید مهم فیلتر و ترجمه می‌شوند
- `news.json` آپدیت و کامیت می‌شود
- Netlify به صورت خودکار سایت را دوباره دیپلوی می‌کند

---

## منابع خبری فعلی
- Deadline
- Variety
- The Hollywood Reporter
- The Wrap
- IndieWire

فقط اخبار **مهم و رسمی** (تمدید، لغو، تریلر رسمی، تاریخ پخش، کستینگ مهم، معاملات بزرگ و ...) نگه داشته می‌شوند.

---

## نکات
- ترجمه با Google Translate رایگان انجام می‌شود (کیفیت خوب است اما گاهی نیاز به ویرایش دارد).
- عکس‌ها فعلاً placeholder هستند (چون RSS معمولاً عکس نمی‌دهد). بعداً می‌توان og:image گرفت.
- نظرات کاربران در مرورگر خودشان (localStorage) ذخیره می‌شود.
- برای اجرای دستی: در تب Actions گیت‌هاب → Run workflow

---

ساخته‌شده برای آنکات
