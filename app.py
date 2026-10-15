import os, secrets, datetime, json, io, zipfile, uuid, pathlib, shutil, tempfile, hmac, csv
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, func, select, inspect, text
from sqlalchemy.orm import declarative_base, sessionmaker
from passlib.context import CryptContext
from starlette.middleware.sessions import SessionMiddleware

url=os.getenv('DATABASE_URL','sqlite:///./noa.db')
if url.startswith('postgres://'):url='postgresql://'+url[len('postgres://'):]
if url.startswith('postgresql://'):url=url.replace('postgresql://','postgresql+psycopg://',1)
engine=create_engine(url,pool_pre_ping=True,connect_args={'check_same_thread':False} if url.startswith('sqlite') else {})
DB=sessionmaker(bind=engine,expire_on_commit=False)
Base=declarative_base()
crypt=CryptContext(schemes=['bcrypt'],deprecated='auto')
now=lambda:datetime.datetime.now(datetime.timezone.utc)
class User(Base):
 __tablename__='users'
 id=Column(Integer,primary_key=True); name=Column(String(120),nullable=False); email=Column(String(190),unique=True,nullable=False); password_hash=Column(String(255),nullable=False); role=Column(String(25),default='trader'); active=Column(Integer,default=1); created_at=Column(DateTime(timezone=True),default=now)
class Product(Base):
 __tablename__='products'
 id=Column(Integer,primary_key=True); name=Column(String(160),nullable=False); category=Column(String(80),default='هوديات'); price=Column(Integer,default=0); cost=Column(Integer,default=0); stock=Column(Integer,default=0); colors=Column(Text,default='أسود,أبيض'); sizes=Column(Text,default='S,M,L,XL,2XL,3XL'); created_at=Column(DateTime(timezone=True),default=now)
class Order(Base):
 __tablename__='orders'
 id=Column(Integer,primary_key=True); images=Column(Text,default='[]'); customer=Column(String(120),nullable=False); phone=Column(String(40),nullable=False); province=Column(String(80),default=''); area=Column(String(160),default=''); landmark=Column(String(160),default=''); product_id=Column(Integer,ForeignKey('products.id')); product_name=Column(String(160),default=''); color=Column(String(60),default=''); size=Column(String(20),default=''); quantity=Column(Integer,default=1); price=Column(Integer,default=0); cost=Column(Integer,default=0); deposit=Column(Integer,default=0); delivery=Column(Integer,default=0); status=Column(String(40),default='جديد'); notes=Column(Text,default=''); created_by=Column(Integer,ForeignKey('users.id')); created_at=Column(DateTime(timezone=True),default=now)
class Expense(Base):
 __tablename__='expenses'
 id=Column(Integer,primary_key=True); receipt=Column(Text,default=''); description=Column(Text,default=''); category=Column(String(80),default='مشتريات'); name=Column(String(160),nullable=False); amount=Column(Integer,default=0); created_by=Column(Integer,ForeignKey('users.id')); created_at=Column(DateTime(timezone=True),default=now)
class Audit(Base):
 __tablename__='audit'
 id=Column(Integer,primary_key=True); user_id=Column(Integer); action=Column(String(100)); details=Column(Text); created_at=Column(DateTime(timezone=True),default=now)
UPLOAD_ROOT=pathlib.Path(os.getenv('UPLOAD_DIR','/data/noa_uploads' if os.getenv('RAILWAY_ENVIRONMENT') else './uploads'))
BACKUP_CATEGORIES=['ملابس','دي تي اف','ترويج','خسائر أخرى','مشتريات','سحب خاص']
IMAGE_TYPES={'image/jpeg':'.jpg','image/png':'.png','image/webp':'.webp'}
MAX_UPLOAD=12*1024*1024

def migrate():
 # Additive migrations: never drop old orders, users, or expenses.
 with engine.begin() as conn:
  inspector=inspect(conn)
  for table,col,ddl in [('orders','images',"TEXT DEFAULT '[]'"),('expenses','receipt',"TEXT DEFAULT ''"),('expenses','description',"TEXT DEFAULT ''")]:
   if table in inspector.get_table_names() and col not in {x['name'] for x in inspector.get_columns(table)}:
    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {col} {ddl}'))

def owned_upload(key):
 if not isinstance(key,str) or not key or '/' in key or '..' in key or '\\' in key:raise HTTPException(400,'ملف غير صالح')
 return UPLOAD_ROOT/key

