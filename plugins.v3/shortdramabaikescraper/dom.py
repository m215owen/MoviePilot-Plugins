from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Dict, Iterator, List, Optional, Union

__all__ = ["Node", "parse_html"]

#: HTML 空元素：没有结束标签，不能压栈
_VOID = frozenset(
    {"img", "br", "meta", "link", "input", "hr", "source", "area", "base", "col", "embed", "param", "track", "wbr"}
)

_WS_RE = re.compile(r"\s+")


class Node:
    __slots__ = ("tag", "attrs", "children", "parent")

    def __init__(self, tag: str, attrs: Optional[Dict[str, str]] = None, parent: Optional["Node"] = None) -> None:
        self.tag = tag
        self.attrs: Dict[str, str] = attrs or {}
        self.children: List[Union["Node", str]] = []
        self.parent = parent

    # ── 属性 ──

    @property
    def classes(self) -> List[str]:
        return (self.attrs.get("class") or "").split()

    def has_class(self, name: str) -> bool:
        return name in self.classes

    def attr(self, name: str, default: str = "") -> str:
        return self.attrs.get(name) or default

    # ── 遍历 ──

    @property
    def text(self) -> str:
        return _WS_RE.sub(" ", self._collect()).strip()

    def _collect(self) -> str:
        parts: List[str] = []
        for child in self.children:
            if isinstance(child, str):
                parts.append(child)
            else:
                parts.append(child._collect())
        return "".join(parts)

    def walk(self) -> Iterator["Node"]:
        for child in self.children:
            if isinstance(child, Node):
                yield child
                yield from child.walk()

    def find_all(self, tag: str = "", cls: str = "") -> List["Node"]:
        result: List[Node] = []
        for node in self.walk():
            if tag and node.tag != tag:
                continue
            if cls and not node.has_class(cls):
                continue
            result.append(node)
        return result

    def find(self, tag: str = "", cls: str = "") -> Optional["Node"]:
        for node in self.walk():
            if tag and node.tag != tag:
                continue
            if cls and not node.has_class(cls):
                continue
            return node
        return None

    @property
    def siblings(self) -> List["Node"]:
        if self.parent is None:
            return []
        return [c for c in self.parent.children if isinstance(c, Node)]

    def next_element(self) -> Optional["Node"]:
        if self.parent is None:
            return None
        items = self.siblings
        for index, item in enumerate(items):
            if item is self and index + 1 < len(items):
                return items[index + 1]
        return self.parent.next_element()

    def __repr__(self) -> str:  # pragma: no cover - 调试便利
        return f"<Node {self.tag} class={' '.join(self.classes)!r} text={self.text[:30]!r}>"


class _TreeBuilder(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.root = Node("root")
        self._stack: List[Node] = [self.root]

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        node = Node(tag.lower(), {str(k).lower(): (v if isinstance(v, str) else "") for k, v in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)
        if tag.lower() not in _VOID:
            self._stack.append(node)

    def handle_startendtag(self, tag: str, attrs: Any) -> None:
        node = Node(tag.lower(), {str(k).lower(): (v if isinstance(v, str) else "") for k, v in attrs}, self._stack[-1])
        self._stack[-1].children.append(node)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in _VOID:
            return
        for index in range(len(self._stack) - 1, 0, -1):
            if self._stack[index].tag == tag:
                del self._stack[index:]
                return

    def handle_data(self, data: str) -> None:
        self._stack[-1].children.append(data)


def parse_html(html: str) -> Node:
    builder = _TreeBuilder()
    try:
        builder.feed(html or "")
        builder.close()
    except Exception:  # noqa: BLE001 - 站点 HTML 不规范，容错优先
        return Node("root")
    return builder.root
