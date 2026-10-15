import os, secrets, datetime, json
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, ForeignKey, Text, func, select
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
 id=Column(Integer,primary_key=True); customer=Column(String(120),nullable=False); phone=Column(String(40),nullable=False); province=Column(String(80),default=''); area=Column(String(160),default=''); landmark=Column(String(160),default=''); product_id=Column(Integer,ForeignKey('products.id')); product_name=Column(String(160),default=''); color=Column(String(60),default=''); size=Column(String(20),default=''); quantity=Column(Integer,default=1); price=Column(Integer,default=0); cost=Column(Integer,default=0); deposit=Column(Integer,default=0); delivery=Column(Integer,default=0); status=Column(String(40),default='جديد'); notes=Column(Text,default=''); created_by=Column(Integer,ForeignKey('users.id')); created_at=Column(DateTime(timezone=True),default=now)
class Expense(Base):
 __tablename__='expenses'
 id=Column(Integer,primary_key=True); name=Column(String(160),nullable=False); category=Column(String(80),default='عام'); amount=Column(Integer,default=0); created_by=Column(Integer,ForeignKey('users.id')); created_at=Column(DateTime(timezone=True),default=now)
class Audit(Base):
 __tablename__='audit'
 id=Column(Integer,primary_key=True); user_id=Column(Integer); action=Column(String(100)); details=Column(Text); created_at=Column(DateTime(timezone=True),default=now)
@asynccontextmanager
async def lifespan(app):
 Base.metadata.create_all(engine)
 with DB() as db:
  if not db.query(User).first():
   email=os.getenv('OWNER_EMAIL');password=os.getenv('OWNER_PASSWORD')
   if email and password and len(password)>=12:
    db.add(User(name='مالك نوا',email=email.lower().strip(),password_hash=crypt.hash(password),role='owner'));db.commit()
 yield
if os.getenv('RAILWAY_ENVIRONMENT') and (not os.getenv('SESSION_SECRET') or len(os.getenv('SESSION_SECRET','')) < 32):
 raise RuntimeError('Set a strong SESSION_SECRET of at least 32 characters in Railway variables')
app=FastAPI(title='nōa Management',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(SessionMiddleware,secret_key=os.getenv('SESSION_SECRET') or secrets.token_urlsafe(48),https_only=os.getenv('HTTPS_ONLY','false').lower()=='true',same_site='lax',max_age=86400)
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
  return {'orders':len(orders),'delivered':len(completed),'pending':sum(o.status not in ['تم التسليم','ملغي','راجع'] for o in orders),'returned':sum(o.status=='راجع' for o in orders),'revenue':revenue if u['role']!='assistant' else None,'profit':revenue-cost-expenses if u['role']=='owner' else None,'expenses':expenses if u['role']=='owner' else None,'recent':[item(o,['id','customer','product_name','status','price','quantity','created_at']) for o in sorted(orders,key=lambda x:x.id,reverse=True)[:7]]}
@app.get('/api/products')
def products(req:Request):
 u=auth(req)
 with DB() as db:
  fields=['id','name','category','price','stock','colors','sizes']
  if u['role']=='owner':fields.append('cost')
  return [item(p,fields) for p in db.query(Product).order_by(Product.id.desc()).all()]
class ProductIn(BaseModel):name:str=Field(min_length=2,max_length=160);category:str='هوديات';price:int=Field(ge=0);cost:int=Field(ge=0);stock:int=Field(ge=0);colors:str='أسود,أبيض';sizes:str='S,M,L,XL,2XL,3XL'
@app.post('/api/products')
def add_product(data:ProductIn,req:Request):
 u=auth(req,['owner','admin'])
 with DB() as db:
  p=Product(**data.model_dump());db.add(p);db.flush();log(db,u,'create_product',str(p.id));db.commit();return {'id':p.id}
@app.get('/api/orders')
def orders(req:Request):
 u=auth(req)
 with DB() as db:
  q=db.query(Order)
  if u['role']=='trader':q=q.filter(Order.created_by==u['id'])
  fields=['id','customer','phone','province','area','landmark','product_id','product_name','color','size','quantity','price','deposit','delivery','status','notes','created_by','created_at']
  if u['role']=='owner':fields.append('cost')
  return [item(o,fields) for o in q.order_by(Order.id.desc()).limit(500).all()]
class OrderIn(BaseModel):
 customer:str=Field(min_length=2,max_length=120);phone:str=Field(min_length=7,max_length=40);province:str='';area:str='';landmark:str='';product_id:int; color:str='';size:str='';quantity:int=Field(ge=1,le=1000);price:int=Field(ge=0);deposit:int=Field(ge=0);delivery:int=Field(ge=0);notes:str=''
@app.post('/api/orders')
def add_order(data:OrderIn,req:Request):
 u=auth(req)
 with DB() as db:
  p=db.get(Product,data.product_id)
  if not p:raise HTTPException(404,'المنتج غير موجود')
  d=data.model_dump();d.update(product_name=p.name,cost=p.cost,created_by=u['id']);o=Order(**d);db.add(o);db.flush();log(db,u,'create_order',str(o.id));db.commit();return {'id':o.id}
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
 with DB() as db:return [item(e,['id','name','category','amount','created_at']) for e in db.query(Expense).order_by(Expense.id.desc()).limit(500).all()]
class ExpenseIn(BaseModel):name:str=Field(min_length=2);category:str='عام';amount:int=Field(gt=0)
@app.post('/api/expenses')
def add_expense(data:ExpenseIn,req:Request):
 u=auth(req,['owner'])
 with DB() as db:
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