def save_upload(upload):
 if upload.content_type not in IMAGE_TYPES:raise HTTPException(400,'الصورة يجب أن تكون JPG أو PNG أو WEBP')
 data=upload.file.read(MAX_UPLOAD+1)
 if not data or len(data)>MAX_UPLOAD:raise HTTPException(413,'حجم الصورة يتجاوز 12MB')
 # Signature checks prevent arbitrary executable uploads.
 valid=(data.startswith(b'\xff\xd8\xff') if upload.content_type=='image/jpeg' else data.startswith(b'\x89PNG\r\n\x1a\n') if upload.content_type=='image/png' else data.startswith(b'RIFF') and data[8:12]==b'WEBP')
 if not valid:raise HTTPException(400,'محتوى الصورة غير صالح')
 name=uuid.uuid4().hex+IMAGE_TYPES[upload.content_type]
 UPLOAD_ROOT.mkdir(parents=True,exist_ok=True)
 owned_upload(name).write_bytes(data)
 return name

@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 migrate()
 UPLOAD_ROOT.mkdir(parents=True,exist_ok=True)
 with DB() as db:
  # OWNER_EMAIL / OWNER_PASSWORD are the source of truth for owner login.
  # Update existing owner credentials when Railway variables change.
  email=(os.getenv('OWNER_EMAIL') or '').strip().lower()
  password=os.getenv('OWNER_PASSWORD') or ''
  if email and password:
   owner=db.query(User).filter(User.role=='owner').order_by(User.id).first()
   if owner is None:
    owner=User(name='مالك نوا',email=email,password_hash=crypt.hash(password),role='owner',active=1)
    db.add(owner)
   else:
    owner.email=email
    owner.active=1
    if not crypt.verify(password,owner.password_hash):
     owner.password_hash=crypt.hash(password)
   db.commit()
 yield
if os.getenv('RAILWAY_ENVIRONMENT') and (not os.getenv('SESSION_SECRET') or len(os.getenv('SESSION_SECRET','')) < 32):
 raise RuntimeError('Set a strong SESSION_SECRET of at least 32 characters in Railway variables')
