"""Subject TAGS code mapping for ACP-127 messages.

Source: docs/faqs.txt, Appendix I (permanent Subject TAGS) and Appendix II
(temporary Subject TAGS), National Archives RG 59 CFPF FAQ. The FAQ documents
only Subject TAGS, not Geographic or Organization TAGS -- codes outside this
mapping are classified as "unknown" rather than guessed at.

Appendix I additionally states that every code in the E/M/P/S/T fields is
permanent (full lists are only in the TAGS handbooks, not reproduced in the
FAQ) -- see _WILDCARD_PERMANENT_PREFIXES.
"""

PERMANENT_SUBJECT_TAGS = {
    "ACLM": ("Administration", "Claims Against the U.S. Government"),
    "ACMM": ("Administration", "Committees"),
    "AEMR": ("Administration", "Emergency Planning and Evacuation"),
    "AGAO": ("Administration", "General Accounting Office"),
    "AINF": ("Administration", "Information Management Services"),
    "AINR": ("Administration", "INR Program Administration"),
    "ALTR": ("Administration", "Newsletter"),
    "AMGT": ("Administration", "Management Operations"),
    "AODE": ("Administration", "Employees Abroad"),
    "AORG": ("Administration", "International Organization Administration"),
    "ASEC": ("Administration", "Security"),
    "ASIG": ("Administration", "Inspector General Activities"),
    "BAGB": ("Business Services", "Agribusiness"),
    "BBAK": ("Business Services", "Background on Firms, Products, and Individuals"),
    "BBCP": ("Business Services", "Business Consultation Program"),
    "BBSR": ("Business Services", "Business Services Reporting"),
    "BDIS": ("Business Services", "Trade Complaints and Disputes"),
    "BENC": ("Business Services", "Engineering and Construction Services"),
    "BEXP": ("Business Services", "Trade Expansion and Promotion"),
    "BFOL": ("Business Services", "Follow-up Request"),
    "BGEN": ("Business Services", "Business Services - General"),
    "BPRO": ("Business Services", "Business Proposals and Inquiries"),
    "BTIO": ("Business Services", "Trade and Investment Opportunities"),
    "BTRA": ("Business Services", "Travel by U.S. and Foreign Businessmen"),
    "CARR": ("Consular Affairs", "Americans Arrested Abroad"),
    "CASC": ("Consular Affairs", "Assistance to Citizens"),
    "CDES": ("Consular Affairs", "Deaths and Estates"),
    "CFED": ("Consular Affairs", "Federal Agency Services"),
    "CGEN": ("Consular Affairs", "Consular Affairs - General"),
    "CPRS": ("Consular Affairs", "Property Protection Services"),
    "OCLR": ("Operations", "Military Vessel and Flight Clearances and Visits"),
    "OCON": ("Operations", "Conferences and Meetings"),
    "OGEN": ("Operations", "Operations - General"),
    "OREP": ("Operations", "U.S. Congressional Travel"),
    "OVIP": ("Operations", "Visits and Travel of Prominent Individuals and Leaders"),
}

TEMPORARY_SUBJECT_TAGS = {
    "AART": ("Administration", "Art-in-Embassies Program"),
    "AAUD": ("Administration", "Audits"),
    "ABLD": ("Administration", "Buildings"),
    "ABUD": ("Administration", "Budget Services and Financial Systems"),
    "ACOM": ("Administration", "Departmental Communications"),
    "ACMS": ("Administration", "COMSEC Material"),
    "ACOU": ("Administration", "Courier Operations"),
    "ADTO": ("Administration", "Domestic Telecommunications Operations"),
    "AFAC": ("Administration", "Commo & Records Unit/Combined Commo Centers (CRU/CCC)"),
    "AFIN": ("Administration", "Financial Services"),
    "AFOP": ("Administration", "Foreign Service Post COM Center Operations & Administration"),
    "AFSI": ("Administration", "Foreign Service Institute"),
    "AFSP": ("Administration", "Post Administration"),
    "ALIB": ("Administration", "Library Services"),
    "ALOW": ("Administration", "Allowances"),
    "AMED": ("Administration", "Medical Services"),
    "AMTC": ("Administration", "Telecommunications Equipment Maintenance"),
    "ANET": ("Administration", "Communications, circuits, and Networks"),
    "APER": ("Administration", "Personnel"),
    "APOU": ("Administration", "Mail and Pouch"),
    "APUB": ("Administration", "Publishing, Printing, Distribution, and Library Services"),
    "AREC": ("Administration", "Commissary and Recreation"),
    "AREG": ("Administration", "Regulations and Directives"),
    "ASAF": ("Administration", "Safety"),
    "ASCH": ("Administration", "Overseas Schools"),
    "ASUP": ("Administration", "Supplies and Equipment"),
    "ATRN": ("Administration", "Transportation"),
    "AVCE": ("Administration", "Foreign Service Post Voice Communications Facility"),
    "AWRD": ("Administration", "Awards"),
    "BLIB": ("Business Services", "Commercial Libraries"),
    "BPUB": ("Business Services", "Business-Commercial Publications and Libraries"),
    "CPAS": ("Consular Affairs", "Passports and Citizenship"),
    "CVIS": ("Consular Affairs", "Visas"),
    "OEXC": ("Operations", "Educational and Cultural Exchange Operations"),
    "OSCI": ("Operations", "Science Grants"),
    "OTRA": ("Operations", "Travel and Visits"),
}

# Appendix I: "All Subject TAGS in the [E/M/P/S/T] field are permanent." The FAQ
# does not enumerate these codes (see the on-line TAGS handbooks for details).
_WILDCARD_PERMANENT_PREFIXES = frozenset({"E", "M", "P", "S", "T"})

_WILDCARD_FIELD_NAMES = {
    "E": "Economic Affairs",
    "M": "Military and Defense Affairs",
    "P": "Political Affairs",
    "S": "Social Affairs",
    "T": "Technology and Science",
}


def classify_subject_tag(code: str) -> tuple[str, str | None]:
    """Classify a 4-letter Subject TAGS code per docs/faqs.txt Appendix I/II.

    Returns (status, title):
      status is one of "permanent", "temporary", "permanent-wildcard", "unknown".
      title is the Appendix title text, or None if not explicitly enumerated
      (wildcard-covered and unknown codes have no title in the FAQ).
    """
    code = code.strip().upper()

    if code in PERMANENT_SUBJECT_TAGS:
        _, title = PERMANENT_SUBJECT_TAGS[code]
        return "permanent", title

    if code in TEMPORARY_SUBJECT_TAGS:
        _, title = TEMPORARY_SUBJECT_TAGS[code]
        return "temporary", title

    if len(code) == 4 and code[0] in _WILDCARD_PERMANENT_PREFIXES:
        return "permanent-wildcard", None

    return "unknown", None
