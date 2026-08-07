"""Standalone static validation for Luna external audio routing."""

from __future__ import annotations

import ast
from pathlib import Path


SOURCE_PATH = (
    Path(__file__).parents[1]
    / "custom_components"
    / "luna_assistant"
    / "conversation.py"
)
SOURCE = SOURCE_PATH.read_text(encoding="utf-8")
TREE = ast.parse(SOURCE)


class RoutingVisitor(ast.NodeVisitor):
    """Collect relevant service-call data from routing helpers."""

    def __init__(self) -> None:
        self.current_function: str | None = None
        self.microsoft_entity_id_value: str | None = None
        self.luna_media_player_value: str | None = None
        self.has_microsoft_service_check = False

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        previous = self.current_function
        self.current_function = node.name
        self.generic_visit(node)
        self.current_function = previous

    def visit_Call(self, node: ast.Call) -> None:
        if self.current_function == "_async_route_with_microsoft_tts":
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "has_service"
            ):
                self.has_microsoft_service_check = True

            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "async_call"
                and len(node.args) >= 3
                and isinstance(node.args[2], ast.Dict)
            ):
                for key, value in zip(node.args[2].keys, node.args[2].values):
                    if isinstance(key, ast.Name) and key.id == "ATTR_ENTITY_ID":
                        if isinstance(value, ast.Name):
                            self.microsoft_entity_id_value = value.id

        if self.current_function == "_async_route_with_luna_tts":
            if (
                isinstance(node.func, ast.Attribute)
                and node.func.attr == "async_call"
                and len(node.args) >= 3
                and isinstance(node.args[2], ast.Dict)
            ):
                for key, value in zip(node.args[2].keys, node.args[2].values):
                    if (
                        isinstance(key, ast.Name)
                        and key.id == "ATTR_MEDIA_PLAYER_ENTITY_ID"
                        and isinstance(value, ast.Name)
                    ):
                        self.luna_media_player_value = value.id

        self.generic_visit(node)


visitor = RoutingVisitor()
visitor.visit(TREE)

assert visitor.has_microsoft_service_check
assert visitor.microsoft_entity_id_value == "target_entity_id"
assert visitor.luna_media_player_value == "target_entity_id"
assert "media_player_state.entity_id" in SOURCE
assert ".name" not in SOURCE
assert "friendly_name" not in SOURCE.replace(
    'friendly name shown in the UI', ''
).replace('friendly/display name', '')
assert "LOGGER," in SOURCE

print("Luna external audio routing validation passed.")
