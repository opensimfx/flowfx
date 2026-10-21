import logging

log = logging.getLogger("flowfx")
if not log.handlers:
    _h = logging.StreamHandler()
    _h.setFormatter(logging.Formatter("[FlowFX] %(levelname)s %(message)s"))
    log.addHandler(_h)
    log.setLevel(logging.INFO)
