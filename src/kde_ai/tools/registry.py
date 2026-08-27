from __future__ import annotations

from kde_ai import rag
from kde_ai.tools import (
    edit_config,
    kde_settings,
    ocr,
    open_url,
    pacman_mutate,
    plasma_script,
    privileged,
    propose_solved,
    readonly,
    system_info,
    websearch,
)

HANDLERS = {
    "system_info": system_info.handle,
    "run_readonly_cmd": readonly.handle,
    "search_bugzilla": websearch.search_bugzilla,
    "search_invent": websearch.search_invent,
    "open_url": open_url.handle,
    "kde_settings_hint": kde_settings.handle,
    "propose_solved": propose_solved.handle,
    "run_privileged_cmd": privileged.handle,
    "pacman_mutate": pacman_mutate.handle,
    "edit_config": edit_config.handle,
    "plasma_script": plasma_script.handle,
    "screenshot_ocr": ocr.handle,
    "search_docs": rag.handle,
}

SCHEMAS = [
    system_info.SCHEMA,
    readonly.SCHEMA,
    websearch.BUGZILLA_SCHEMA,
    websearch.INVENT_SCHEMA,
    open_url.SCHEMA,
    kde_settings.SCHEMA,
    propose_solved.SCHEMA,
    privileged.SCHEMA,
    pacman_mutate.SCHEMA,
    edit_config.SCHEMA,
    plasma_script.SCHEMA,
    ocr.SCHEMA,
    rag.SCHEMA,
]
