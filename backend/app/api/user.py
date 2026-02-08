from __future__ import annotations

import json
import time
import uuid

from fastapi import APIRouter, Depends, Request

from app.core.deps import get_current_user
from app.core.response import ResultMessage, ResultStatus
from app.core.security import encrypt_password, token_manager
from app.services.auth_role_service import SysAuthRoleService
from app.services.device_service import SysDeviceService
from app.services.permission_service import SysPermissionService
from app.services.role_service import SysRoleService
from app.services.template_service import SysTemplateService
from app.services.user_auth_service import SysUserAuthService
from app.services.user_service import SysUserService
from app.services.wx_login_service import WxLoginService
from app.utils.captcha_utils import generate_code, send_email_captcha, send_sms_captcha
from app.utils.dto import permission_list_to_dto, role_to_dto, user_to_dto
from app.utils.request_utils import parse_body


router = APIRouter()

user_service = SysUserService()
role_service = SysRoleService()
template_service = SysTemplateService()
device_service = SysDeviceService()
auth_role_service = SysAuthRoleService()
permission_service = SysPermissionService()
user_auth_service = SysUserAuthService()
wx_login_service = WxLoginService()


def _generate_wechat_username(openid: str) -> str:
    base = f"wx_{openid[:10]}"
    username = base
    suffix = 1
    while user_service.select_user_by_username(username):
        username = f"{base}_{suffix}"
        suffix += 1
    return username


def _auto_register_wechat_user(openid: str, union_id: str | None) -> dict | None:
    username = _generate_wechat_username(openid)
    user = {
        "username": username,
        "name": f"微信用户{int(time.time() * 1000) % 10000:04d}",
        "password": encrypt_password(uuid.uuid4().hex),
        "roleId": 2,
        "wxOpenId": openid,
        "wxUnionId": union_id,
    }
    if user_service.add(user) <= 0:
        return None
    return user_service.select_user_by_username(username)


@router.get("/check-token")
async def check_token(request: Request, user=Depends(get_current_user)):
    auth = request.headers.get("authorization", "")
    token = auth.replace("Bearer ", "") if auth else None
    role = auth_role_service.select_by_id(user.get("roleId"))
    permissions = permission_service.select_by_user_id(user.get("userId"))
    permission_tree = permission_service.build_permission_tree(permissions)
    response = {
        "token": token,
        "refreshToken": token,
        "expiresIn": 2592000,
        "userId": user.get("userId"),
        "user": user_to_dto(user),
        "role": role_to_dto(role),
        "permissions": permission_list_to_dto(permission_tree),
    }
    return ResultMessage.success(data=response)


@router.post("/refresh-token")
async def refresh_token(user=Depends(get_current_user), request: Request = None):
    auth = request.headers.get("authorization") if request else None
    token = auth.replace("Bearer ", "") if auth else ""
    new_token = token_manager().refresh_token(token)
    if not new_token:
        return ResultMessage.error("Token刷新失败，请重新登录", code=ResultStatus.UNAUTHORIZED)
    role = auth_role_service.select_by_id(user.get("roleId"))
    permissions = permission_service.select_by_user_id(user.get("userId"))
    permission_tree = permission_service.build_permission_tree(permissions)
    response = {
        "token": new_token,
        "refreshToken": new_token,
        "expiresIn": 2592000,
        "userId": user.get("userId"),
        "user": user_to_dto(user),
        "role": role_to_dto(role),
        "permissions": permission_list_to_dto(permission_tree),
    }
    return ResultMessage.success(data=response)


@router.post("/login")
async def login(request: Request):
    data = await parse_body(request)
    username = data.get("username")
    password = data.get("password")
    if not username or not password:
        return ResultMessage.error("参数错误")
    try:
        user = user_service.login(username, password)
    except ValueError as exc:
        if str(exc) == "UsernameNotFound":
            return ResultMessage.error("用户不存在")
        if str(exc) == "PasswordNotMatch":
            return ResultMessage.error("密码错误")
        return ResultMessage.error("登录失败")
    token = token_manager().create_token(user.get("userId"))
    role = auth_role_service.select_by_id(user.get("roleId"))
    permissions = permission_service.select_by_user_id(user.get("userId"))
    permission_tree = permission_service.build_permission_tree(permissions)
    response = {
        "token": token,
        "refreshToken": token,
        "expiresIn": 2592000,
        "userId": user.get("userId"),
        "user": user_to_dto(user),
        "role": role_to_dto(role),
        "permissions": permission_list_to_dto(permission_tree),
    }
    return ResultMessage.success(data=response)


