"""
Job-posting source layer — one adapter per applicant tracking system.

Unlike FMCSA, this evidence family has no central registry. A private mid-size company
publishes its openings on whatever ATS it happens to license, so the harness needs an
adapter per system and an honest account of the companies it cannot reach.

Adapters implemented:
    workday    JSON API (wday/cxs). Clean, paginated, richest source.
    icims      HTML portal. Job links carry the id; titles need unwrapping.
    paylocity  Company careers page links to job detail pages; each detail page
               embeds a "jobTitle" JSON field.

Every adapter returns a list of Posting objects and nothing else — no classification,
no project semantics. All responses go through the shared DatedCache.
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, field

import requests

from core.cache import DatedCache, slug

USER_AGENT = ("Mkt_Research_Harness/1.0 (independent study project; "
              "contact matthewlebrecht@gmail.com)")

# Bound on how many postings one company can contribute. Kenco alone lists 561; pulling
# every page of every ATS would be slow and needlessly heavy on the origin. Whenever this
# bites, the adapter records it so the run reports truncated coverage instead of implying
# it saw everything.
MAX_POSTINGS_PER_COMPANY = 600
WORKDAY_PAGE_SIZE = 20


@dataclass
class Posting:
    title: str
    location: str = ""
    posted: str = ""
    url: str = ""
    job_id: str = ""
    description: str = ""

    @property
    def text(self) -> str:
        """What the classifier reads."""
        return f"{self.title}\n{self.description}".strip()


def dedupe(postings: list) -> tuple[list, int]:
    """Collapse identical title+location pairs.

    The same requisition is often listed more than once on a portal. Counting both would
    inflate a signal's strength, and signal_strength drives how much weight a finding
    carries later. Distinct locations are kept apart — two automation techs in two cities
    is genuinely two sites investing, which is exactly the pattern worth seeing.
    """
    seen, out, dropped = set(), [], 0
    for p in postings:
        key = (p.title.strip().lower(), p.location.strip().lower())
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        out.append(p)
    return out, dropped


@dataclass
class FetchResult:
    postings: list[Posting] = field(default_factory=list)
    truncated: bool = False
    reported_total: int | None = None
    notes: list[str] = field(default_factory=list)


class JobSourceClient:
    def __init__(self, cache: DatedCache):
        self.cache = cache
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    # ---------- transport ----------

    def _get(self, url: str, key: str, suffix: str = ".html") -> str:
        body, _ = self.cache.get(key, suffix,
                                 lambda: self._raise_for(self.session.get(url, timeout=45)).text)
        return body

    def _post_json(self, url: str, payload: dict, key: str) -> dict:
        body, _ = self.cache.get(
            key, ".json",
            lambda: self._raise_for(self.session.post(
                url, json=payload, timeout=45,
                headers={"Accept": "application/json", "Content-Type": "application/json"})).text)
        return json.loads(body)

    @staticmethod
    def _raise_for(response):
        response.raise_for_status()
        return response

    # ---------- dispatch ----------

    def fetch(self, company_id: str, config: dict) -> FetchResult:
        ats = (config.get("ats") or "").lower()
        adapter = {
            "workday": self._workday,
            "icims": self._icims,
            "paylocity": self._paylocity,
            "greenhouse": self._greenhouse,
            "lever": self._lever,
            "adp": self._adp,          # session 10 item 7
            "inline": self._inline,    # session 10 item 7
        }.get(ats)
        if adapter is None:
            raise ValueError(f"no adapter for ats={ats!r} (company {company_id})")
        return adapter(company_id, config)

    # ---------- adapters ----------

    def _workday(self, company_id: str, config: dict) -> FetchResult:
        base = config["cxs_url"].rstrip("/")
        out, offset, total = [], 0, None
        result = FetchResult()
        while offset < MAX_POSTINGS_PER_COMPANY:
            payload = {"appliedFacets": {}, "limit": WORKDAY_PAGE_SIZE,
                       "offset": offset, "searchText": ""}
            data = self._post_json(f"{base}/jobs", payload,
                                   f"workday_{slug(company_id)}_{offset}")
            total = data.get("total", total)
            page = data.get("jobPostings", [])
            if not page:
                break
            for j in page:
                path = j.get("externalPath") or ""
                out.append(Posting(
                    title=(j.get("title") or "").strip(),
                    location=(j.get("locationsText") or "").strip(),
                    posted=(j.get("postedOn") or "").strip(),
                    job_id=(j.get("bulletFields") or [""])[0],
                    url=config["careers_url"] if not path else
                        re.sub(r"/wday/cxs/[^/]+/", "/", base).rsplit("/", 1)[0] + path,
                ))
            offset += WORKDAY_PAGE_SIZE
        # Truncation means the cap stopped us, NOT that dedupe shrank the list. Conflating
        # the two would stamp "counts are lower bounds" on a complete read.
        result.truncated = bool(total and len(out) < total)
        deduped, dropped = dedupe(out[:MAX_POSTINGS_PER_COMPANY])
        result.postings = deduped
        if dropped:
            result.notes.append(
                f"{dropped} duplicate title+location listings collapsed "
                f"({len(out)} raw -> {len(deduped)} distinct)")
        result.reported_total = total
        if result.truncated:
            result.notes.append(
                f"Workday reports {total} open postings; this run read {len(out)} "
                f"(MAX_POSTINGS_PER_COMPANY={MAX_POSTINGS_PER_COMPANY}). Signal counts "
                f"are lower bounds.")
        return result

    def _icims(self, company_id: str, config: dict) -> FetchResult:
        host = config["host"]
        result = FetchResult()
        seen: dict[str, Posting] = {}
        for page in range(0, 6):
            url = f"https://{host}/jobs/search?ss=1&in_iframe=1&pr={page}"
            body = self._get(url, f"icims_{slug(company_id)}_p{page}")
            found = re.findall(
                r'<a[^>]+href="(https://[^"]*?/jobs/(\d+)/[^"]+)"[^>]*>(.*?)</a>', body, re.S)
            new = 0
            for link, jid, label in found:
                if jid in seen:
                    continue
                title = html.unescape(re.sub(r"<[^>]+>", " ", label))
                # iCIMS wraps the anchor text with the results grid's column label, and
                # the label is tenant-configurable: "Title", but also "Requisition Title"
                # (Gilbane) and "External Job Title" (Suffolk). v1.0 stripped only the
                # bare form, so Suffolk's two AI roles came through as "External Job Title
                # AI Systems Engineer". It never caused a false positive -- the prefix
                # carries no signal terms -- but it lands verbatim in observation_text and
                # evidence_excerpt, which is what a human reads at the audit.
                title = re.sub(r"^\s*(external\s+job|requisition|job|position)?\s*title\b\s*",
                               "", title, flags=re.I).strip()
                title = re.sub(r"\s+", " ", title)
                if not title:
                    continue
                seen[jid] = Posting(title=title, url=link.split("?")[0], job_id=jid)
                new += 1
            if new == 0:
                break
        else:
            # Session 10 item 6 (J32): the loop ran to its bound with every page still
            # yielding new postings, so the listing is unread past page 6. That is a
            # truncation and is reported as one, like the Workday cap.
            result.truncated = True
            result.notes.append("iCIMS listing read to the 6-page bound with postings still "
                                "arriving; postings past it are unread, counts are lower bounds")
        deduped, dropped = dedupe(list(seen.values())[:MAX_POSTINGS_PER_COMPANY])
        result.postings = deduped
        if dropped:
            result.notes.append(f"{dropped} duplicate title+location listings collapsed")
        result.notes.append(
            "iCIMS portal only; any postings this employer runs on other systems "
            "(JazzHR, Paycor) are not covered by this adapter.")
        return result

    def _paylocity(self, company_id: str, config: dict) -> FetchResult:
        careers = config["careers_url"]
        body = self._get(careers, f"paylocity_{slug(company_id)}_careers")
        ids = []
        for m in re.finditer(r"recruiting\.paylocity\.com/Recruiting/Jobs/Details/(\d+)", body):
            if m.group(1) not in ids:
                ids.append(m.group(1))
        result = FetchResult()
        for jid in ids[:MAX_POSTINGS_PER_COMPANY]:
            detail_url = f"https://recruiting.paylocity.com/Recruiting/Jobs/Details/{jid}"
            page = self._get(detail_url, f"paylocity_{slug(company_id)}_{jid}")
            m = re.search(r'"jobTitle"\s*:\s*"([^"]+)"', page)
            title = html.unescape(m.group(1)).strip() if m else ""
            if not title:
                t = re.search(r"<title>(.*?)</title>", page, re.S)
                title = html.unescape(re.sub(r"<[^>]+>", "", t.group(1))).strip() if t else ""
                title = re.sub(r"^[^-]*-\s*", "", title)  # strip "Company - " prefix
            if not title or title.lower().startswith("job not found"):
                # Expired/pulled requisition still linked from the careers page.
                result.notes.append(f"Paylocity job {jid} is no longer live (Job Not Found)")
                continue
            result.postings.append(Posting(title=title, url=detail_url, job_id=jid))
        return result

    # ---- added 2026-09-01 for the full-universe run ----
    #
    # Greenhouse and Lever both publish a documented, keyless, unpaginated JSON board API.
    # They are added because DISCOVERY FOUND THEM, not on a guess about what is popular:
    # a detected ATS with no adapter is a named coverage gap, and these two were the two
    # most common named gaps across the Anvil-100 probe.
    #
    # `careers_url` stays the company's own page in both. The board API is how the
    # postings are read; it is not what the observation cites, because source_grade A on
    # this harness means the claim is attributable to the company's own careers page.

    def _adp(self, company_id: str, config: dict) -> FetchResult:
        """ADP Workforce Now career center: a public JSON requisition list (session 10).

        Probed 2026-09-03: robots.txt on workforcenow.adp.com permits this crawler and the
        endpoint answers without a session. Pages of 50; `meta.totalNumber` is the total,
        so truncation is measured rather than guessed.
        """
        cid = config.get("cid") or ""
        ccid = config.get("ccid") or "19000101_000001"
        if not cid:
            raise ValueError(f"adp adapter needs the client id (cid) for {company_id}")
        result = FetchResult()
        out, skip, total = [], 0, None
        while skip < MAX_POSTINGS_PER_COMPANY:
            url = ("https://workforcenow.adp.com/mascsr/default/careercenter/public/events/"
                   f"staffing/v1/job-requisitions?cid={cid}&ccId={ccid}&lang=en_US"
                   f"&$top=50&$skip={skip}")
            body = self._get(url, f"adp_{slug(company_id)}_{skip}", suffix=".json")
            data = json.loads(body) if body.strip() else {}
            reqs = data.get("jobRequisitions") or []
            total = (data.get("meta") or {}).get("totalNumber", total)
            if not reqs:
                break
            for q in reqs:
                locs = q.get("requisitionLocations") or []
                loc = ((locs[0].get("nameCode") or {}).get("shortName") or "") if locs else ""
                jid = str(q.get("itemID") or "")
                out.append(Posting(
                    title=(q.get("requisitionTitle") or "").strip(),
                    location=str(loc).strip(),
                    posted=str(q.get("postDate") or "").strip(),
                    job_id=jid,
                    url=("https://workforcenow.adp.com/mascsr/default/mdf/recruitment/"
                         f"recruitment.html?cid={cid}&ccId={ccid}&jobId={jid}&lang=en_US"),
                ))
            if len(reqs) < 50:
                break
            skip += 50
        result.truncated = bool(total and len(out) < total)
        deduped, dropped = dedupe(out[:MAX_POSTINGS_PER_COMPANY])
        result.postings = deduped
        result.reported_total = total
        if dropped:
            result.notes.append(f"{dropped} duplicate title+location listings collapsed")
        if result.truncated:
            result.notes.append(f"ADP reports {total} requisitions; this run read {len(out)}. "
                                f"Signal counts are lower bounds.")
        return result

    def _inline(self, company_id: str, config: dict) -> FetchResult:
        """A careers page that lists its postings inline in server HTML (session 10)."""
        from harnesses.h_jobpost_01.discovery import INLINE_MIN, inline_postings
        careers = config["careers_url"]
        body = self._get(careers, f"inline_{slug(company_id)}_careers")
        listed = inline_postings(body, careers)
        result = FetchResult()
        if len(listed) < INLINE_MIN:
            result.notes.append(f"inline parser found {len(listed)} job-like anchor(s), "
                                f"below the {INLINE_MIN} floor; the page is not a list")
            return result
        result.postings = [Posting(title=t, url=u, job_id=u.rsplit("/", 1)[-1][:40])
                           for u, t in listed[:MAX_POSTINGS_PER_COMPANY]]
        result.notes.append("read from an inline list on the company's own careers page; "
                            "titles only, no descriptions")
        return result

    def _greenhouse(self, company_id: str, config: dict) -> FetchResult:
        board = config.get("board") or ""
        result = FetchResult()
        if not board:
            raise ValueError(f"greenhouse adapter needs a board token ({company_id})")
        url = f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs"
        body = self._get(url, f"greenhouse_{slug(company_id)}", ".json")
        data = json.loads(body)
        jobs = data.get("jobs", [])
        for j in jobs[:MAX_POSTINGS_PER_COMPANY]:
            loc = (j.get("location") or {}).get("name", "") if isinstance(
                j.get("location"), dict) else ""
            result.postings.append(Posting(
                title=(j.get("title") or "").strip(),
                location=(loc or "").strip(),
                posted=(j.get("updated_at") or "")[:10],
                url=j.get("absolute_url") or config["careers_url"],
                job_id=str(j.get("id") or ""),
            ))
        result.reported_total = len(jobs)
        deduped, dropped = dedupe(result.postings)
        result.postings = deduped
        if dropped:
            result.notes.append(
                f"{dropped} duplicate title+location listings collapsed")
        result.truncated = len(jobs) > MAX_POSTINGS_PER_COMPANY
        return result

    def _lever(self, company_id: str, config: dict) -> FetchResult:
        board = config.get("board") or ""
        result = FetchResult()
        if not board:
            raise ValueError(f"lever adapter needs a board token ({company_id})")
        url = f"https://api.lever.co/v0/postings/{board}?mode=json"
        body = self._get(url, f"lever_{slug(company_id)}", ".json")
        data = json.loads(body)
        for j in data[:MAX_POSTINGS_PER_COMPANY]:
            cats = j.get("categories") or {}
            result.postings.append(Posting(
                title=(j.get("text") or "").strip(),
                location=(cats.get("location") or "").strip(),
                url=j.get("hostedUrl") or config["careers_url"],
                job_id=str(j.get("id") or ""),
            ))
        result.reported_total = len(data)
        deduped, dropped = dedupe(result.postings)
        result.postings = deduped
        if dropped:
            result.notes.append(
                f"{dropped} duplicate title+location listings collapsed")
        result.truncated = len(data) > MAX_POSTINGS_PER_COMPANY
        return result
