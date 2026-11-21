"""Loading the data folder and indexing it by every key the bank's systems use.

The systems do not share one key, so each index answers one hop of a path:
account -> holders, login -> account, email -> record, customer -> KYC applicant,
applicant -> checks, email -> notes, name -> search results.
"""
import json
import os

from .names import NameRules

TABLES = ("alerts", "hits", "customers", "accounts", "onboarding", "kyc_checks", "notes", "search_results")


def read_jsonl(path):
    """Rows of a JSON Lines file. A missing file or a broken line is skipped, not fatal."""
    rows = []
    try:
        with open(path, encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                if isinstance(row, dict):
                    rows.append(row)
    except OSError:
        pass
    return rows


def find_folder(folder):
    """The folder that holds alerts.jsonl: the one given, or a dev/ folder inside it."""
    if os.path.isfile(os.path.join(folder, "alerts.jsonl")):
        return folder
    for sub in ("dev", "data", "unseen", "test"):
        inner = os.path.join(folder, sub)
        if os.path.isfile(os.path.join(inner, "alerts.jsonl")):
            return inner
    try:
        for name in sorted(os.listdir(folder)):
            inner = os.path.join(folder, name)
            if os.path.isfile(os.path.join(inner, "alerts.jsonl")):
                return inner
    except OSError:
        pass
    return folder


def text(value):
    """A field as a stripped string; null and missing are ''."""
    if value is None:
        return ""
    return str(value).strip()


def key(value):
    return text(value).lower()


def _group(rows, field, fold=False):
    index = {}
    for row in rows:
        k = key(row.get(field)) if fold else text(row.get(field))
        if k:
            index.setdefault(k, []).append(row)
    return index


class Store(object):
    def __init__(self, folder):
        self.folder = find_folder(folder)
        for table in TABLES:
            setattr(self, table, read_jsonl(os.path.join(self.folder, table + ".jsonl")))
        variants = os.path.join(self.folder, "name_variants.json")
        if not os.path.isfile(variants):
            variants = os.path.join(os.path.dirname(os.path.abspath(self.folder)), "name_variants.json")
        self.rules = NameRules.from_file(variants)

        self.customer = dict((text(c.get("record_id")), c) for c in self.customers if text(c.get("record_id")))
        self.customers_by_email = _group(self.customers, "email", fold=True)
        self.accounts_by_id = _group(self.accounts, "account_id")
        self.accounts_by_login = _group(self.accounts, "login_handle", fold=True)
        self.accounts_by_customer = _group(self.accounts, "customer_id")
        self.onboarding_by_customer = _group(self.onboarding, "customer_id")
        self.checks_by_applicant = _group(self.kyc_checks, "applicant_id")
        self.notes_by_email = _group(self.notes, "requester_email", fold=True)
        self.search_by_query = _group(self.search_results, "query", fold=True)
        self.hit = dict((text(h.get("hit_id")), h) for h in self.hits if text(h.get("hit_id")))
        self.alert = dict((text(a.get("alert_id")), a) for a in self.alerts if text(a.get("alert_id")))
        self.alert_of_hit = {}
        for alert in self.alerts:
            for hit_id in alert.get("hit_ids") or []:
                self.alert_of_hit.setdefault(text(hit_id), alert)

    def applicants(self, record_id):
        """KYC applicant IDs of a customer record, through its onboarding rows."""
        out = []
        for row in self.onboarding_by_customer.get(record_id, []):
            applicant = text(row.get("kyc_applicant_id"))
            if applicant and applicant not in out:
                out.append(applicant)
        return out

    def checks(self, record_id):
        """Every identity check of a customer record held by the KYC provider."""
        return [c for a in self.applicants(record_id) for c in self.checks_by_applicant.get(a, [])]

    def notes_of(self, record_id):
        """Support and onboarding notes filed under the record's email."""
        email = key(self.customer.get(record_id, {}).get("email"))
        return self.notes_by_email.get(email, []) if email else []