@router.post("/tel-login")
async def tel_login(request: Request):
    data = await parse_body(request)
    tel = data.get("tel")
    code = data.get("code") or data.get("verifyCode")
    if not tel or not code:
        return ResultMessage.error("参数错误")
    if user_service.query_captcha(code, tel) < 1:
        return ResultMessage.error("验证码错误或已过期")
    user = user_service.select_user_by_tel(tel)
    if not user:
        return ResultMessage(201, "该手机号未注册，请先注册")
    token = token_manager().create_token(user.get("userId"))
    role = auth_role_service.select_by_id(user.get("roleId"))
    permissions = permission_service.select_by_user_id(user.get("userId"))
    permission_tree = permission_service.build_permission_tree(permissions)
    response = {
        "token": token,
        "refreshToken": token,
        "expiresIn": 2592000,
        "userId": user.get("userId"),
        "user": user_to_dto(user),
        "role": role_to_dto(role),
        "permissions": permission_list_to_dto(permission_tree),
    }
    return ResultMessage.success(data=response)


@router.post("/wx-login")
async def wx_login(request: Request):
    data = await parse_body(request)
    code = data.get("code")
    if not code:
        return ResultMessage.error("微信登录code不能为空")

    try:
        wx_login_info = await wx_login_service.get_wx_login_info(str(code))
    except ValueError as exc:
        return ResultMessage.error(str(exc))
    except Exception as exc:
        return ResultMessage.error(f"微信登录失败: {exc}")

    openid = wx_login_info.get("openid")
    union_id = wx_login_info.get("unionid")
    if not openid:
        return ResultMessage.error("获取微信openid失败")

    try:
        user_auth = user_auth_service.select_by_openid_and_platform(openid, "wechat")
    except Exception:
        user_auth = None
    user = None
    is_new_user = False

    if user_auth:
        user_id = user_auth.get("user_id") or user_auth.get("userId")
        if user_id:
            user = user_service.select_user_by_user_id(int(user_id))

    if not user:
        user = user_service.select_user_by_wx_open_id(openid)

    if not user:
        user = _auto_register_wechat_user(openid, union_id)
        is_new_user = True
        if not user:
            return ResultMessage.error("微信登录失败")

    if not user_auth:
        auth_payload = {
            "userId": user.get("userId"),
            "openId": openid,
            "unionId": union_id,
            "platform": "wechat",
            "profile": json.dumps(wx_login_info, ensure_ascii=False),
        }
        try:
            user_auth_service.insert(auth_payload)
        except Exception:
            pass

    if user.get("wxOpenId") != openid or (union_id and user.get("wxUnionId") != union_id):
        user_service.update({"userId": user.get("userId"), "wxOpenId": openid, "wxUnionId": union_id})
        user = user_service.select_user_by_user_id(user.get("userId")) or user

    token = token_manager().create_token(user.get("userId"))
    role = auth_role_service.select_by_id(user.get("roleId"))
    permissions = permission_service.select_by_user_id(user.get("userId"))
    permission_tree = permission_service.build_permission_tree(permissions)
    response = {
        "token": token,
        "refreshToken": token,
        "expiresIn": 2592000,
        "userId": user.get("userId"),
        "isNewUser": is_new_user,
        "user": user_to_dto(user),
        "role": role_to_dto(role),
        "permissions": permission_list_to_dto(permission_tree),
    }
    return ResultMessage.success(data=response)


@router.post("")
async def register(request: Request):
    data = await parse_body(request)
    username = data.get("username")
    password = data.get("password")
    name = data.get("name")
    email = data.get("email")
    tel = data.get("tel")
    code = data.get("code") or data.get("verifyCode")
    if user_service.query_captcha(code, email or tel) < 1:
        return ResultMessage.error("无效验证码")

    user = {
        "username": username,
        "name": name,
        "email": email,
        "tel": tel,
        "password": encrypt_password(password),
        "roleId": 2,
    }
    if user_service.add(user) <= 0:
        return ResultMessage.error("注册失败")

    created = user_service.select_user_by_username(username)
    if not created:
        return ResultMessage.error("注册失败")

    # 复制管理员默认角色和模板
    admin_user_id = 1
    admin_roles = role_service.query({"userId": admin_user_id})
    default_role_id = None
    role_keys = [
        "avatar",
        "roleName",
        "roleDesc",
        "voiceName",
        "ttsPitch",
        "ttsSpeed",
        "modelId",
        "ttsId",
        "sttId",
        "memoryType",
        "temperature",
        "topP",
        "isDefault",
    ]
    for role in admin_roles:
        role_copy = {k: role.get(k) for k in role_keys}
        role_copy["userId"] = created["userId"]
        role_service.add(role_copy)
        if default_role_id is None and role.get("isDefault") == "1":
            default_role_id = role.get("roleId")
    templates = template_service.query(admin_user_id)
    for tpl in templates:
        tpl_copy = {
            "userId": created["userId"],
            "templateName": tpl.get("templateName"),
            "templateDesc": tpl.get("templateDesc"),
            "templateContent": tpl.get("templateContent"),
            "category": tpl.get("category"),
        }
        template_service.add(tpl_copy)

    if default_role_id:
        device_service.add(
            {
                "deviceId": f"user_chat_{created['userId']}",
                "deviceName": "网页聊天",
                "userId": created["userId"],
                "type": "web",
                "state": "0",
                "roleId": default_role_id,
            }
        )

    return ResultMessage.success(user_to_dto(created))


