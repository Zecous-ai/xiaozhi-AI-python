from __future__ import annotations

import json
import logging
from typing import Dict, List, Optional

from app.dialogue.tools import ToolCallback, ToolContext
from app.dialogue.message_service import MessageService

TAG = "IotService"
logger = logging.getLogger("iot_service")


class IotService:
    def __init__(self, session_manager, message_service: MessageService) -> None:
        self.session_manager = session_manager
        self.message_service = message_service

    def handle_device_descriptors(self, session_id: str, descriptors: List[Dict]) -> None:
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        for descriptor in descriptors:
            name = descriptor.get("name")
            if not name:
                continue
            session.iot_descriptors[name] = descriptor
            self._register_function_tools(session, descriptor)

    def handle_device_states(self, session_id: str, states: List[Dict]) -> None:
        session = self.session_manager.get_session(session_id)
        if not session:
            return
        for state in states:
            name = state.get("name")
            props = state.get("state") or {}
            descriptor = session.iot_descriptors.get(name)
            if not descriptor:
                logger.error("[%s] - SessionId: %s 未找到设备 %s 的描述信息", TAG, session_id, name)
                continue
            properties = descriptor.get("properties") or {}
            for prop_name, value in props.items():
                prop = properties.get(prop_name)
                if prop is not None:
                    prop["value"] = value
                    logger.info(
                        "[%s] - SessionId: %s handleDeviceStates 物联网状态更新: %s , %s = %s",
                        TAG,
                        session_id,
                        name,
                        prop_name,
                        value,
                    )
                else:
                    logger.error(
                        "[%s] - SessionId: %s handleDeviceStates 未找到设备 %s 的属性 %s",
                        TAG,
                        session_id,
                        name,
                        prop_name,
                    )

    def get_iot_status(self, session_id: str, iot_name: str, prop_name: str) -> Optional[object]:
        session = self.session_manager.get_session(session_id)
        if not session:
            return None
        descriptor = session.iot_descriptors.get(iot_name)
        if not descriptor:
            logger.error("[%s] - SessionId: %s getIotStatus 未找到设备 %s", TAG, session_id, iot_name)
            return None
        prop = (descriptor.get("properties") or {}).get(prop_name)
        if prop is None:
            logger.error(
                "[%s] - SessionId: %s getIotStatus 未找到设备 %s 的属性 %s",
                TAG,
                session_id,
                iot_name,
                prop_name,
            )
            return None
        return prop.get("value")

    def set_iot_status(self, session_id: str, iot_name: str, prop_name: str, value: object) -> bool:
        session = self.session_manager.get_session(session_id)
        if not session:
            return False
        descriptor = session.iot_descriptors.get(iot_name)
        if not descriptor:
            return False
        prop = (descriptor.get("properties") or {}).get(prop_name)
        if prop is None:
            logger.error(
                "[%s] - SessionId: %s setIotStatus 未找到设备 %s 的属性 %s",
                TAG,
                session_id,
                iot_name,
                prop_name,
            )
            return False
        prop_type = prop.get("type")
        if not self._type_match(prop_type, value):
            value_type = type(value).__name__ if value is not None else "NoneType"
            logger.error(
                "[%s] - SessionId: %s setIotStatus 属性 %s 的值类型不匹配, 注册类型: %s, 入参类型: %s",
                TAG,
                session_id,
                prop_name,
                prop_type,
                value_type,
            )
            return False
        prop["value"] = value
        logger.info(
            "[%s] - SessionId: %s setIotStatus 物联网状态更新: %s , %s = %s",
            TAG,
            session_id,
            iot_name,
            prop_name,
            value,
        )
        self.send_iot_message(session_id, iot_name, prop_name, {prop_name: value})
        return True

    def send_iot_message(self, session_id: str, iot_name: str, method_name: str, params: Dict) -> bool:
        try:
            logger.info(
                "[%s] - SessionId: %s, message send iotName: %s, methodName: %s, parameters: %s",
                TAG,
                session_id,
                iot_name,
                method_name,
                json.dumps(params, ensure_ascii=False),
            )
            session = self.session_manager.get_session(session_id)
            if not session:
                return False
            descriptor = session.iot_descriptors.get(iot_name)
            if not descriptor:
                return False
            methods = descriptor.get("methods") or {}
            if method_name not in methods:
                logger.error("[%s] - SessionId: %s, %s method not found: %s", TAG, session_id, iot_name, method_name)
                return False
            command = {"name": iot_name, "method": method_name, "parameters": params}
            return self.message_service.send_iot_command(session, [command])
        except Exception:
            logger.exception("[%s] - SessionId: %s, error sending Iot message", TAG, session_id)
        return False

    def _register_function_tools(self, session, descriptor: Dict) -> None:
        tools_holder = session.tools_session_holder
        if not tools_holder:
            return
        iot_name = descriptor.get("name")
        properties = descriptor.get("properties") or {}
        methods = descriptor.get("methods") or {}

        for prop_name, prop_info in properties.items():
            func_name = f"iot_get_{iot_name.lower()}_{prop_name.lower()}"
            schema = {
                "type": "object",
                "properties": {
                    "response_success": {
                        "type": "string",
                        "description": "查询成功时的友好回复，必须使用{value}作为占位符表示查询到的值",
                    }
                },
                "required": ["response_success"],
            }

            def _handler(params: Dict, context: ToolContext, _prop=prop_name) -> str:
                value = self.get_iot_status(session.session_id, iot_name, _prop)
                if value is None:
                    return "无法获取设置"
                resp = params.get("response_success")
                if resp:
                    if "{value}" in resp:
                        resp = resp.replace("{value}", str(value))
                    return resp
                return f"当前的设置为{value}"

            tool = ToolCallback(
                name=func_name,
                description=f"查询{iot_name}的{prop_info.get('description') or prop_name}",
                input_schema=schema,
                handler=_handler,
                return_direct=True,
            )
            tools_holder.register_function(func_name, tool)

        for method_name, method_info in methods.items():
            func_name = f"iot_{iot_name}_{method_name}"
            params_schema = method_info.get("parameters") or {}
            if params_schema:
                param_name, param_info = next(iter(params_schema.items()))
            else:
                param_name, param_info = "value", {"type": "string", "description": "参数"}
            schema = {
                "type": "object",
                "properties": {
                    param_name: {
                        "type": param_info.get("type") or "string",
                        "description": param_info.get("description") or "",
                    },
                    "response_success": {
                        "type": "string",
                        "description": "操作成功时的友好回复,关于该设备的操作结果，设备名称使用description中的名称，不要出现占位符",
                    },
                },
                "required": [param_name, "response_success"],
            }

            def _handler(params: Dict, context: ToolContext, _param=param_name, _method=method_name) -> str:
                response_success = params.get("response_success")
                params = dict(params)
                params.pop("response_success", None)
                result = self.send_iot_message(session.session_id, iot_name, _method, params)
                if result:
                    if not response_success:
                        response_success = "操作成功"
                    return response_success
                return "操作失败"

            tool = ToolCallback(
                name=func_name,
                description=f"{descriptor.get('description') or iot_name} - {method_info.get('description') or method_name}",
                input_schema=schema,
                handler=_handler,
                return_direct=True,
            )
            tools_holder.register_function(func_name, tool)

    @staticmethod
    def _type_match(prop_type: Optional[str], value: object) -> bool:
        if not prop_type:
            return False
        prop_type = prop_type.lower()
        if prop_type == "object":
            return True
        if prop_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if prop_type == "string":
            return isinstance(value, str)
        if prop_type == "boolean":
            return isinstance(value, bool)
        return False


__all__ = ["IotService"]
