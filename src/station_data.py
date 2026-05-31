"""Consolidated station name data for ACP-127 reference normalization.

Single source of truth for station name variants and OCR corrections.
Derived from the old STATION_VARIANTS + _VARIANT_TO_TARGET dicts.
"""

import re

STATIONS = {
    "ABCDE": [
        "ABCDE",
    ],
    "ABIDJA": [
        "ABIDAJN",
        "ABIDJA",
    ],
    "ABIDJAN": [
        "ABIDJAN",
        "ABIDJDAN",
    ],
    "ABUDHABI": [
        "ABU DHABI",
        "ABUDHABI",
        "ABUDH",
        "BUDH",
    ],
    "ABUJA": [
        "ABUJA",
    ],
    "ACAPUL": [
        "ACAPUL",
    ],
    "ACCRA": [
        "ACCRA",
    ],
    "ADANA": [
        "ADANA",
    ],
    "ADDIS": [
        "ADDIS",
    ],
    "ADDISABABA": [
        "ADDIS ABABA",
        "ADDISABABA",
    ],
    "AIPEI": [
        "AIPEI",
    ],
    "AITTA": [
        "AITTA",
    ],
    "AITTAIPEI": [
        "AITTAIPEI",
    ],
    "AITWA": [
        "AITWA",
    ],
    "ALEXAN": [
        "ALEXAN",
    ],
    "ALEXANDRIA": [
        "ALEXANDRIA",
    ],
    "ALGIER": [
        "ALGIER",
    ],
    "ALGIERS": [
        "ALGIERS",
    ],
    "ALMATY": [
        "ALMATY",
    ],
    "AMEMBASSYHANOI": [
        "AMEMBASSYHANOI",
    ],
    "AMMAN": [
        "AMMAN",
    ],
    "AMSTER": [
        "AMSTER",
    ],
    "AMSTERDAM": [
        "AMSTERDAM",
    ],
    "ANKARA": [
        "ANKARA",
    ],
    "ANTANA": [
        "ANTANA",
    ],
    "ANTANANARIVO": [
        "ANTANANARIVO",
        "TANANARIVE",
    ],
    "ANTWER": [
        "ANTWER",
        "ANTWERP",
    ],
    "APIA": [
        "APIA",
    ],
    "AQABA": [
        "AQABA",
    ],
    "ARSAW": [
        "ARSAW",
    ],
    "ASHGABAT": [
        "ASHGABAT",
    ],
    "ASMARA": [
        "ASMARA",
    ],
    "ASTANA": [
        "ASTANA",
    ],
    "ASUNCI": [
        "ASUNCI",
    ],
    "ASUNCION": [
        "ASUNCION",
    ],
    "ASWAN": [
        "ASWAN",
    ],
    "ATHENS": [
        "ATHENS",
        "THENS",
    ],
    "ATLANT": [
        "ATLANT",
        "TLANT",
    ],
    "ATO": [
        "ATO",
    ],
    "AUCKLA": [
        "AUCKLA",
    ],
    "AUCKLAND": [
        "AUCKLAND",
    ],
    "BAGHDA": [
        "BAGHDA",
    ],
    "BAGHDAD": [
        "BAGHADAD",
        "BAGHDAD",
    ],
    "BAKU": [
        "BAKU",
    ],
    "BALI": [
        "BALI",
    ],
    "BAMAKO": [
        "BAMAKO",
    ],
    "BANDARSERIBEGAWAN": [
        "BANDAR SERI BEGAWAN",
        "BANDARSERIBEGAWAN",
    ],
    "BANGKOK": [
        "BANGKOK",
        "BANGKO",
        "ANGKOK",
        "ANGKO",
    ],
    "BANGUI": [
        "BANGUI",
    ],
    "BANJUL": [
        "BANJUL",
    ],
    "BARCEL": [
        "BARCEL",
    ],
    "BARCELONA": [
        "BARCELONA",
    ],
    "BARRAN": [
        "BARRAN",
    ],
    "BARRANQUILLA": [
        "BARRANQUILLA",
    ],
    "BASRAH": [
        "BASRAH",
    ],
    "BATHUR": [
        "BATHUR",
    ],
    "BEIJIN": [
        "BEIJIN",
    ],
    "BEIJING": [
        "BEIJING",
    ],
    "BEIRUT": [
        "BEIRUT",
        "BEIRUTQ",
    ],
    "BELEM": [
        "BELEM",
    ],
    "BELFAS": [
        "BELFAS",
    ],
    "BELFAST": [
        "BELFAST",
    ],
    "BELGRA": [
        "BELGRA",
    ],
    "BELGRADE": [
        "BELGRADE",
    ],
    "BELIZE": [
        "BELIZE",
    ],
    "BELMOPAN": [
        "BELMOPAN",
    ],
    "BERLIN": [
        "BERLIN",
        "ERLIN",
    ],
    "BERN": [
        "BERN",
    ],
    "BIENH": [
        "BIENH",
    ],
    "BILBAO": [
        "BILBAO",
    ],
    "BISHKEK": [
        "BISHKEK",
    ],
    "BISSAU": [
        "BISSAU",
    ],
    "BLANTY": [
        "BLANTY",
    ],
    "BLANTYRE": [
        "BLANTYRE",
    ],
    "BOGOTA": [
        "BOGOT",
        "BOGOTA",
    ],
    "BOHEMI": [
        "BOHEMI",
    ],
    "BOMBAY": [
        "BOMBAY",
    ],
    "BONN": [
        "BONN",
    ],
    "BORDEA": [
        "BORDEA",
    ],
    "BORDEAUX": [
        "BORDEAUX",
    ],
    "BRASIL": [
        "BRASIL",
    ],
    "BRASILIA": [
        "BRASIILIA",
        "BRASILIA",
    ],
    "BRATISLAVA": [
        "BRATISLAVA",
    ],
    "BRAZZA": [
        "BRAZZA",
    ],
    "BRAZZAVILLE": [
        "BRAZZAVILLE",
    ],
    "BREMEN": [
        "BREMEN",
    ],
    "BRIDGE": [
        "BRIDGE",
    ],
    "BRIDGETOWN": [
        "BRIDGETOWN",
    ],
    "BRISBA": [
        "BRISBA",
    ],
    "BRISBANE": [
        "BRISBANE",
    ],
    "BRUSSE": [
        "BRUSSE",
    ],
    "BRUSSELS": [
        "BRUSSELS",
    ],
    "BUCHAR": [
        "BUCHA",
        "BUCHAR",
    ],
    "BUCHAREST": [
        "BUCHAREST",
    ],
    "BUDAPE": [
        "BUDAPE",
        "BUDAPST",
    ],
    "BUDAPEST": [
        "BUDAPEST",
    ],
    "BUENOS": [
        "BUENOS",
    ],
    "BUENOSAIRES": [
        "BUENOS AIRES",
        "BUENOSAIRES",
    ],
    "BUJUMB": [
        "BUJUMB",
    ],
    "BUJUMBURA": [
        "BUJUMBURA",
    ],
    "BUKAVU": [
        "BUKAVU",
    ],
    "CAIRO": [
        "CAIRO",
    ],
    "CALCUT": [
        "CALCUT",
    ],
    "CALCUTTA": [
        "CALCUTT",
        "CALCUTTA",
    ],
    "CALGAR": [
        "CALGAR",
    ],
    "CALGARY": [
        "CALGARY",
    ],
    "CALI": [
        "CALI",
    ],
    "CANBER": [
        "CANBER",
    ],
    "CANBERRA": [
        "CANBERRA",
    ],
    "CANTH": [
        "CANTH",
    ],
    "CAPET": [
        "CAPET",
    ],
    "CAPETOWN": [
        "CAPE TOWN",
        "CAPETOWN",
    ],
    "CARACA": [
        "CARACA",
    ],
    "CARACAS": [
        "CARACACS",
        "CARACAS",
    ],
    "CASABL": [
        "CASABL",
    ],
    "CASABLANCA": [
        "CASABLANCA",
    ],
    "CDGENEVA": [
        "CDGENEVA",
    ],
    "CEBU": [
        "CEBU",
    ],
    "CHENGDU": [
        "CHENGDU",
    ],
    "CHENNAI": [
        "CHENNAI",
    ],
    "CHIANG": [
        "CHIANG",
    ],
    "CHIANGMAI": [
        "CHIANGMAI",
    ],
    "CHISINAU": [
        "CHISINAU",
    ],
    "CIUDAD": [
        "CIUDAD",
    ],
    "CIUDADJUAREZ": [
        "CIUDAD JUAREZ",
        "CIUDADJUAREZ",
    ],
    "COCOMDOC": [
        "COCOMDOC",
    ],
    "COLOMB": [
        "COLOMB",
    ],
    "COLOMBO": [
        "COLOMBO",
    ],
    "CONAKR": [
        "CONAKR",
    ],
    "CONAKRY": [
        "CONAKRY",
    ],
    "COPENH": [
        "COPENH",
    ],
    "COPENHAGEN": [
        "COPENHAGEN",
    ],
    "COTONO": [
        "COTONO",
    ],
    "COTONOU": [
        "COTONOU",
    ],
    "CRUS": [
        "CRUS",
    ],
    "CURACA": [
        "CURACA",
    ],
    "CURACAO": [
        "CURACAO",
    ],
    "DACCA": [
        "DACC",
        "DACCA",
    ],
    "DAKAR": [
        "DAKAR",
    ],
    "DAMASC": [
        "DAMASC",
    ],
    "DAMASCUS": [
        "DAMASCUS",
    ],
    "DANANG": [
        "DANANG",
    ],
    "DARES": [
        "DARES",
    ],
    "DARESSALAAM": [
        "DAR ES SALAAM",
        "DARESSALAAM",
    ],
    "DEA": [
        "DEA",
    ],
    "DEAUVI": [
        "DEAUVI",
    ],
    "DHAHRA": [
        "DHAHRA",
    ],
    "DHAHRAN": [
        "DHAHRAN",
    ],
    "DHAKA": [
        "DHAKA",
    ],
    "DILI": [
        "DILI",
    ],
    "DJIBOUTI": [
        "DJIBOUTI",
        "DJIBOU",
    ],
    "DOHA": [
        "DOHA",
    ],
    "DORADO": [
        "DORADO",
    ],
    "DOUALA": [
        "DOUALA",
    ],
    "DUBAI": [
        "DUBAI",
    ],
    "DUBLIN": [
        "DUBLIIN",
        "DUBLIN",
        "DUBLN",
    ],
    "DURBAN": [
        "DURBAN",
    ],
    "DUSHANBE": [
        "DUSHANBE",
    ],
    "DUSSEL": [
        "DUSSEL",
    ],
    "DUSSELDORF": [
        "DUSSELDORF",
    ],
    "ECBRU": [
        "ECBRU",
    ],
    "ECBRUSSELS": [
        "ECBRUSSELS",
    ],
    "EDINBU": [
        "EDINBU",
    ],
    "EDINBURGH": [
        "EDINBURGH",
    ],
    "EFTOANKARA": [
        "EFTOANKARA",
    ],
    "EFTOASMARA": [
        "EFTOASMARA",
    ],
    "EFTOATHENS": [
        "EFTOATHENS",
    ],
    "EFTOBAGHDAD": [
        "EFTOBAGHDAD",
    ],
    "EFTOBAKU": [
        "EFTOBAKU",
    ],
    "EFTOBUENOSAIRES": [
        "EFTOBUENOSAIRES",
    ],
    "EFTOCARACAS": [
        "EFTOCARACAS",
    ],
    "EFTOKABUL": [
        "EFTOKABUL",
    ],
    "EFTOLONDON": [
        "EFTOLONDON",
    ],
    "EFTOMONTEVIDEO": [
        "EFTOMONTEVIDEO",
    ],
    "EFTOPORTMORESBY": [
        "EFTOPORTMORESBY",
    ],
    "EFTORABAT": [
        "EFTORABAT",
    ],
    "EFTOSANAA": [
        "EFTOSANAA",
    ],
    "EFTOSKOPJE": [
        "EFTOSKOPJE",
    ],
    "EFTOUSUNNEWYORK": [
        "EFTOUSUNNEWYORK",
    ],
    "EFTOYEREVAN": [
        "EFTOYEREVAN",
    ],
    "FESTTWO": [
        "FESTTWO",
    ],
    "FLOREN": [
        "FLOREN",
    ],
    "FLORENCE": [
        "FLORENCE",
    ],
    "FORTL": [
        "FORTL",
    ],
    "FRANCE": [
        "FRANCE",
    ],
    "FRANKF": [
        "FRANKF",
    ],
    "FRANKFURT": [
        "FRANKFURT",
    ],
    "FREETO": [
        "FREETO",
    ],
    "FREETOWN": [
        "FREETOWN",
    ],
    "FUKUOK": [
        "FUKUOK",
    ],
    "FUKUOKA": [
        "FUKUOKA",
    ],
    "GABORO": [
        "GABORO",
    ],
    "GABORONE": [
        "GABORONE",
    ],
    "GENEVA": [
        "GENEA",
        "GENEFA",
        "GENEVA",
        "ENEVA",
    ],
    "GENOA": [
        "GENOA",
    ],
    "GEORGE": [
        "GEORGE",
    ],
    "GEORGETOWN": [
        "GEORGETOWN",
    ],
    "GOTEBO": [
        "GOTEBO",
    ],
    "GOTEBORG": [
        "GOTEBORG",
    ],
    "GRENAD": [
        "GRENAD",
    ],
    "GRENADA": [
        "GRENADA",
    ],
    "GUADAL": [
        "GUADAL",
    ],
    "GUADALAJARA": [
        "GUADALAJARA",
    ],
    "GUANGZHOU": [
        "GUANGZHOU",
    ],
    "GUATEM": [
        "GUATEM",
    ],
    "GUATEMALA": [
        "GUATEMALA",
    ],
    "GUAYAQ": [
        "GUAYAQ",
    ],
    "GUAYAQUIL": [
        "GUAYAQUIL",
    ],
    "HALIFA": [
        "HALIFA",
    ],
    "HALIFAX": [
        "HALIFAX",
    ],
    "HAMBUR": [
        "HAMBUR",
    ],
    "HAMBURG": [
        "HAMBURG",
    ],
    "HAMILT": [
        "HAMILT",
    ],
    "HAMILTON": [
        "HAMILTON",
    ],
    "HANOI": [
        "HANOI",
    ],
    "HARARE": [
        "HARARE",
    ],
    "HAVANA": [
        "HAVANA",
    ],
    "HELSIN": [
        "HELSIN",
    ],
    "HELSINKI": [
        "HELSINKI",
    ],
    "HERMOS": [
        "HERMOS",
    ],
    "HERMOSILLO": [
        "HERMOSILLO",
    ],
    "HILLAH": [
        "HILLAH",
    ],
    "HOCHIMINHCITY": [
        "HO CHI MINH CITY",
        "HOCHIMINHCITY",
    ],
    "HONGK": [
        "HONGK",
    ],
    "HONGKONG": [
        "HONG KONG",
        "HONGKONG",
    ],
    "HOUSTO": [
        "HOUSTO",
    ],
    "HYDERABAD": [
        "HYDERABAD",
    ],
    "IAEAV": [
        "IAEA",
        "IAEAV",
    ],
    "IAEAVIENNA": [
        "IAEAVIENNA",
    ],
    "IBADAN": [
        "IBADAN",
    ],
    "IENNA": [
        "IENNA",
    ],
    "IRANRPODUBAI": [
        "IRANRPODUBAI",
    ],
    "ISFAHA": [
        "ISFAHA",
        "ISFAHAN",
    ],
    "ISLAMA": [
        "ISLAMA",
    ],
    "ISLAMABAD": [
        "ISLAMABAD",
    ],
    "ISO": [
        "ISO",
    ],
    "ISTANB": [
        "ISTANB",
    ],
    "ISTANBUL": [
        "ISTANBUL",
    ],
    "IZMIR": [
        "IZMIR",
    ],
    "JAKART": [
        "JAKART",
    ],
    "JAKARTA": [
        "JAKARTA",
    ],
    "JECPA": [
        "JECPA",
    ],
    "JEDDAH": [
        "JEDDAH",
    ],
    "JERUSA": [
        "JERUSA",
    ],
    "JERUSALEM": [
        "JERUSALEM",
        "JERUSALEMO",
    ],
    "JIDDA": [
        "JIDDA",
    ],
    "JOHANN": [
        "JOHANN",
    ],
    "JOHANNESBURG": [
        "JOHANNESBURG",
    ],
    "KABUL": [
        "KABUL",
    ],
    "KADUNA": [
        "KADUNA",
    ],
    "KAMPAL": [
        "KAMPAL",
    ],
    "KAMPALA": [
        "KAMPALA",
    ],
    "KARACH": [
        "KARACH",
    ],
    "KARACHI": [
        "KARACHI",
    ],
    "KATHMA": [
        "KATHMA",
    ],
    "KATHMANDU": [
        "KATHAMNDU",
        "KATHMANDU",
    ],
    "KHARTO": [
        "KHARTO",
        "KHARTOM",
    ],
    "KHARTOUM": [
        "KHARTOUM",
    ],
    "KHORRA": [
        "KHORRA",
    ],
    "KIEV": [
        "KIEV",
    ],
    "KIGALI": [
        "KIGALI",
    ],
    "KINGST": [
        "KINGSON",
        "KINGST",
    ],
    "KINGSTON": [
        "KINGSTON",
    ],
    "KINSHA": [
        "KINSHA",
        "KINSHSA",
    ],
    "KINSHASA": [
        "KINSHAS",
        "KINSHASA",
        "KINSHASAC",
    ],
    "KIRKUK": [
        "KIRKUK",
    ],
    "KISANG": [
        "KISANG",
    ],
    "KOLKATA": [
        "KOLKATA",
    ],
    "KOLONIA": [
        "KOLONIA",
    ],
    "KOROR": [
        "KOROR",
    ],
    "KRAKOW": [
        "KRAKOW",
    ],
    "KUALA": [
        "KUALA",
    ],
    "KUALALUMPUR": [
        "KUALA LUMPUR",
        "KUALALUMPUR",
    ],
    "KUWAIT": [
        "KUWAIT",
    ],
    "KYIV": [
        "KYIV",
    ],
    "KYOTO": [
        "KYOTO",
    ],
    "LAGOS": [
        "LAGOGS",
        "LAGOS",
    ],
    "LAHORE": [
        "LAHORE",
    ],
    "LAPAZ": [
        "LA PAZ",
        "LAPAZ",
    ],
    "LEIPZIG": [
        "LEIPZIG",
    ],
    "LENING": [
        "LENING",
    ],
    "LIBREV": [
        "LIBREV",
    ],
    "LIBREVILLE": [
        "LIBREVILLE",
    ],
    "LILONG": [
        "LILONG",
    ],
    "LILONGWE": [
        "LILONGWE",
    ],
    "LIMA": [
        "LIMA",
    ],
    "LISBON": [
        "LISBO",
        "LISBON",
    ],
    "LIVERP": [
        "LIVERP",
    ],
    "LJUBLJANA": [
        "LJUBLJANA",
    ],
    "LOME": [
        "LOME",
    ],
    "LONDON": [
        "LONDON",
    ],
    "LOSAN": [
        "LOSAN",
    ],
    "LUANDA": [
        "LUANDA",
    ],
    "LUBUMB": [
        "LUBUMB",
    ],
    "LUBUMBASHI": [
        "LUBUMBASHI",
    ],
    "LUSAKA": [
        "LUSAKA",
    ],
    "LUXEMB": [
        "LUXEMB",
    ],
    "LUXEMBOURG": [
        "LUXEMBOURG",
    ],
    "LYON": [
        "LYON",
    ],
    "MADRAS": [
        "MADRAS",
    ],
    "MADRID": [
        "MADRID",
    ],
    "MAJURO": [
        "MAJURO",
    ],
    "MALABO": [
        "MALABO",
    ],
    "MANAGU": [
        "MANAGU",
    ],
    "MANAGUA": [
        "MANAGUA",
    ],
    "MANAMA": [
        "MANAMA",
        "MANANA",
    ],
    "MANILA": [
        "MANILA",
    ],
    "MAPUTO": [
        "LOURENCOMARQUES",
        "MAPUTO",
        "LOUREN",
        "LOURENCO MARQUES",
    ],
    "MARACA": [
        "MARACA",
    ],
    "MARDE": [
        "MARDE",
    ],
    "MARDELPLATA": [
        "MAR DEL PLATA",
        "MARDELPLATA",
    ],
    "MARSEI": [
        "MARSEI",
    ],
    "MARSEILLE": [
        "MARSEILLE",
    ],
    "MARTIN": [
        "MARTIN",
    ],
    "MARTINIQUE": [
        "MARTINIQUE",
    ],
    "MASERU": [
        "MASERU",
    ],
    "MATAMO": [
        "MATAMO",
    ],
    "MATAMOROS": [
        "MATAMOROS",
    ],
    "MAZATL": [
        "MAZATL",
    ],
    "MAZATLAN": [
        "MAZATLAN",
    ],
    "MBABAN": [
        "MBABAN",
    ],
    "MBABANE": [
        "MBABANE",
    ],
    "MBFRV": [
        "MBFRV",
    ],
    "MEDAN": [
        "MEDAN",
    ],
    "MEDELL": [
        "MEDELL",
    ],
    "MEDELLIN": [
        "MEDELLIN",
    ],
    "MELBOU": [
        "MELBOU",
    ],
    "MELBOURNE": [
        "MELBOURNE",
    ],
    "MERIDA": [
        "MERIDA",
    ],
    "MEXICA": [
        "MEXICA",
    ],
    "MEXICO": [
        "MEXICO",
    ],
    "MILAN": [
        "MILAN",
    ],
    "MINSK": [
        "MINSK",
    ],
    "MOGADI": [
        "MOGADI",
    ],
    "MOGADISHU": [
        "MOGADISCIO",
        "MOGADISHU",
    ],
    "MONROV": [
        "MONROV",
    ],
    "MONROVIA": [
        "MONROVIA",
    ],
    "MONTER": [
        "MONTER",
    ],
    "MONTERREY": [
        "MONTERREY",
    ],
    "MONTEV": [
        "MONTEV",
    ],
    "MONTEVIDEO": [
        "MONTEVIDEO",
    ],
    "MONTRE": [
        "MONTRE",
    ],
    "MONTREAL": [
        "MONTREAL",
    ],
    "MOSCOW": [
        "MOSCO",
        "MOSCOE",
        "MOSCOW",
    ],
    "MOSUL": [
        "MOSUL",
    ],
    "MTNGE": [
        "MTNGE",
    ],
    "MUMBAI": [
        "MUMBAI",
    ],
    "MUNICH": [
        "MUNICH",
    ],
    "MUSCAT": [
        "MUSCAOA",
        "MUSCAT",
    ],
    "NAGOYA": [
        "NAGOYA",
    ],
    "NAHA": [
        "NAHA",
    ],
    "NAIROB": [
        "NAIROB",
    ],
    "NAIROBI": [
        "NAIROBI",
    ],
    "NAPLES": [
        "NAPLES",
    ],
    "NASSAU": [
        "NASSAU",
    ],
    "NATO": [
        "NATO",
    ],
    "NATOB": [
        "NATOB",
    ],
    "NATOBRUSSELS": [
        "NATOBRUSSELS",
    ],
    "NDJAENA": [
        "NDJAENA",
    ],
    "NDJAME": [
        "NDJAME",
    ],
    "NDJAMENA": [
        "NDJAMENA",
    ],
    "NEWDE": [
        "NEWDE",
    ],
    "NEWDELHI": [
        "NEW DELHI",
        "NEWDEHLI",
        "NEWDELHI",
    ],
    "NEWFAN": [
        "NEWFAN",
    ],
    "NHATR": [
        "NHATR",
    ],
    "NIAMEY": [
        "NIAMEY",
    ],
    "NICE": [
        "NICE",
    ],
    "NICOSI": [
        "NICOSI",
        "NICOSIS",
    ],
    "NICOSIA": [
        "NICOSIA",
    ],
    "NOGALES": [
        "NOGALES",
    ],
    "NOUAKCHOTT": [
        "NOUACKCHOTT",
        "NOUAKCHOTT",
        "NOUAKC",
        "OUAKC",
    ],
    "NUEVO": [
        "NUEVO",
    ],
    "NUEVOLAREDO": [
        "NUEVOLAREDO",
    ],
    "OECDP": [
        "OECD",
        "OECDP",
    ],
    "OECDPARIS": [
        "OECDPARIS",
    ],
    "OPORTO": [
        "OPORTO",
    ],
    "ORAN": [
        "ORAN",
    ],
    "OSAKA": [
        "OSAKA",
    ],
    "OSAKAKOBE": [
        "OSAKAKOBE",
        "OSAKA KOBE",
    ],
    "OSLO": [
        "OSLO",
    ],
    "OTTAWA": [
        "OTTAWA",
    ],
    "OUAGAD": [
        "OUAGA",
        "OUAGAD",
    ],
    "OUAGADOUGOU": [
        "OUAGADOUGOU",
    ],
    "PALERM": [
        "PALERM",
        "PALERMO",
    ],
    "PALMS": [
        "PALMS",
    ],
    "PANAMA": [
        "PANAMA",
    ],
    "PARAMA": [
        "PARAMA",
    ],
    "PARAMARIBO": [
        "PARAMARIBO",
    ],
    "PARIS": [
        "PARIS",
    ],
    "PARISFR": [
        "PARISFR",
    ],
    "PARTO": [
        "PARTO",
    ],
    "PEKING": [
        "PEKING",
    ],
    "PERTH": [
        "PERTH",
    ],
    "PESHAW": [
        "PESHAW",
    ],
    "PESHAWAR": [
        "PESHAWAR",
    ],
    "PHNOM": [
        "PHNOM",
    ],
    "PHNOMPENH": [
        "PHNOM PENH",
        "PHNOMPENH",
    ],
    "PODGORICA": [
        "PODGORICA",
    ],
    "PONTA": [
        "PONTA",
    ],
    "PONTADELGADA": [
        "PONTA DELGADA",
        "PONTADELGADA",
    ],
    "PORTA": [
        "PORTA",
    ],
    "PORTAUPRINCE": [
        "PORT AU PRINCE",
        "PORTAUPRINCE",
    ],
    "PORTL": [
        "PORTL",
        "PORT LOUIS",
        "PORTLOUIS",
    ],
    "PORTLOUIS": [
        "PORTLOUIS",
    ],
    "PORTM": [
        "PORTM",
    ],
    "PORTMORESBY": [
        "PORT MORESBY",
        "PORTMORESBY",
    ],
    "PORTO": [
        "PORTO",
    ],
    "PORTOFSPAIN": [
        "PORT OF SPAIN",
        "PORTOFSPAIN",
    ],
    "POZNAN": [
        "POZNAN",
    ],
    "PRAGUE": [
        "PRAGUE",
    ],
    "PRAIA": [
        "PRAIA",
    ],
    "PRETOR": [
        "PRETOR",
    ],
    "PRETORIA": [
        "PRETORIA",
    ],
    "PRISTINA": [
        "PRISITNA",
        "PRISTINA",
    ],
    "QUEBEC": [
        "QUEBEC",
    ],
    "QUITO": [
        "QUITO",
    ],
    "RABAT": [
        "RABAT",
    ],
    "RANGOO": [
        "RANGOO",
    ],
    "RANGOON": [
        "RANGON",
        "RANGOON",
    ],
    "RECIFE": [
        "RECIFE",
    ],
    "REFKU": [
        "REFKU",
    ],
    "REFSI": [
        "REFSI",
    ],
    "REYKJA": [
        "REYKJA",
    ],
    "REYKJAVIK": [
        "REYKJAVIK",
    ],
    "RFCPA": [
        "RFCPA",
    ],
    "RIGA": [
        "RIGA",
    ],
    "RIODEJANEIRO": [
        "RIO DE JANEIRO",
        "RIODEJANEIRO",
        "RIODE",
        "IODE",
    ],
    "RIYADH": [
        "RIYADH",
    ],
    "ROME": [
        "ROME",
        "ROMER",
    ],
    "ROTTER": [
        "ROTTER",
    ],
    "ROTTERDAM": [
        "ROTTERDAM",
    ],
    "RPODUBAI": [
        "RPODUBAI",
    ],
    "SAIGON": [
        "SAIGON",
        "AIGON",
    ],
    "SALISB": [
        "SALISB",
    ],
    "SALTT": [
        "SALTT",
        "SALT TALKS",
        "SALTTALKS",
    ],
    "SALVAD": [
        "SALVAD",
    ],
    "SALZBU": [
        "SALZBU",
    ],
    "SANA": [
        "SANA",
    ],
    "SANAA": [
        "SANAA",
    ],
    "SANJO": [
        "SANJO",
    ],
    "SANJOSE": [
        "SAN JOSE",
        "SANJOSE",
    ],
    "SANSA": [
        "SANSA",
    ],
    "SANSALVADOR": [
        "SAN SALVADOR",
        "SANSALVADOR",
    ],
    "SANTIA": [
        "SANTAGO",
        "SANTIA",
        "SANTIGO",
    ],
    "SANTIAGO": [
        "SANTIAGO",
    ],
    "SANTO": [
        "SANTO",
    ],
    "SANTODOMINGO": [
        "SANTO DOMINGO",
        "SANTODOMINGO",
    ],
    "SAOPA": [
        "SAOPA",
    ],
    "SAOPAULO": [
        "SAO PAULO",
        "SAOPAULO",
    ],
    "SAPPOR": [
        "SAPPOR",
    ],
    "SAPPORO": [
        "SAPPORO",
    ],
    "SARAJEVO": [
        "SARAJEVO",
    ],
    "SBERL": [
        "SBERL",
    ],
    "SECDEF": [
        "SECDEF",
    ],
    "SECSTATE": [
        "SECSTATE",
    ],
    "SECTO": [
        "SECTO",
    ],
    "SEOUL": [
        "SEOUL",
    ],
    "SEVILL": [
        "SEVILL",
        "SEVILLE",
    ],
    "SHANGHAI": [
        "SHANGHAI",
    ],
    "SHENYANG": [
        "SHENYANG",
    ],
    "SHIRAZ": [
        "SHIRAZ",
    ],
    "SINAI": [
        "SINAI",
    ],
    "SINGAP": [
        "SINGAP",
    ],
    "SINGAPORE": [
        "SINGAPORE",
    ],
    "SKOPJE": [
        "SKOPJE",
    ],
    "SOFIA": [
        "SOFIA",
    ],
    "STATE": [
        "STATA",
        "STATE",
        "STATES",
        "STATTE",
        "DEPTS",
        "DEPT",
    ],
    "STJOH": [
        "STJOH",
        "STJOHU",
    ],
    "STOCKH": [
        "STOCKH",
    ],
    "STOCKHOLM": [
        "STOCKHOLM",
    ],
    "STPETERSBURG": [
        "LENINGRAD",
        "STPETERSBURG",
    ],
    "STRASB": [
        "STRASB",
    ],
    "STRASBOURG": [
        "STRASBOURG",
    ],
    "STUTTG": [
        "STUTTG",
        "STUTTGART",
    ],
    "SUNN": [
        "SUNN",
    ],
    "SURABA": [
        "SURABA",
    ],
    "SURABAYA": [
        "SURABAYA",
    ],
    "SUVA": [
        "SUVA",
    ],
    "SYDNEY": [
        "SYDNEY",
    ],
    "TABRIZ": [
        "TABRIZ",
    ],
    "TAIF": [
        "TAIF",
    ],
    "TAIPEI": [
        "TAIPEI",
        "TAIPEIH",
    ],
    "TALLINN": [
        "TALLINN",
    ],
    "TANANA": [
        "TANANA",
    ],
    "TANGIE": [
        "TANGIE",
        "TANGIER",
    ],
    "TASHKENT": [
        "TASHKENT",
    ],
    "TBILISI": [
        "TBILISI",
    ],
    "TEGUCI": [
        "TEGUCI",
    ],
    "TEGUCIGALPA": [
        "TEGUCIGALPA",
    ],
    "TEHRAN": [
        "TEHRAN",
        "TEHRN",
    ],
    "TELAV": [
        "TELAV",
    ],
    "TELAVIV": [
        "TEL AVIV",
        "TELAVIV",
    ],
    "THEHA": [
        "THEHA",
    ],
    "THEHAGUE": [
        "HAGUE",
        "THE HAGUE",
        "THEHAGUE",
    ],
    "THESSA": [
        "THESS",
        "THESSA",
    ],
    "THESSALONIKI": [
        "THESSALONIKI",
    ],
    "TIJUAN": [
        "TIJUAN",
    ],
    "TIJUANA": [
        "TIJUANA",
    ],
    "TIRANA": [
        "TIRANA",
    ],
    "TOKYO": [
        "TOKYO",
        "TOKYT",
        "OKYO",
    ],
    "TORONT": [
        "TORONT",
    ],
    "TORONTO": [
        "TORONTO",
    ],
    "TORREM": [
        "TORREM",
    ],
    "TOSEC": [
        "TOSEC",
    ],
    "TRIEST": [
        "TRIEST",
        "TRIESTE",
    ],
    "TRIPOL": [
        "TRIPOL",
        "TRIPOTI",
    ],
    "TRIPOLI": [
        "TRIPOLI",
    ],
    "TUNIS": [
        "TUNIS",
    ],
    "TURIN": [
        "TURIN",
    ],
    "UDORN": [
        "UDORN",
    ],
    "ULAANBAATAR": [
        "ULAANBAAATAR",
        "ULAANBAATAR",
    ],
    "UNESCOPARIS": [
        "UNESCOPARIS",
    ],
    "UNESCOPARISFR": [
        "UNESCOPARISFR",
    ],
    "UNROME": [
        "UNROME",
    ],
    "UNVIE": [
        "UNVIE",
    ],
    "UNVIEVIENNA": [
        "UNVIEVIENNA",
    ],
    "USBER": [
        "USBER",
    ],
    "USBERL": [
        "USBERL",
    ],
    "USBERLIN": [
        "USBERLIN",
    ],
    "USDOC": [
        "USDOC",
    ],
    "USECB": [
        "USECB",
    ],
    "USEUBRUSSELS": [
        "USEUBRUSSELS",
    ],
    "USIA": [
        "USIA",
    ],
    "USNATO": [
        "USNATO",
    ],
    "USOECD": [
        "USOECD",
    ],
    "USOSCE": [
        "USOSCE",
    ],
    "USSCC": [
        "USSCC",
    ],
    "USUNN": [
        "USUN",
        "USUNN",
    ],
    "USUNNEWYORK": [
        "USUN NEW YORK",
        "USUNNEWYORK",
    ],
    "VALLET": [
        "VALLET",
    ],
    "VALLETTA": [
        "VALLETTA",
    ],
    "VANCOU": [
        "VANCOU",
    ],
    "VANCOUVER": [
        "VANCOUVER",
    ],
    "VATICAN": [
        "VATICAN",
    ],
    "VICTOR": [
        "VICTOR",
    ],
    "VICTORIA": [
        "VICTORIA",
    ],
    "VIENNA": [
        "VIENNA",
    ],
    "VIENTI": [
        "VIENTI",
    ],
    "VIENTIANE": [
        "VIENTIANE",
    ],
    "VILNIUS": [
        "VILNIUS",
    ],
    "VIRGIS": [
        "VIRGIS",
    ],
    "VLADIV": [
        "VLADIV",
    ],
    "VLADIVOSTOK": [
        "VLADIVOSTOK",
    ],
    "WARSAW": [
        "WARSAW",
        "WARSZAW",
    ],
    "WASHDC": [
        "WASHDC",
        "WASDC",
        "WASLDC",
    ],
    "WELLINGTON": [
        "WELLINGTON",
        "WELLIN",
        "ELLIN",
    ],
    "WESTI": [
        "WESTI",
    ],
    "WINDHOEK": [
        "WINDHOEK",
    ],
    "WINNIP": [
        "WINNIP",
    ],
    "WINNIPEG": [
        "WINNIPEG",
    ],
    "YAOUND": [
        "YAOUND",
    ],
    "YAOUNDE": [
        "YAOUNDE",
    ],
    "YEKATERINBURG": [
        "YEKATERINBURG",
    ],
    "YEREVAN": [
        "YEREVAN",
    ],
    "ZAGREB": [
        "ZAGREB",
    ],
    "ZANZIB": [
        "ZANZIB",
        "ZANZIBAR",
    ],
    "ZURICH": [
        "ZURICH",
        "ZURIVH",
    ],
    "DIA": [
        "DIA",
    ],
}


def _build_variant_map():
    mapping = {}
    for canonical, variants in STATIONS.items():
        for v in variants:
            if v not in mapping:
                mapping[v] = canonical
    return mapping


def _build_single_stations():
    result = []
    for canonical in STATIONS:
        if " " not in canonical:
            result.append(canonical)
    return sorted(result, key=len, reverse=True)


def _build_multi_stations():
    result = []
    for canonical in STATIONS:
        if " " in canonical:
            result.append(canonical)
    return sorted(result, key=len, reverse=True)


_SINGLE_STATIONS = _build_single_stations()
_MULTI_STATIONS = _build_multi_stations()
_VARIANT_TO_TARGET = _build_variant_map()
STATION_PATTERN = "|".join([re.escape(c) for c in _SINGLE_STATIONS])
