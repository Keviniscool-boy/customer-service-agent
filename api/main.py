from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, Field

from agent.chat import EcomAgent
from agent.presentation import visible_reply
from agent.database import (
    create_session,
    create_order,
    delete_session,
    get_connection,
    get_user_by_id,
    init_db,
    load_messages,
    list_orders_for_user,
    list_refunds_for_user,
    session_belongs_to_user,
    transition_order_status,
)
from api.auth import (
    authenticate_user,
    create_access_token,
    decode_access_token,
    register_user,
)
from config.settings import settings


app = FastAPI(title="Ecom Service Agent")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        origin.strip()
        for origin in settings.cors_origins.split(",")
        if origin.strip()
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
bearer_scheme = HTTPBearer(auto_error=False)


def error_body(code: str, message: str, details=None) -> dict:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}


@app.exception_handler(HTTPException)
async def http_exception_handler(
    request: Request,
    exc: HTTPException,
) -> JSONResponse:
    code_by_status = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
    }
    code = code_by_status.get(exc.status_code, "HTTP_ERROR")
    if isinstance(exc.detail, str):
        message = exc.detail
        details = None
    else:
        message = "请求失败"
        details = jsonable_encoder(exc.detail)
    return JSONResponse(
        status_code=exc.status_code,
        content=error_body(code, message, details),
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_body(
            "VALIDATION_ERROR",
            "请求参数错误",
            jsonable_encoder(exc.errors()),
        ),
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_body("INTERNAL_SERVER_ERROR", "服务器内部错误"),
    )


class Credentials(BaseModel):
    username: str
    password: str


class ChatRequest(BaseModel):
    message: str
    session_id: str | None = None


class SessionCreateRequest(BaseModel):
    title: str | None = None


class OrderCreateRequest(BaseModel):
    product_name: str = Field(min_length=1)
    amount: float = Field(gt=0)
    tracking_number: str | None = None
    shipping_address: str | None = None


class RefundCreateRequest(BaseModel):
    reason: str = Field(min_length=1)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/products")
def list_products(keyword: str = ""):
    from agent.database import search_products

    return {"products": search_products(keyword)}


@app.post("/register")
def register(credentials: Credentials):
    try:
        user = register_user(credentials.username, credentials.password)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return {"user": user}


@app.post("/login")
def login(credentials: Credentials):
    user = authenticate_user(credentials.username, credentials.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": user,
    }


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供认证信息",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        token = credentials.credentials
        payload = decode_access_token(token)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Token 缺少用户信息")
        user = get_user_by_id(user_id)
        if user is None:
            raise ValueError("用户不存在")
        return user
    except Exception as error:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token 无效或已过期",
        ) from error


def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="需要管理员权限")
    return user


@app.get("/me")
def me(user: dict = Depends(get_current_user)):
    return {"user": user}


@app.get("/admin/summary")
def admin_summary(user: dict = Depends(require_admin)):
    connection = get_connection()
    summary = {}
    for table in ("users", "orders", "refunds", "sessions"):
        summary[table] = connection.execute(
            f"SELECT COUNT(*) AS count FROM {table}"
        ).fetchone()["count"]
    connection.close()
    return {"summary": summary}


@app.get("/admin/users")
def admin_users(user: dict = Depends(require_admin)):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, username, role, created_at
        FROM users
        ORDER BY created_at DESC
        """
    ).fetchall()
    connection.close()
    return {"users": [dict(row) for row in rows]}


@app.get("/admin/orders")
def admin_orders(user: dict = Depends(require_admin)):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT orders.order_id, orders.product_name, orders.status,
               orders.amount, orders.tracking_number,
               orders.shipping_address, users.username
        FROM orders
        LEFT JOIN users ON users.id = orders.user_id
        ORDER BY orders.order_id DESC
        """
    ).fetchall()
    connection.close()
    return {"orders": [dict(row) for row in rows]}


@app.get("/admin/refunds")
def admin_refunds(user: dict = Depends(require_admin)):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT refunds.refund_id, refunds.order_id, refunds.amount,
               refunds.reason, refunds.status, refunds.created_at,
               users.username
        FROM refunds
        LEFT JOIN users ON users.id = refunds.user_id
        ORDER BY refunds.created_at DESC
        """
    ).fetchall()
    connection.close()
    return {"refunds": [dict(row) for row in rows]}


@app.get("/admin/sessions")
def admin_sessions(user: dict = Depends(require_admin)):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT sessions.id, sessions.title, sessions.summary,
               sessions.created_at, sessions.updated_at,
               users.username, COUNT(messages.id) AS message_count
        FROM sessions
        LEFT JOIN users ON users.id = sessions.user_id
        LEFT JOIN messages ON messages.session_id = sessions.id
        GROUP BY sessions.id
        ORDER BY sessions.updated_at DESC, sessions.created_at DESC
        """
    ).fetchall()
    connection.close()
    return {"sessions": [dict(row) for row in rows]}


