"""Akwa Ibom geography seed data.

Used to seed the `geographies` table and to drive keyword expansion. The 31
LGAs are canonical; the towns list contains the major business hubs that often
appear as keywords in ads (not exhaustive).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class GeoEntry:
    name: str
    kind: str           # "state" | "lga" | "town"
    parent: str | None  # name of parent geography (state for LGA, LGA for town)


AKWA_IBOM_STATE = GeoEntry(name="Akwa Ibom", kind="state", parent=None)

AKWA_IBOM_LGAS: tuple[str, ...] = (
    "Abak",
    "Eastern Obolo",
    "Eket",
    "Esit Eket",
    "Essien Udim",
    "Etim Ekpo",
    "Etinan",
    "Ibeno",
    "Ibesikpo Asutan",
    "Ibiono Ibom",
    "Ika",
    "Ikono",
    "Ikot Abasi",
    "Ikot Ekpene",
    "Ini",
    "Itu",
    "Mbo",
    "Mkpat Enin",
    "Nsit Atai",
    "Nsit Ibom",
    "Nsit Ubium",
    "Obot Akara",
    "Okobo",
    "Onna",
    "Oron",
    "Oruk Anam",
    "Udung Uko",
    "Ukanafun",
    "Uruan",
    "Urue-Offong/Oruko",
    "Uyo",
)

# Major business hubs / markets — many overlap with LGA names which is expected.
AKWA_IBOM_TOWNS: tuple[tuple[str, str], ...] = (
    ("Uyo", "Uyo"),
    ("Eket", "Eket"),
    ("Ikot Ekpene", "Ikot Ekpene"),
    ("Oron", "Oron"),
    ("Abak", "Abak"),
    ("Itu", "Itu"),
)


def all_entries() -> list[GeoEntry]:
    out: list[GeoEntry] = [AKWA_IBOM_STATE]
    for lga in AKWA_IBOM_LGAS:
        out.append(GeoEntry(name=lga, kind="lga", parent=AKWA_IBOM_STATE.name))
    for town, parent_lga in AKWA_IBOM_TOWNS:
        if town in AKWA_IBOM_LGAS:
            continue
        out.append(GeoEntry(name=town, kind="town", parent=parent_lga))
    return out


def default_locations() -> list[str]:
    return list(AKWA_IBOM_LGAS)