app=FastAPI(title='nōa Management',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(SessionMiddleware,secret_key=os.getenv('SESSION_SECRET') or secrets.token_urlsafe(48),https_only=os.getenv('HTTPS_ONLY','true' if os.getenv('RAILWAY_ENVIRONMENT') else 'false').lower()=='true',same_site='lax',max_age=86400)
app.mount('/static',StaticFiles(directory='static'),name='static')
@app.get('/')
def home():return FileResponse('static/index.html')
@app.get('/health')
def health():return {'status':'ok'}
def auth(req,roles=None):
 uid=req.session.get('uid')
 if not uid:raise HTTPException(401,'يرجى تسجيل الدخول')
 with DB() as db:
  u=db.get(User,uid)
  if not u or not u.active:raise HTTPException(401,'الحساب غير متاح')
  if roles and u.role not in roles:raise HTTPException(403,'لا تمتلك الصلاحية')
  return {'id':u.id,'name':u.name,'role':u.role,'email':u.email}
def log(db,u,action,details=''):
 db.add(Audit(user_id=u['id'],action=action,details=details))
def item(x,fields):
 return {k:(getattr(x,k).isoformat() if isinstance(getattr(x,k),datetime.datetime) else getattr(x,k)) for k in fields}
class Login(BaseModel):email:str;password:str
@app.post('/api/login')
def login(data:Login,req:Request):
 with DB() as db:
  u=db.query(User).filter(User.email==data.email.lower().strip()).first()
  if not u or not u.active or not crypt.verify(data.password,u.password_hash):raise HTTPException(401,'البريد أو كلمة المرور غير صحيحة')
  req.session.clear();req.session['uid']=u.id
  return {'ok':True,'name':u.name,'role':u.role}
@app.post('/api/logout')
def logout(req:Request):req.session.clear();return {'ok':True}
@app.get('/api/me')
def me(req:Request):return auth(req)
@app.get('/api/dashboard')
def dashboard(req:Request):
 u=auth(req)
 with DB() as db:
  q=db.query(Order)
  if u['role']=='trader':q=q.filter(Order.created_by==u['id'])
  orders=q.all();completed=[o for o in orders if o.status=='تم التسليم'];revenue=sum(o.price*o.quantity+o.delivery for o in completed);cost=sum(o.cost*o.quantity for o in completed)
  expenses=sum(e.amount for e in db.query(Expense).all()) if u['role']=='owner' else 0
  return {'orders':len(orders),'delivered':len(completed),'pending':sum(o.status not in ['تم التسليم','ملغي','راجع'] for o in orders),'returned':sum(o.status=='راجع' for o in orders),'revenue':revenue if u['role']=='owner' else None,'profit':revenue-cost-expenses if u['role']=='owner' else None,'expenses':expenses if u['role']=='owner' else None,'commission':1500*len(completed) if u['role']=='admin' else None,'recent':[item(o,['id','customer','product_name','status','quantity','created_at'] + (['price'] if u['role']=='owner' else [])) for o in sorted(orders,key=lambda x:x.id,reverse=True)[:7]]}
@app.get('/api/products')
def products(req:Request):
 u=auth(req)
 with DB() as db:
  fields=['id','name','category','colors','sizes']
  if u['role']=='owner':fields.extend(['price','stock','cost'])
  return [item(p,fields) for p in db.query(Product).order_by(Product.id.desc()).all()]
class ProductIn(BaseModel):name:str=Field(min_length=2,max_length=160);category:str='هوديات';price:int=Field(ge=0);cost:int=Field(ge=0);stock:int=Field(ge=0);colors:str='أسود,أبيض';sizes:str='S,M,L,XL,2XL,3XL'
@app.post('/api/products')
def add_product(data:ProductIn,req:Request):
 u=auth(req,['owner'])
 with DB() as db:
  p=Product(**data.model_dump());db.add(p);db.flush();log(db,u,'create_product',str(p.id));db.commit();return {'id':p.id}
@app.get('/api/orders')
def orders(req:Request):
 u=auth(req)
 with DB() as db:
  q=db.query(Order)
  if u['role']=='trader':q=q.filter(Order.created_by==u['id'])
  fields=['id','customer','phone','province','area','landmark','product_id','product_name','color','size','quantity','status','notes','images','created_by','created_at']
  if u['role']=='owner':fields.extend(['price','deposit','delivery','cost'])
  return [item(o,fields) for o in q.order_by(Order.id.desc()).limit(500).all()]
class OrderIn(BaseModel):
 customer:str=Field(min_length=2,max_length=120);phone:str=Field(min_length=7,max_length=40);province:str='';area:str='';landmark:str='';product_id:int; color:str='';size:str='';quantity:int=Field(ge=1,le=1000);price:int=Field(ge=0);deposit:int=Field(ge=0);delivery:int=Field(ge=0);notes:str=''
@app.post('/api/orders')
def add_order(data:OrderIn,req:Request):
 u=auth(req)
 with DB() as db:
  p=db.get(Product,data.product_id)
  if not p:raise HTTPException(404,'المنتج غير موجود')
  d=data.model_dump();
  if u['role']!='owner':d['price']=p.price
  d.update(product_name=p.name,cost=p.cost,created_by=u['id']);o=Order(**d);db.add(o);db.flush();log(db,u,'create_order',str(o.id));db.commit();return {'id':o.id}
class StatusIn(BaseModel):status:str
STATES=['جديد','قيد الطباعة','تم التجهيز','عند شركة التوصيل','تم التسليم','راجع','ملغي']
@app.patch('/api/orders/{oid}/status')
def status(oid:int,data:StatusIn,req:Request):
 u=auth(req,['owner','admin','assistant'])
 if data.status not in STATES:raise HTTPException(400,'حالة غير معتمدة')
 with DB() as db:
  o=db.get(Order,oid)
  if not o:raise HTTPException(404,'الطلب غير موجود')
  previous=o.status;o.status=data.status;log(db,u,'order_status',f'{oid}: {previous} -> {data.status}');db.commit();return {'ok':True}
@app.get('/api/expenses')
def expenses(req:Request):
 auth(req,['owner'])
 with DB() as db:return [item(e,['id','name','category','amount','description','receipt','created_at']) for e in db.query(Expense).order_by(Expense.id.desc()).limit(500).all()]
class ExpenseIn(BaseModel):name:str=Field(min_length=2);category:str='مشتريات';amount:int=Field(gt=0);description:str='';receipt:str=''
@app.post('/api/expenses')
def add_expense(data:ExpenseIn,req:Request):
 u=auth(req,['owner'])
 with DB() as db:
  if data.category not in BACKUP_CATEGORIES:raise HTTPException(400,'تصنيف غير معتمد')
  if data.receipt and not owned_upload(data.receipt).is_file():raise HTTPException(400,'صورة الوصل غير موجودة')
  e=Expense(**data.model_dump(),created_by=u['id']);db.add(e);db.flush();log(db,u,'create_expense',str(e.id));db.commit();return {'id':e.id}
@app.get('/api/users')
def users(req:Request):
 auth(req,['owner'])
 with DB() as db:return [item(u,['id','name','email','role','active','created_at']) for u in db.query(User).order_by(User.id).all()]
class UserIn(BaseModel):name:str=Field(min_length=2);email:str;password:str=Field(min_length=12);role:str
@app.post('/api/users')
def add_user(data:UserIn,req:Request):
 u=auth(req,['owner'])
 if data.role not in ['admin','assistant','trader']:raise HTTPException(400,'دور غير مسموح')
 with DB() as db:
  if db.query(User).filter(User.email==data.email.lower().strip()).first():raise HTTPException(409,'البريد مستخدم')
  x=User(name=data.name,email=data.email.lower().strip(),password_hash=crypt.hash(data.password),role=data.role);db.add(x);db.flush();log(db,u,'create_user',str(x.id));db.commit();return {'id':x.id}
@app.get('/api/audit')
def audit(req:Request):
 auth(req,['owner'])
 with DB() as db:return [item(x,['id','user_id','action','details','created_at']) for x in db.query(Audit).order_by(Audit.id.desc()).limit(100).all()]

@app.post('/api/uploads')
def upload_image(req:Request,file:UploadFile=File(...)):
 auth(req,['owner','admin','assistant','trader'])
 key=save_upload(file)
 return {'key':key,'url':'/api/uploads/'+key}

@app.get('/api/uploads/{key}')
def read_image(key:str,req:Request):
 auth(req)
 path=owned_upload(key)
 if not path.is_file():raise HTTPException(404,'الصورة غير موجودة')
 return FileResponse(path,headers={'Cache-Control':'private, no-store','X-Content-Type-Options':'nosniff'})

class ImagesIn(BaseModel):images:list[str]=Field(max_length=20)
@app.patch('/api/orders/{oid}/images')
def attach_images(oid:int,data:ImagesIn,req:Request):
 u=auth(req,['owner','admin','assistant','trader'])
 with DB() as db:
  o=db.get(Order,oid)
  if not o:raise HTTPException(404,'الطلب غير موجود')
  if u['role']=='trader' and o.created_by!=u['id']:raise HTTPException(403,'ليس طلبك')
  if o.status in ['تم التسليم','راجع','ملغي']:raise HTTPException(409,'لا يمكن تعديل صور الطلب المغلق')
  for key in data.images:
   if not owned_upload(key).is_file():raise HTTPException(400,'إحدى الصور غير موجودة')
  o.images=json.dumps(data.images);log(db,u,'order_images',str(oid));db.commit()
  return {'ok':True}

@app.get('/api/commission')
def commission(req:Request):
 u=auth(req,['admin','owner'])
 with DB() as db:
  q=db.query(Order).filter(Order.status=='تم التسليم')
  if u['role']=='admin':q=q.filter(Order.created_by==u['id'])
  items=q.all()
  return {'rate':1500,'delivered':len(items),'earned':len(items)*1500,'note':'العمولة تُحسب فقط على الطلبات المسلّمة، وتُزال عند تغيير حالتها إلى راجع أو ملغي. لا تشمل تسوية المدفوعات.'}

# Portable JSON backup with uploaded images. Owner only. Do not put secrets in export.
BACKUP_MODELS={'users':User,'products':Product,'orders':Order,'expenses':Expense,'audit':Audit}
def record(model,row):
 return {c.name:(getattr(row,c.name).isoformat() if isinstance(getattr(row,c.name),datetime.datetime) else getattr(row,c.name)) for c in model.__table__.columns}

@app.get('/api/backup')
def backup(req:Request):
 u=auth(req,['owner'])
 with DB() as db:
  payload={'format':'noa-premium-v04','version':1,'created_at':now().isoformat(),'tables':{name:[record(model,r) for r in db.query(model).all()] for name,model in BACKUP_MODELS.items()}}
  log(db,u,'backup_export');db.commit()
 mem=io.BytesIO()
 with zipfile.ZipFile(mem,'w',zipfile.ZIP_DEFLATED) as z:
  z.writestr('data.json',json.dumps(payload,ensure_ascii=False))
  if UPLOAD_ROOT.exists():
   for file in UPLOAD_ROOT.iterdir():
    if file.is_file() and file.suffix.lower() in IMAGE_TYPES.values():z.write(file,'images/'+file.name)
 mem.seek(0)
 return StreamingResponse(mem,media_type='application/zip',headers={'Content-Disposition':'attachment; filename="noa-backup.zip"','Cache-Control':'no-store'})

@app.post('/api/restore/preview')
def restore_preview(req:Request,file:UploadFile=File(...)):
 auth(req,['owner'])
 with zipfile.ZipFile(file.file) as z:
  if 'data.json' not in z.namelist():raise HTTPException(400,'ملف النسخة غير صالح')
  d=json.loads(z.read('data.json'))
  if d.get('format')!='noa-premium-v04':raise HTTPException(400,'نسخة غير متوافقة')
  return {'tables':{k:len(v) for k,v in d['tables'].items()},'images':sum(x.startswith('images/') for x in z.namelist()),'note':'المعاينة فقط؛ الاسترداد يستبدل البيانات الحالية'}

@app.post('/api/restore')
def restore(req:Request,file:UploadFile=File(...),confirm:str=''):
 auth(req,['owner'])
 if confirm!='RESTORE_NOA':raise HTTPException(400,'تأكيد الاسترداد غير صحيح')
 # Limited-size archive, fixed filenames and row schema; reject suspicious zip entries.
 archive=file.file.read(150*1024*1024+1)
 if len(archive)>150*1024*1024:raise HTTPException(413,'النسخة كبيرة جداً للاسترداد من الواجهة')
 with zipfile.ZipFile(io.BytesIO(archive)) as z:
  names=z.namelist()
  if 'data.json' not in names or len(names)>3000 or any(n.startswith('/') or '..' in pathlib.PurePosixPath(n).parts for n in names):raise HTTPException(400,'نسخة غير صالحة')
  if z.getinfo('data.json').file_size>30*1024*1024:raise HTTPException(413,'ملف البيانات كبير')
  d=json.loads(z.read('data.json'))
  if d.get('format')!='noa-premium-v04' or set(d.get('tables',{}))!=set(BACKUP_MODELS):raise HTTPException(400,'نسخة غير متوافقة')
  for n in names:
   if n=='data.json':continue
   key=n.removeprefix('images/')
   if not n.startswith('images/') or '/' in key or pathlib.Path(key).suffix.lower() not in IMAGE_TYPES.values() or z.getinfo(n).file_size>MAX_UPLOAD:raise HTTPException(400,'ملف صورة غير صالح')
  # Import inside one transaction: a database error rolls back the data replacement.
  with DB.begin() as db:
   for model in [Audit,Order,Expense,Product,User]:db.query(model).delete(synchronize_session=False)
   for name in ['users','products','orders','expenses','audit']:
    model=BACKUP_MODELS[name];cols={c.name:c for c in model.__table__.columns}
    for entry in d['tables'][name]:
     if not isinstance(entry,dict) or not set(entry).issubset(cols):raise HTTPException(400,'حقول غير صالحة')
     values={k:(datetime.datetime.fromisoformat(v) if v and isinstance(v,str) and isinstance(cols[k].type,DateTime) else v) for k,v in entry.items()}
     db.add(model(**values))
   db.flush()
  UPLOAD_ROOT.mkdir(parents=True,exist_ok=True)
  for n in names:
   if n.startswith('images/'):
    key=n[7:];owned_upload(key).write_bytes(z.read(n))
  # Ensure PostgreSQL sequences continue above restored IDs.
  if engine.dialect.name=='postgresql':
   with engine.begin() as conn:
    for table in BACKUP_MODELS:
     conn.execute(text("SELECT setval(pg_get_serial_sequence(:t, 'id'), COALESCE((SELECT MAX(id) FROM " + table + "),1), (SELECT COUNT(*)>0 FROM " + table + "))"),{'t':table})
 return {'ok':True,'message':'تم الاسترداد. سجّل الدخول مجدداً إذا تغير حساب المالك.'}