@router.get("")
async def query_users(request: Request, user=Depends(get_current_user)):
    params = request.query_params
    page_num = int(params.get("start", 1))
    page_size = int(params.get("limit", 10))
    filters = {
        "email": params.get("email"),
        "tel": params.get("tel"),
        "name": params.get("name"),
        "isAdmin": params.get("isAdmin"),
    }
    page = user_service.query_users(filters, page_num, page_size)
    return ResultMessage.success(data=page)


@router.put("/{user_id}")
async def update_user(user_id: int, request: Request, current=Depends(get_current_user)):
    data = await parse_body(request)
    user = user_service.select_user_by_user_id(user_id)
    if not user:
        return ResultMessage.error("无此用户，更新失败")
    if data.get("email"):
        existing = user_service.select_user_by_email(data["email"])
        if existing and existing.get("userId") != user_id:
            return ResultMessage.error("邮箱已被其他用户绑定，更新失败")
    if data.get("tel"):
        existing = user_service.select_user_by_tel(data["tel"])
        if existing and existing.get("userId") != user_id:
            return ResultMessage.error("手机号已被其他用户绑定，更新失败")
    update_data = {"userId": user_id}
    for key in ["email", "tel", "avatar", "name"]:
        if data.get(key):
            update_data[key] = data.get(key)
    if data.get("password"):
        update_data["password"] = encrypt_password(data.get("password"))
    if user_service.update(update_data) > 0:
        updated = user_service.select_user_by_user_id(user_id)
        return ResultMessage.success(user_to_dto(updated))
    return ResultMessage.error("更新失败")


@router.post("/resetPassword")
async def reset_password(request: Request):
    data = await parse_body(request)
    email = data.get("email")
    code = data.get("code")
    password = data.get("password")
    if user_service.query_captcha(code, email) < 1:
        return ResultMessage.error("验证码错误或已过期")
    user = user_service.select_user_by_email(email)
    if not user:
        return ResultMessage.error("该邮箱未注册")
    user_service.update({"userId": user["userId"], "password": encrypt_password(password)})
    return ResultMessage.success("密码重置成功")


@router.post("/sendEmailCaptcha")
async def send_email(request: Request):
    data = await parse_body(request)
    email = data.get("email")
    if data.get("type") == "forget":
        existing = user_service.select_user_by_email(email)
        if not existing:
            return ResultMessage.error("该邮箱未注册")
    code = generate_code()
    user_service.generate_code(email, None, code)
    result = send_email_captcha(email, code)
    if result.success:
        return ResultMessage.success()
    return ResultMessage.error(result.message)


@router.post("/sendSmsCaptcha")
async def send_sms(request: Request):
    data = await parse_body(request)
    tel = data.get("tel")
    if data.get("type") == "forget":
        existing = user_service.select_user_by_tel(tel)
        if not existing:
            return ResultMessage.error("该手机号未注册")
    code = generate_code()
    user_service.generate_code(None, tel, code)
    result = send_sms_captcha(tel, code)
    if result.success:
        return ResultMessage.success()
    return ResultMessage.error(result.message)


@router.get("/checkCaptcha")
async def check_captcha(request: Request):
    code = request.query_params.get("code")
    email = request.query_params.get("email")
    tel = request.query_params.get("tel")
    email_or_tel = email or tel
    if not code or not email_or_tel:
        return ResultMessage.error("参数错误")
    if user_service.query_captcha(code, email_or_tel) > 0:
        return ResultMessage.success()
    return ResultMessage.error("验证码错误或已过期")


@router.get("/checkUser")
async def check_user(request: Request):
    username = request.query_params.get("username")
    tel = request.query_params.get("tel")
    email = request.query_params.get("email")
    if not any([username, tel, email]):
        return ResultMessage.error("参数错误")
    if tel and user_service.select_user_by_tel(tel):
        return ResultMessage.error("手机已注册")
    if email and user_service.select_user_by_email(email):
        return ResultMessage.error("邮箱已注册")
    if username and user_service.select_user_by_username(username):
        return ResultMessage.error("用户名已存在")
    return ResultMessage.success()
