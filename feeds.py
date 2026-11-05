"""Sources, categories, routing rules and focus countries for Cyber Watch.

HOW ITEMS GET THEIR CATEGORIES
  1. Every feed has a primary category (the key it sits under in FEEDS).
  2. Keyword rules below can add more categories. For example a CyberScoop story
     about a prompt injection bug is tagged both CYBER and AI SECURITY.
  3. AI SECURITY pulls out security stories from AI feeds, so the AI tab stays
     general AI news.

To add a source, append a dict to a category. Any RSS or Atom URL works.
Optional keys: "official": True (shows an OFFICIAL badge), "limit": N (max items).
Mastodon accounts also expose RSS at https://<instance>/@<user>.rss.
"""

FEEDS = {
    # ---------------------------------------------------------------- CYBER
    "cyber": [
        {"name": "CISA Advisories", "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml", "official": True},
        {"name": "UK NCSC", "url": "https://www.ncsc.gov.uk/api/1/services/v1/all-rss-feed.xml", "official": True},
        {"name": "Krebs on Security", "url": "https://krebsonsecurity.com/feed/"},
        {"name": "BleepingComputer", "url": "https://www.bleepingcomputer.com/feed/"},
        {"name": "The Hacker News", "url": "https://feeds.feedburner.com/TheHackersNews"},
        {"name": "Dark Reading", "url": "https://www.darkreading.com/rss.xml"},
        {"name": "SecurityWeek", "url": "https://feeds.feedburner.com/securityweek"},
        {"name": "The Record", "url": "https://therecord.media/feed"},
        {"name": "CyberScoop", "url": "https://cyberscoop.com/feed/"},
        {"name": "The Register Security", "url": "https://www.theregister.com/security/headlines.atom"},
        {"name": "Ars Technica Security", "url": "https://arstechnica.com/security/feed/"},
        {"name": "Wired Security", "url": "https://www.wired.com/feed/category/security/latest/rss"},
        {"name": "Infosecurity Magazine", "url": "https://www.infosecurity-magazine.com/rss/news/"},
        {"name": "Help Net Security", "url": "https://www.helpnetsecurity.com/feed/"},
        {"name": "Security Affairs", "url": "https://securityaffairs.com/feed"},
        {"name": "Hackread", "url": "https://hackread.com/feed/"},
        {"name": "The Cyber Express", "url": "https://thecyberexpress.com/feed/"},
        {"name": "DataBreaches.net", "url": "https://databreaches.net/feed/"},
        {"name": "Graham Cluley", "url": "https://grahamcluley.com/feed/"},
        {"name": "Sophos News", "url": "https://news.sophos.com/en-us/category/serious-security/feed/"},
        {"name": "Troy Hunt", "url": "https://www.troyhunt.com/rss/"},
        {"name": "Schneier on Security", "url": "https://www.schneier.com/feed/atom/"},
        {"name": "Wiz Blog", "url": "https://www.wiz.io/feed/rss.xml"},
        {"name": "Google Security Blog", "url": "https://security.googleblog.com/feeds/posts/default", "official": True},
    ],

    # ---------------------------------------------------------- AI SECURITY
    # Dedicated AI security sources. More AI security stories are routed in
    # automatically from the CYBER, AI, TECH and COMMUNITY feeds by keyword.
    "aisec": [
        {"name": "Embrace The Red", "url": "https://embracethered.com/blog/index.xml"},
        {"name": "Simon Willison: Prompt Injection", "url": "https://simonwillison.net/tags/prompt-injection.atom"},
        {"name": "Simon Willison: AI Security", "url": "https://simonwillison.net/tags/ai-security-research.atom"},
    ],

    # ------------------------------------------------------------------- AI
    "ai": [
        {"name": "MIT Tech Review AI", "url": "https://www.technologyreview.com/topic/artificial-intelligence/feed"},
        {"name": "VentureBeat AI", "url": "https://venturebeat.com/category/ai/feed/"},
        {"name": "The Verge AI", "url": "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml"},
        {"name": "TechCrunch AI", "url": "https://techcrunch.com/category/artificial-intelligence/feed/"},
        {"name": "Ars Technica AI", "url": "https://arstechnica.com/ai/feed/"},
        {"name": "Wired AI", "url": "https://www.wired.com/feed/tag/ai/latest/rss"},
        {"name": "OpenAI News", "url": "https://openai.com/news/rss.xml", "official": True},
        {"name": "Google AI Blog", "url": "https://blog.google/technology/ai/rss/", "official": True},
        {"name": "Hugging Face Blog", "url": "https://huggingface.co/blog/feed.xml"},
        {"name": "Import AI", "url": "https://importai.substack.com/feed"},
    ],

    # ----------------------------------------------------------------- TECH
    "tech": [
        {"name": "Ars Technica", "url": "https://feeds.arstechnica.com/arstechnica/index"},
        {"name": "Wired", "url": "https://www.wired.com/feed/rss"},
        {"name": "The Verge", "url": "https://www.theverge.com/rss/index.xml"},
        {"name": "TechCrunch", "url": "https://techcrunch.com/feed/"},
        {"name": "Engadget", "url": "https://www.engadget.com/rss.xml"},
        {"name": "ZDNet", "url": "https://www.zdnet.com/news/rss.xml"},
        {"name": "IEEE Spectrum", "url": "https://spectrum.ieee.org/feeds/feed.rss"},
        {"name": "Slashdot", "url": "http://rss.slashdot.org/Slashdot/slashdotMain"},
        {"name": "Hacker News (150+ pts)", "url": "https://hnrss.org/frontpage?points=150"},
    ],

    # -------------------------------------------------------------- FINANCE
    "finance": [
        {"name": "Finextra", "url": "https://www.finextra.com/rss/headlines.aspx"},
        {"name": "Banking Dive", "url": "https://www.bankingdive.com/feeds/news/"},
        {"name": "Payments Dive", "url": "https://www.paymentsdive.com/feeds/news/"},
        {"name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
        {"name": "Cointelegraph", "url": "https://cointelegraph.com/rss"},
        {"name": "Decrypt", "url": "https://decrypt.co/feed"},
        {"name": "Chainalysis Blog", "url": "https://www.chainalysis.com/blog/feed/"},
        {"name": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "official": True},
        {"name": "European Central Bank", "url": "https://www.ecb.europa.eu/rss/press.html", "official": True},
    ],

    # ------------------------------------------- COMMUNITY (CULTURE & SCIENCE)
    # Articles only (no videos, no Reddit or open forums), so random posts
    # cannot slip in. Groups:
    #   Academic research: papers, cryptography, malware analysis, conference research
    #   Bug bounty and hacker community
    #   Hacktivism, state-sponsored campaigns and workforce (also routed in by keyword)
    "community": [
        # Academic research and cryptography
        {"name": "IACR ePrint (Cryptography)", "url": "https://eprint.iacr.org/rss/rss.xml", "limit": 12},
        {"name": "arXiv Cryptography & Security", "url": "http://export.arxiv.org/rss/cs.CR", "limit": 12},
        {"name": "Google Project Zero", "url": "https://googleprojectzero.blogspot.com/feeds/posts/default", "official": True},
        {"name": "PortSwigger Research", "url": "https://portswigger.net/research/rss"},
        {"name": "Trail of Bits", "url": "https://blog.trailofbits.com/feed/"},
        {"name": "Citizen Lab", "url": "https://citizenlab.ca/feed/"},
        # Malware analysis and threat research
        {"name": "Cisco Talos", "url": "https://blog.talosintelligence.com/rss/"},
        {"name": "Unit 42", "url": "https://unit42.paloaltonetworks.com/feed/"},
        {"name": "ESET WeLiveSecurity", "url": "https://www.welivesecurity.com/feed/"},
        {"name": "Check Point Research", "url": "https://research.checkpoint.com/feed/"},
        {"name": "SentinelLabs", "url": "https://www.sentinelone.com/labs/feed/"},
        {"name": "Malwarebytes Labs", "url": "https://www.malwarebytes.com/blog/feed/"},
        {"name": "Google Threat Intelligence", "url": "https://cloudblog.withgoogle.com/topics/threat-intelligence/rss/"},
        {"name": "Microsoft Security Blog", "url": "https://www.microsoft.com/en-us/security/blog/feed/"},
        {"name": "The DFIR Report", "url": "https://thedfirreport.com/feed/"},
        {"name": "Volexity", "url": "https://www.volexity.com/blog/feed/"},
        {"name": "SANS Internet Storm Center", "url": "https://isc.sans.edu/rssfeed.xml"},
        # Bug bounty and hacker community
        {"name": "Intigriti Blog", "url": "https://blog.intigriti.com/feed"},
        {"name": "Detectify Labs", "url": "https://labs.detectify.com/feed/"},
    ],
}

CATEGORY_LABELS = {
    "map": "Global Threat Map",
    "cyber": "Cyber",
    "aisec": "AI Security",
    "ai": "AI",
    "tech": "Tech",
    "finance": "Finance",
    "community": "Community",
}

CATEGORY_DESC = {
    "map": "Click a highlighted country to see its stories across every category.",
    "cyber": "Breaches, vulnerabilities, advisories and incident news.",
    "aisec": "Security of AI: prompt injection, jailbreaks, model and agent attacks, AI-powered threats.",
    "ai": "General AI news and releases.",
    "tech": "Wider technology news.",
    "finance": "Fintech, crypto, banking and financial-sector security.",
    "community": "Culture & Science. Articles on academic research (cryptography, malware analysis, conference research), bug bounty, hacktivism and state-sponsored campaigns, and the security workforce.",
}

# ------------------------------------------------------------ routing rules
# Case-insensitive regex. An item is also tagged with a category when its
# title or summary matches. Edit freely.

AI_TERMS = (
    r"\bAI\b|\bA\.I\.|\bLLMs?\b|large language model|generative AI|\bGenAI\b|agentic|AI agents?|"
    r"machine learning|neural network|chatbot|ChatGPT|OpenAI|Anthropic|\bClaude\b|\bGemini\b|"
    r"Copilot|\bMCP\b|model context protocol|deepfake|foundation model|Hugging ?Face"
)
# Security words that count when the story is already about AI
AISEC_SEC_TERMS = (
    r"vulnerab|exploit|attack|breach|malware|phishing|\bhack|CVE-|zero-day|ransomware|malicious|"
    r"jailbreak|prompt injection|data poisoning|model poisoning|poisoned|adversarial|model extraction|"
    r"model inversion|red team|AI security|LLM security|guardrail|backdoor|AI worm|hijack|"
    r"excessive agency|OWASP|exfiltrat|data leak|supply chain|safety bypass|abuse|misuse|fraud|scam"
)

COMMUNITY_TERMS = (
    r"bug bounty|bounty program|hacktivis|DEF ?CON|Black Hat|BSides|cryptograph|zero-knowledge|"
    r"post-quantum|\bAPT ?\d+|state-sponsored|nation-state|state-backed|malware analysis|"
    r"reverse engineering|\bCTF\b|capture the flag|academic|peer-reviewed|workforce|skills gap|"
    r"talent shortage|cybersecurity jobs|security careers|hacker group|threat actor group"
)

# Applied to COMMUNITY research feeds so threat research also shows up under CYBER
CYBER_TERMS = (
    r"malware|ransomware|vulnerab|exploit|threat actor|\bAPT ?\d*|breach|zero-day|CVE-|botnet|"
    r"phishing|backdoor|espionage|campaign|infostealer|stealer"
)

FINANCE_TERMS = (
    r"\bbank(?:s|ing)?\b|crypto|bitcoin|ethereum|\bDeFi\b|fintech|payment fraud|\bSWIFT\b|\bATM\b|"
    r"crypto wallet|stablecoin|financial sector|financial institution|stock exchange|credit card"
)

# ------------------------------------------------------------ severity rules
# Each rule is (badge label, level, regex). Level "urgent" shows a red stripe, "high" an amber one.
# A story gets the strongest level any rule gives it, plus up to two badges. These are keyword
# heuristics on the headline and summary, so a badge means "the text says so", not "verified".
SEVERITY_RULES = [
    ("Actively exploited", "urgent",
     r"actively exploited|exploited in the wild|known exploited vulnerabilit|\bKEV\b|under active attack|"
     r"being exploited|active exploitation|exploitation attempts"),
    ("Zero-day", "urgent", r"zero-?day|\b0-day\b"),
    ("Critical flaw", "high",
     r"critical (?:vulnerabilit|flaw|bug|security|severity|rce)|CVSS (?:score )?(?:of )?(?:9|10)|"
     r"remote code execution|\bRCE\b|unauthenticated|wormable|emergency (?:patch|directive|update)"),
    ("Ransomware", "high", r"ransomware"),
    ("Data breach", "high",
     r"data breach|breach(?:ed)? .{0,40}(?:data|records|customers|accounts)|data leak|exposed .{0,20}(?:data|records)"),
]
CVE_PATTERN = r"CVE-\d{4}-\d{4,7}"

# --------------------------------------------------------- focus countries
# iso = numeric ISO 3166 code used by the map data. Keywords are matched as whole
# words, case-insensitive. Threat-actor names are included so attribution stories
# land on the right country. Add more countries here, they appear on the map
# automatically.
COUNTRIES = {
    "China": {
        "iso": "156", "flag": "cn", "lat": 35.9, "lon": 104.2,
        "keywords": ["china", "chinese", "beijing", "prc", "volt typhoon", "salt typhoon", "apt41",
                     "apt31", "apt40", "apt10", "mustang panda", "huawei", "hong kong"],
    },
    "Russia": {
        "iso": "643", "flag": "ru", "lat": 61.5, "lon": 80.0,
        "keywords": ["russia", "russian", "moscow", "kremlin", "apt28", "apt29", "fancy bear",
                     "cozy bear", "sandworm", "midnight blizzard", "turla", "killnet", "gru", "fsb"],
    },
    "North Korea": {
        "iso": "408", "flag": "kp", "lat": 40.3, "lon": 127.5,
        "keywords": ["north korea", "north korean", "dprk", "pyongyang", "lazarus", "kimsuky",
                     "andariel", "apt38", "bluenoroff"],
    },
    "Iran": {
        "iso": "364", "flag": "ir", "lat": 32.4, "lon": 53.7,
        "keywords": ["iran", "iranian", "tehran", "apt33", "apt34", "apt35", "charming kitten",
                     "muddywater", "oilrig", "cyberav3ngers"],
    },
    "United States": {
        "iso": "840", "flag": "us", "lat": 39.8, "lon": -98.6,
        "keywords": ["united states", "u.s.", "usa", "american", "americans", "fbi", "nsa", "cisa",
                     "pentagon", "white house", "doj", "department of justice", "treasury", "ofac",
                     "dhs", "congress", "us-based"],
    },
    "United Kingdom": {
        "iso": "826", "flag": "gb", "lat": 54.0, "lon": -2.0,
        "keywords": ["united kingdom", "uk", "u.k.", "british", "britain", "england", "london",
                     "ncsc", "gchq", "scotland", "wales", "nhs"],
    },
    "Germany": {
        "iso": "276", "flag": "de", "lat": 51.2, "lon": 10.4,
        "keywords": ["germany", "german", "germans", "berlin", "bsi", "bundestag"],
    },
    "France": {
        "iso": "250", "flag": "fr", "lat": 46.6, "lon": 2.2,
        "keywords": ["france", "french", "paris", "anssi"],
    },
    "Israel": {
        "iso": "376", "flag": "il", "lat": 31.0, "lon": 34.9,
        "keywords": ["israel", "israeli", "tel aviv", "jerusalem", "nso group", "unit 8200"],
    },
    "Japan": {
        "iso": "392", "flag": "jp", "lat": 36.2, "lon": 138.3,
        "keywords": ["japan", "japanese", "tokyo", "nippon"],
    },
    "South Korea": {
        "iso": "410", "flag": "kr", "lat": 36.5, "lon": 127.8,
        "keywords": ["south korea", "south korean", "seoul"],
    },
    "Australia": {
        "iso": "036", "flag": "au", "lat": -25.3, "lon": 133.8,
        "keywords": ["australia", "australian", "australians", "sydney", "melbourne", "canberra", "acsc"],
    },
    "Brazil": {
        "iso": "076", "flag": "br", "lat": -10.8, "lon": -52.9,
        "keywords": ["brazil", "brazilian", "brasil", "sao paulo", "brasilia"],
    },
    "India": {
        "iso": "356", "flag": "in", "lat": 22.6, "lon": 79.0,
        "keywords": ["india", "indian", "indians", "delhi", "mumbai", "bengaluru", "bangalore", "cert-in"],
    },
}
