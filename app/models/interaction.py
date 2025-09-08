from typing import Optional
from pydantic import BaseModel


class Position(BaseModel):
    x: Optional[int] = None
    y: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None


class Coordinate(BaseModel):
    x: Optional[float] = None
    y: Optional[float] = None


class Parent(BaseModel):
    tagName: Optional[str] = None
    id: Optional[str] = None
    className: Optional[str] = None


class Form(BaseModel):
    action: Optional[str] = None
    id: Optional[str] = None
    method: Optional[str] = None


class DomInfo(BaseModel):
    tagName: Optional[str] = None
    id: Optional[str] = None
    className: Optional[str] = None
    type: Optional[str] = None
    name: Optional[str] = None
    value: Optional[str] = None
    textContent: Optional[str] = None
    placeholder: Optional[str] = None
    href: Optional[str] = None
    position: Optional[Position] = None
    disabled: Optional[bool] = None
    readonly: Optional[bool] = None
    checked: Optional[bool] = None
    required: Optional[bool] = None
    visible: Optional[bool] = None
    parent: Optional[Parent] = None
    form: Optional[Form] = None


class EventData(BaseModel):
    nodeId: Optional[int] = None
    coordinates: Optional[Coordinate] = None


class PageContext(BaseModel):
    url: Optional[str] = None
    path: Optional[str] = None
    title: Optional[str] = None
    domain: Optional[str] = None


class InteractionEvent(BaseModel):
    user: Optional[str] = None
    timestamp: Optional[int] = None
    source: Optional[str] = None
    sessionId: Optional[str] = None
    sessionDuration: Optional[int] = None
    pageContext: Optional[PageContext] = None
    domInfo: Optional[DomInfo] = None
    eventData: Optional[EventData] = None
    interactionType: Optional[int] = None
    inputType: Optional[str] = None
    inputValue: Optional[str] = None
