# -*- coding: utf-8 -*-
from dataclasses import asdict, dataclass


@dataclass
class Contacto:
    id: str
    email: str
    etiqueta: str
    tipo: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
