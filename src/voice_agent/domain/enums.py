"""Closed vocabularies: the single source for prompts, validation and SQL values."""

from enum import StrEnum


class BodyType(StrEnum):
    THREE_WHEELER = "three_wheeler"
    MINI_TRUCK = "mini_truck"
    PICKUP = "pickup"
    CARGO_VAN = "cargo_van"
    LCV = "lcv"
    ICV = "icv"
    TIPPER = "tipper"


class Fuel(StrEnum):
    DIESEL = "diesel"
    PETROL = "petrol"
    CNG = "cng"
    ELECTRIC = "electric"


class City(StrEnum):
    MUMBAI = "mumbai"
    DELHI = "delhi"
    BENGALURU = "bengaluru"
    PUNE = "pune"
    HYDERABAD = "hyderabad"
    CHENNAI = "chennai"
    AHMEDABAD = "ahmedabad"
    JAIPUR = "jaipur"
    LUCKNOW = "lucknow"
    KOLKATA = "kolkata"


class Purpose(StrEnum):
    CITY_DELIVERY = "city_delivery"
    LONG_HAUL = "long_haul"
    CONSTRUCTION = "construction"
    AGRICULTURE = "agriculture"


class Intent(StrEnum):
    SEARCH = "search"
    CORRECT = "correct"
    FOLLOW_UP = "follow_up"
    RELAX = "relax"
    RESET = "reset"
    OUT_OF_DOMAIN = "out_of_domain"


class Language(StrEnum):
    EN = "en"
    HINGLISH = "hi-en"


class AliasKind(StrEnum):
    MAKE = "make"
    MODEL = "model"
    BODY_TYPE = "body_type"
    FUEL = "fuel"
    CITY = "city"


class SellerType(StrEnum):
    DEALER = "dealer"
    INDIVIDUAL = "individual"


class FollowUpField(StrEnum):
    PRICE = "price"
    KM = "km"
    PAYLOAD = "payload"
    GVW = "gvw"
    YEAR = "year"
    FUEL = "fuel"
    OWNERS = "owners"
    PAPERS = "papers"
    CITY = "city"
    SELLER = "seller"
    REGISTRATION = "registration"
    SUMMARY = "summary"
    OTHER = "other"
