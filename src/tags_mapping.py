"""TAGS code mapping for ACP-127 messages.

Subject TAGS (PERMANENT_SUBJECT_TAGS, TEMPORARY_SUBJECT_TAGS) come from
docs/faqs.txt, Appendix I and Appendix II (National Archives RG 59 CFPF FAQ)
-- this is the authoritative, official source, and every code in these two
dicts plus the E/M/P/S/T wildcard rule is FAQ-documented.

ORGANIZATION_TAGS is a separate, non-FAQ mapping: independent research that
identified the meaning of common Organization TAGS codes (bodies like NATO,
OECD, OPEC, ...) by sampling real message subjects/bodies -- see
docs/tags_coverage.md for full methodology and evidence citations. Only codes
confirmed by that research (spelled out in the sampled text, or an
unambiguous standard institution) are included; ambiguous/uncertain guesses
were left out.
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

# Organization TAGS meanings identified via docs/tags_coverage.md research
# (NOT from docs/faqs.txt -- the FAQ does not define Organization TAGS at all).
ORGANIZATION_TAGS = {
    "NATO": "North Atlantic Treaty Organization",
    "UNGA": "UN General Assembly",
    "OECD": "Organisation for Economic Co-operation and Development",
    "IAEA": "International Atomic Energy Agency",
    "CSCE": "Conference on Security and Co-operation in Europe",
    "UNSC": "UN Security Council",
    "GATT": "General Agreement on Tariffs and Trade",
    "OPIC": "Overseas Private Investment Corporation",
    "CCMS": "NATO Committee on the Challenges of Modern Society",
    "ICAO": "International Civil Aviation Organization",
    "IBRD": "International Bank for Reconstruction and Development (World Bank)",
    "ICRC": "International Committee of the Red Cross",
    "OPEC": "Organization of the Petroleum Exporting Countries",
    "UNDP": "UN Development Programme",
    "IMCO": "Inter-Governmental Maritime Consultative Organization (predecessor of IMO)",
    "UNEP": "UN Environment Programme",
    "CIEC": "Conference on International Economic Cooperation (\"North-South Dialogue\")",
    "NASA": "National Aeronautics and Space Administration",
    "WARC": "World Administrative Radio Conference",
    "ICEM": "Intergovernmental Committee for European Migration",
    "UNEF": "UN Emergency Force",
    "WIPO": "World Intellectual Property Organization",
    "ICCS": "International Commission of Control and Supervision (Vietnam ceasefire body)",
    "IFAD": "International Fund for Agricultural Development",
    "FSLN": "Frente Sandinista de Liberación Nacional (Sandinista National Liberation Front, Nicaragua)",
    "FNLA": "Frente Nacional de Libertação de Angola",
    "AFDB": "African Development Bank",
    "USIA": "United States Information Agency",
    "NACB": "Non-Aligned Coordinating Bureau",
    "NACC": "Non-Aligned Coordinating Committee",
    "IATA": "International Air Transport Association",
    "AFDF": "African Development Fund",
    "NOAA": "National Oceanic and Atmospheric Administration",
    "UNTC": "UN Trusteeship Council",
    "ZANU": "Zimbabwe African National Union",
    "ZAPU": "Zimbabwe African People's Union",
    "CEMA": "Council for Mutual Economic Assistance (COMECON)",
    "AALC": "African-American Labor Center",
    "ICAF": "Industrial College of the Armed Forces",
    "ACDA": "US Arms Control and Disarmament Agency",
    "CCIR": "International Radio Consultative Committee",
    "ORIT": "Inter-American Regional Organization of Workers (AFL-CIO-affiliated)",
    "INCB": "International Narcotics Control Board",
    "WFTU": "World Federation of Trade Unions",
    "IRSG": "International Rubber Study Group",
    "USGS": "US Geological Survey",
    "FHWA": "Federal Highway Administration",
    "USAF": "US Air Force",
    "USIS": "US Information Service (overseas arm of USIA)",
    "USDA": "US Department of Agriculture",
    "UJNR": "US-Japan Cooperative Program in Natural Resources",
    "NIOC": "National Iranian Oil Company",
    "FCIA": "Foreign Credit Insurance Association",
    "CACM": "Central American Common Market",
    "KCIA": "Korean Central Intelligence Agency",
    "ICCO": "International Cocoa Organization",
    "CIME": "OECD Committee on International Investment and Multinational Enterprises",
    "BWIA": "British West Indian Airways",
    "ICES": "International Council for the Exploration of the Sea",
    "FNCB": "First National City Bank (Citibank's former name)",
    "ISVS": "International Secretariat for Volunteer Service",
    "IAJC": "Inter-American Juridical Committee",
    "FIAT": "Fabbrica Italiana Automobili Torino (Italian automaker)",
    "CSTP": "OECD Committee for Scientific and Technological Policy",
    "ABCC": "Atomic Bomb Casualty Commission (Tokyo, US-Japan joint body)",
    "CPSU": "Communist Party of the Soviet Union",
    "CISL": "Confederazione Italiana Sindacati Lavoratori (Italian trade union confederation)",
    "NTSB": "National Transportation Safety Board",
    "IFRB": "International Frequency Registration Board (ITU)",
    "ICAC": "International Cotton Advisory Committee",
    "FLEC": "Frente de Libertação do Enclave de Cabinda",
    "NMFS": "National Marine Fisheries Service",
    "CEAO": "Communauté Économique de l'Afrique de l'Ouest (West African Economic Community)",
    "CNAD": "NATO Conference of National Armaments Directors",
    "CEPE": "Corporación Estatal Petrolera Ecuatoriana (Ecuador state oil company)",
    "OCAM": "Organisation Commune Africaine et Malgache",
    "LPDR": "Lao People's Democratic Republic (official name post-1975)",
    "IGGI": "Inter-Governmental Group on Indonesia (aid consortium)",
    "IESC": "International Executive Service Corps",
    "FEOF": "Foreign Exchange Operations Fund (Laos monetary stabilization fund)",
    "QUAI": "Quai d'Orsay (metonym for the French Foreign Ministry)",
    "CGIL": "Confederazione Generale Italiana del Lavoro (Italian communist-aligned union federation)",
    "CNEA": "Comisión Nacional de Energía Atómica (Argentina's atomic energy commission)",
    "AIIC": "American International Insurance Company (in this dataset's usage — not to be confused with the interpreters' association of the same acronym)",
    "APRA": "Alianza Popular Revolucionaria Americana (Peruvian political party)",
    "FARC": "Fuerzas Armadas Revolucionarias de Colombia",
    "ALIA": "Alia — The Royal Jordanian Airline",
    "USTS": "United States Travel Service",
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


def lookup_organization_tag(code: str) -> str | None:
    """Look up a code in ORGANIZATION_TAGS (non-FAQ, research-derived).

    Returns the meaning string, or None if the code isn't in this mapping.
    """
    return ORGANIZATION_TAGS.get(code.strip().upper())
