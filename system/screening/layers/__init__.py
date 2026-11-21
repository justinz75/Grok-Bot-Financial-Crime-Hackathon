"""Optional layers on top of the rules.

The rules decide. A layer adds to what an analyst sees, and each one can be switched
off, on, or to enforce, so its effect can be measured on its own:

    score      strength-of-evidence score (arithmetic, no model)
    briefing   what decided the hit, what was missing, what would settle it
    reviewer   a language model's second opinion on each clearance
    reader     a language model reads identity notes the patterns cannot

    off        the layer does not run
    on         it annotates the explain file and changes nothing that is scored
               (for the reader: what it reads may support a match but never clear one)
    enforce    it may also turn a clearance into a review
               (for the reader: what it reads counts in full)

No layer can ever create a clearance. Modes come from the SCREENING_LAYERS environment
variable ("score=on,reviewer=enforce"), else system/layers.json, else the defaults.

A layer module provides build(store, mode), returning an object with
    annotate(case) -> dict or None      one person against one hit
    guard(case, note) -> str or None    optional: why this clearance needs a person
The reader module's build(store, mode) returns a function with the signature of
extract.read_identity_note.
"""
import importlib
import json
import os

ORDER = ("score", "reviewer", "briefing")  # the briefing runs last so it can quote the others
NAMES = ORDER + ("reader",)
DEFAULTS = {"score": "on", "briefing": "on", "reviewer": "off", "reader": "off"}
_MODES = {
    "off": "off", "0": "off", "false": "off", "no": "off",
    "on": "on", "1": "on", "true": "on", "yes": "on", "shadow": "on", "safe": "on",
    "enforce": "enforce", "trust": "enforce",
}
CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "layers.json")


def config(text=None):
    """The mode of every layer."""
    modes = dict(DEFAULTS)
    try:
        with open(CONFIG_FILE, encoding="utf-8") as handle:
            for name, mode in json.load(handle).items():
                if name in modes and str(mode).lower() in _MODES:
                    modes[name] = _MODES[str(mode).lower()]
    except (OSError, ValueError, AttributeError):
        pass
    if text is None:
        text = os.environ.get("SCREENING_LAYERS", "")
    for item in text.replace(";", ",").split(","):
        item = item.strip().lower()
        if not item:
            continue
        name, _, mode = item.partition("=")
        if name == "none":
            modes = dict((n, "off") for n in modes)
        elif name in modes and _MODES.get(mode or "on"):
            modes[name] = _MODES[mode or "on"]
    return modes


class Case(object):
    """One person against one hit, as a layer sees it."""

    def __init__(self, store, alert, row, customer, hit, outcome, states, notes):
        self.store = store          # the loaded data folder (store.rules holds the name rules)
        self.rules = store.rules
        self.alert = alert          # the alert row
        self.row = row              # the raw hit row
        self.customer = customer    # decide.Customer
        self.hit = hit              # decide.Hit
        self.outcome = outcome      # decide.Outcome from the rules
        self.states = states        # decide.states(): name, dob, location, shared
        self.notes = notes          # annotations made so far by earlier layers, by layer name


def load(store, modes, problems=None):
    """Build the annotating layers that are switched on: [(name, mode, layer)].
    A layer that cannot be built is left out and the problem is noted."""
    active = []
    for name in ORDER:
        mode = modes.get(name, "off")
        if mode == "off":
            continue
        try:
            module = importlib.import_module("." + name, __name__)
            active.append((name, mode, module.build(store, mode)))
        except Exception as error:
            if problems is not None:
                problems.append("%s layer is off: %s: %s" % (name, type(error).__name__, error))
    return active


def load_reader(store, modes, problems=None):
    """The note reader to use: the rules' own, or the model-backed one when switched on."""
    mode = modes.get("reader", "off")
    if mode == "off":
        return None
    try:
        module = importlib.import_module(".reader", __name__)
        return module.build(store, mode)
    except Exception as error:
        if problems is not None:
            problems.append("reader layer is off: %s: %s" % (type(error).__name__, error))
        return None