@app.get("/admin/sessions/{session_id}/messages")
def admin_session_messages(
    session_id: str,
    user: dict = Depends(require_admin),
):
    connection = get_connection()
    session = connection.execute(
        "SELECT id FROM sessions WHERE id = ?",
        (session_id,),
    ).fetchone()
    if session is None:
        connection.close()
        raise HTTPException(status_code=404, detail="会话不存在")

    rows = connection.execute(
        """
        SELECT role, content, created_at
        FROM messages
        WHERE session_id = ? AND role IN ('user', 'assistant')
        ORDER BY id ASC
        """,
        (session_id,),
    ).fetchall()
    connection.close()
    messages = [
        {
            "role": row["role"],
            "content": (
                visible_reply(row["content"])
                if row["role"] == "assistant"
                else row["content"]
            ),
            "created_at": row["created_at"],
        }
        for row in rows
    ]
    return {"messages": messages}


@app.get("/orders")
def list_orders(user: dict = Depends(get_current_user)):
    return {"orders": list_orders_for_user(user["id"])}


@app.get("/orders/{order_id}")
def get_order_detail(
    order_id: str,
    user: dict = Depends(get_current_user),
):
    from agent.database import get_order_for_user

    order = get_order_for_user(order_id, user["id"])
    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"order": order}


@app.post("/orders")
def create_new_order(
    request: OrderCreateRequest,
    user: dict = Depends(get_current_user),
):
    order_id = create_order(
        user_id=user["id"],
        order_id=None,
        product_name=request.product_name,
        status="待发货",
        amount=request.amount,
        tracking_number=request.tracking_number,
        shipping_address=request.shipping_address,
    )
    return {
        "order": {
            "order_id": order_id,
            "product_name": request.product_name,
            "status": "待发货",
            "amount": request.amount,
            "tracking_number": request.tracking_number,
            "shipping_address": request.shipping_address,
        }
    }


@app.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: str,
    user: dict = Depends(get_current_user),
):
    try:
        order = transition_order_status(
            order_id,
            user["id"],
            "已取消",
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    if order is None:
        raise HTTPException(status_code=404, detail="订单不存在")
    return {"order": order}


@app.get("/refunds")
def list_refunds(user: dict = Depends(get_current_user)):
    return {"refunds": list_refunds_for_user(user["id"])}


@app.post("/orders/{order_id}/refunds")
def create_order_refund(
    order_id: str,
    request: RefundCreateRequest,
    user: dict = Depends(get_current_user),
):
    from agent.tools.refund import apply_refund

    result = apply_refund(order_id, request.reason, user_id=user["id"])
    if not result["success"]:
        status_code = 404 if result["message"].startswith("没有找到订单") else 400
        raise HTTPException(status_code=status_code, detail=result["message"])
    return result


@app.get("/sessions")
def list_sessions(user: dict = Depends(get_current_user)):
    connection = get_connection()
    rows = connection.execute(
        """
        SELECT id, title, summary, created_at, updated_at
        FROM sessions
        WHERE user_id = ?
        ORDER BY updated_at DESC, created_at DESC
        """,
        (user["id"],),
    ).fetchall()
    connection.close()
    return {"sessions": [dict(row) for row in rows]}


@app.post("/sessions")
def create_new_session(
    request: SessionCreateRequest,
    user: dict = Depends(get_current_user),
):
    session_id = create_session(user["id"], request.title)
    return {"session_id": session_id, "title": request.title}


@app.get("/sessions/{session_id}/messages")
def list_session_messages(
    session_id: str,
    user: dict = Depends(get_current_user),
):
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")

    messages = [
        {
            **message,
            "content": (
                visible_reply(message.get("content"))
                if message.get("role") == "assistant"
                else message.get("content", "")
            ),
        }
        for message in load_messages(session_id)
        if message.get("role") in {"user", "assistant"}
        and message.get("content")
    ]
    return {"messages": messages}


@app.delete("/sessions/{session_id}")
def remove_session(session_id: str, user: dict = Depends(get_current_user)):
    if not session_belongs_to_user(session_id, user["id"]):
        raise HTTPException(status_code=404, detail="会话不存在")
    delete_session(session_id)
    return {"success": True}


@app.post("/chat")
def chat(request: ChatRequest, user: dict = Depends(get_current_user)):
    agent = EcomAgent(user_id=user["id"], session_id=request.session_id)
    response = agent.chat(request.message)
    return PlainTextResponse(content=visible_reply(response.reply))
