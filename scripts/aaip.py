"""Shared helpers: stream classification and occupation (sector) tagging for AAIP draws."""
import re

SOURCE_URL = "https://www.alberta.ca/aaip-processing-information"

# slug -> (display name, short name, description)
STREAMS = {
    "alberta-opportunity-stream": ("Alberta Opportunity Stream", "AOS",
        "Alberta's main worker stream for people already working in Alberta on an eligible work permit."),
    "dedicated-health-care-pathway": ("Dedicated Health Care Pathways", "DHCP",
        "Express Entry and non-Express Entry pathways for regulated health professionals with an Alberta job offer."),
    "alberta-express-entry-stream": ("Alberta Express Entry Stream", "AAES",
        "Draws from the federal Express Entry pool: Accelerated Tech, Law Enforcement and Priority Sector draws."),
    "rural-renewal-stream": ("Rural Renewal Stream", "RRS",
        "For workers with a job offer in a designated rural Alberta community and an endorsement from that community."),
    "tourism-and-hospitality-stream": ("Tourism and Hospitality Stream", "THS",
        "For workers in eligible tourism and hospitality occupations with an Alberta employer."),
    "other": ("Other draws", "Other", "Draws that don't map to a single named stream."),
}

SECTORS = {
    "health-care": "Health & care workers",
    "tech": "Tech",
    "construction": "Construction & skilled trades",
    "manufacturing": "Manufacturing",
    "agriculture": "Agriculture",
    "aviation": "Aviation",
    "law-enforcement": "Law enforcement",
    "tourism-hospitality": "Tourism & hospitality",
    "rural": "Rural communities",
    "general": "General / all occupations",
}


def slugify(s):
    s = s.lower().replace("–", "-").replace("—", "-")
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return s.strip("-")


def classify(raw):
    """Map the official 'stream / pathway' text to stream, pathway, sector and a checker category."""
    t = " ".join(raw.replace("—", "–").split())
    low = t.lower()
    paren = re.search(r"\(([^)]*)\)", t)
    paren_txt = paren.group(1) if paren else ""
    stream, pathway, sector = "other", "", "general"

    if "dedicated health care" in low:
        stream = "dedicated-health-care-pathway"
        pathway = "Non-Express Entry" if "non-express" in low else "Express Entry"
        sector = "health-care"
    elif "express entry stream" in low:
        stream = "alberta-express-entry-stream"
        if "accelerated tech" in low:
            pathway, sector = "Accelerated Tech Pathway", "tech"
        elif "law enforcement" in low:
            pathway, sector = "Law Enforcement Pathway", "law-enforcement"
        elif "priority sector" in low:
            pathway = "Priority Sectors"
            sector = sector_from_text(paren_txt or t)
        else:
            pathway = t.split("–", 1)[1].strip() if "–" in t else ""
            sector = sector_from_text(t)
    elif "opportunity stream" in low:
        stream = "alberta-opportunity-stream"
        rest = t.split("–", 1)[1].strip() if "–" in t else ""
        pathway = rest
        sector = sector_from_text(rest) if rest else "general"
    elif "rural renewal" in low:
        stream, sector = "rural-renewal-stream", "rural"
    elif "tourism and hospitality" in low:
        stream, sector = "tourism-and-hospitality-stream", "tourism-hospitality"
    else:
        sector = sector_from_text(t)

    # Category used by the score checker: stream + pathway (+ sector for priority sector draws)
    if stream == "alberta-express-entry-stream" and pathway == "Priority Sectors":
        category = f"aaes-priority-{sector}"
        cat_label = f"Alberta Express Entry – Priority Sectors ({SECTORS.get(sector, sector)})"
    elif stream == "alberta-express-entry-stream":
        category = "aaes-" + slugify(pathway or "other")
        cat_label = f"Alberta Express Entry – {pathway}"
    elif stream == "dedicated-health-care-pathway":
        category = "dhcp-" + slugify(pathway)
        cat_label = f"Dedicated Health Care Pathway – {pathway}"
    elif stream == "alberta-opportunity-stream":
        category = "aos" if sector == "general" else f"aos-{sector}"
        cat_label = "Alberta Opportunity Stream" + ("" if sector == "general" else f" – {SECTORS.get(sector, sector)}")
    else:
        category = stream
        cat_label = STREAMS[stream][0]
    return {"stream": stream, "stream_name": STREAMS[stream][0], "pathway": pathway,
            "sector": sector, "sector_name": SECTORS.get(sector, sector),
            "category": category, "category_label": cat_label}


def sector_from_text(t):
    low = t.lower()
    if "health" in low:
        return "health-care"
    if "construction" in low:
        return "construction"
    if "manufactur" in low:
        return "manufacturing"
    if "agricultur" in low:
        return "agriculture"
    if "aviation" in low:
        return "aviation"
    if "tech" in low:
        return "tech"
    if "law enforcement" in low:
        return "law-enforcement"
    if "tourism" in low or "hospitality" in low:
        return "tourism-hospitality"
    if "skilled trade" in low:
        return "construction"
    return "general"
