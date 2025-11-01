# main.py

from fastapi import FastAPI, Request, Form, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette import status
from starlette.middleware.sessions import SessionMiddleware
from starlette.templating import Jinja2Templates

# user_db.py와 classroom_db.py에서 함수 가져오기
from user_db import register_user, get_user, get_user_role, Role
from classroom_db import (
    create_classroom, get_classroom, get_all_classrooms,
    update_classroom, delete_classroom
)

app = FastAPI()
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

templates = Jinja2Templates(directory="templates")

# =============================================================
# 헬퍼 함수
# =============================================================

def get_current_user(request: Request) -> dict | None:
    """현재 로그인한 사용자 정보 반환"""
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    
    user = get_user(user_id)
    if user:
        return {
            "user_id": user_id,
            "role": user.get("role")
        }
    return None

def require_auth(request: Request) -> dict:
    """인증이 필요한 엔드포인트에서 사용"""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="로그인이 필요합니다.")
    return user

def require_admin(request: Request) -> dict:
    """관리자 권한이 필요한 엔드포인트에서 사용"""
    user = require_auth(request)
    if user.get("role") != "Admin":
        raise HTTPException(status_code=403, detail="관리자 권한이 필요합니다.")
    return user

# =============================================================
# 1. 인증 관련 엔드포인트
# =============================================================

# GET: 회원가입 폼 페이지 제공
@app.get("/register", response_class=HTMLResponse)
async def get_register_form(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("register.html", {"request": request, "error_message": None})

# POST: 폼 데이터 처리 및 사용자 등록
@app.post("/register")
async def post_register(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...),
    role: Role = Form(...)
):
    if not user_id or not password:
        error_msg = "ID와 비밀번호를 모두 입력해야 합니다."
        return templates.TemplateResponse("register.html", {"request": request, "error_message": error_msg})
    
    if register_user(user_id, password, role):
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)
    else:
        error_msg = f"'{user_id}'는 이미 사용 중인 ID입니다."
        return templates.TemplateResponse("register.html", {"request": request, "error_message": error_msg})

# GET: 로그인 폼 페이지 제공
@app.get("/login", response_class=HTMLResponse)
async def get_login_form(request: Request):
    user = get_current_user(request)
    if user:
        return RedirectResponse(url="/", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse("login.html", {"request": request, "error_message": None})

# POST: 폼 데이터 처리 및 사용자 인증
@app.post("/login")
async def post_login(
    request: Request,
    user_id: str = Form(...),
    password: str = Form(...)
):
    user = get_user(user_id)
    
    if not user or user.get("password") != password:
        error_msg = "ID 또는 비밀번호가 올바르지 않습니다."
        return templates.TemplateResponse("login.html", {"request": request, "error_message": error_msg})
    
    # 세션에 사용자 정보 저장
    request.session["user_id"] = user_id
    request.session["role"] = user.get("role")
    
    return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

# 로그아웃
@app.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)

# =============================================================
# 2. 메인 페이지
# =============================================================

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    user = get_current_user(request)
    if not user:
        return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)
    
    return templates.TemplateResponse("index.html", {
        "request": request,
        "user": user
    })

# =============================================================
# 3. 강의실 관리
# =============================================================

# 강의실 목록 조회 (모든 로그인 사용자 가능)
@app.get("/classrooms", response_class=HTMLResponse)
async def list_classrooms(request: Request):
    require_auth(request)  # 로그인만 필요 (학생도 조회 가능)
    classrooms = get_all_classrooms()
    return templates.TemplateResponse("classrooms.html", {
        "request": request,
        "classrooms": classrooms,
        "user": get_current_user(request)
    })

# 강의실 생성 폼
@app.get("/classrooms/create", response_class=HTMLResponse)
async def create_classroom_form(request: Request):
    require_admin(request)
    return templates.TemplateResponse("classroom_form.html", {
        "request": request,
        "user": get_current_user(request),
        "classroom": None,
        "mode": "create"
    })

# 강의실 생성
@app.post("/classrooms/create")
async def create_classroom_post(
    request: Request,
    name: str = Form(...),
    location: str = Form(...),
    capacity: int = Form(...),
    projector: bool = Form(default=False),
    whiteboard: bool = Form(default=False)
):
    require_admin(request)
    
    equipment = {}
    if projector:
        equipment["projector"] = True
    if whiteboard:
        equipment["whiteboard"] = True
    
    classroom_id = create_classroom(name, location, capacity, equipment)
    return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)

# 강의실 수정 폼
@app.get("/classrooms/{classroom_id}/edit", response_class=HTMLResponse)
async def edit_classroom_form(request: Request, classroom_id: int):
    require_admin(request)
    classroom = get_classroom(classroom_id)
    if not classroom:
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    return templates.TemplateResponse("classroom_form.html", {
        "request": request,
        "user": get_current_user(request),
        "classroom": classroom,
        "classroom_id": classroom_id,
        "mode": "edit"
    })

# 강의실 수정
@app.post("/classrooms/{classroom_id}/edit")
async def edit_classroom_post(
    request: Request,
    classroom_id: int,
    name: str = Form(...),
    location: str = Form(...),
    capacity: int = Form(...),
    projector: bool = Form(default=False),
    whiteboard: bool = Form(default=False)
):
    require_admin(request)
    
    equipment = {}
    if projector:
        equipment["projector"] = True
    if whiteboard:
        equipment["whiteboard"] = True
    
    if not update_classroom(classroom_id, name, location, capacity, equipment):
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)

# 강의실 삭제
@app.post("/classrooms/{classroom_id}/delete")
async def delete_classroom_post(request: Request, classroom_id: int):
    require_admin(request)
    
    if not delete_classroom(classroom_id):
        raise HTTPException(status_code=404, detail="강의실을 찾을 수 없습니다.")
    
    return RedirectResponse(url="/classrooms", status_code=status.HTTP_303_SEE_OTHER)
