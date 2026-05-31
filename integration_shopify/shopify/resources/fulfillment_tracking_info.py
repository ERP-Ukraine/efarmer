# See LICENSE file for full copyright and licensing details.
#
# Supported tracking companies from Shopify FulfillmentTrackingInfo:
# https://shopify.dev/docs/api/admin-graphql/latest/objects/FulfillmentTrackingInfo

SHOPIFY_TRACKING_COMPANY_OTHER = 'other'

# Companies available for any country.
SHOPIFY_TRACKING_COMPANIES_GLOBAL = [
    '4PX',
    'AGS',
    'Amazon',
    'Amazon Logistics UK',
    'An Post',
    'Anjun Logistics',
    'APC',
    'Asendia USA',
    'Australia Post',
    'Bonshaw',
    'BPost',
    'BPost International',
    'Canada Post',
    'Canpar',
    'CDL Last Mile',
    'China Post',
    'Chronopost',
    'Chukou1',
    'Colissimo',
    'Comingle',
    'Coordinadora',
    'Correios',
    'Correos',
    'CTT',
    'CTT Express',
    'Cyprus Post',
    'Delnext',
    'Deutsche Post',
    'DHL eCommerce',
    'DHL eCommerce Asia',
    'DHL Express',
    'DPD',
    'DPD Local',
    'DPD UK',
    'DTD Express',
    'DX',
    'Eagle',
    'Estes',
    'Evri',
    'FedEx',
    'First Global Logistics',
    'First Line',
    'FSC',
    'Fulfilla',
    'GLS',
    'Guangdong Weisuyi Information Technology (WSE)',
    'Heppner Internationale Spedition GmbH & Co.',
    'Iceland Post',
    'IDEX',
    'Israel Post',
    'Japan Post (EN)',
    'Japan Post (JA)',
    'La Poste Colissimo',
    'La Poste Burkina Faso',
    'Lasership',
    'Latvia Post',
    'Lietuvos Paštas',
    'Logisters',
    'Lone Star Overnight',
    'M3 Logistics',
    'Meteor Space',
    'Mondial Relay',
    'New Zealand Post',
    'NinjaVan',
    'North Russia Supply Chain (Shenzhen) Co.',
    'OnTrac',
    'Packeta',
    'Pago Logistics',
    'Ping An Da Tengfei Express',
    'Pitney Bowes',
    'Portal PostNord',
    'Poste Italiane',
    'PostNL',
    'PostNord DK',
    'PostNord NO',
    'PostNord SE',
    'Purolator',
    'Qxpress',
    'Qyun Express',
    'Royal Mail',
    'Royal Shipments',
    'Sagawa (EN)',
    'Sagawa (JA)',
    'Sendle',
    'SF Express',
    'SFC Fulfillment',
    'SHREE NANDAN COURIER',
    'Singapore Post',
    'Southwest Air Cargo',
    'StarTrack',
    'Step Forward Freight',
    'Swiss Post',
    'TForce Final Mile',
    'Tinghao',
    'TNT',
    'Toll IPEC',
    'United Delivery Service',
    'UPS',
    'USPS',
    'Venipak',
    'We Post',
    'Whistl',
    'Wizmo',
    'WMYC',
    'Xpedigo',
    'XPO Logistics',
    'Yamato (EN)',
    'Yamato (JA)',
    'YiFan Express',
    'YunExpress',
]

# Additional companies for specific countries (merged with the global list).
SHOPIFY_TRACKING_COMPANIES_BY_COUNTRY = [
    # Australia
    'Aramex Australia',
    'TNT Australia',
    'Hunter Express',
    'Couriers Please',
    'Bonds',
    'Allied Express',
    'Direct Couriers',
    'Northline',
    'GO Logistics',
    # Austria
    'Österreichische Post',
    # Bulgaria
    'Speedy',
    # Canada
    'Intelcom',
    'BoxKnight',
    'Loomis',
    # China
    'WanbExpress',
    # Czechia
    'Zásilkovna',
    # Germany
    'Deutsche Post (DE)',
    'Deutsche Post (EN)',
    'DHL',
    'Swiship',
    'Hermes',
    # Spain
    'SEUR',
    # France
    'Colis Privé',
    # United Kingdom
    'Parcelforce',
    'Yodel',
    'DHL Parcel',
    'Tuffnells',
    # Greece
    'ACS Courier',
    # Ireland
    'Fastway',
    'DPD Ireland',
    # India
    'DTDC',
    'India Post',
    'Delhivery',
    'Gati KWE',
    'Professional Couriers',
    'XpressBees',
    'Ecom Express',
    'Ekart',
    'Shadowfax',
    'Bluedart',
    # Italy
    'BRT',
    'GLS Italy',
    # Japan
    'エコ配',
    '西濃運輸',
    '西濃スーパーエキスプレス',
    '福山通運',
    '日本通運',
    '名鉄運輸',
    '第一貨物',
    # Norway
    'Bring',
    # Poland
    'Inpost',
    # Turkey
    'PTT',
    'Yurtiçi Kargo',
    'Aras Kargo',
    'Sürat Kargo',
    # United States
    'Alliance Air Freight',
    'Pilot Freight',
    'LSO',
    'Old Dominion',
    'Pandion',
    'R+L Carriers',
    # South Africa
    'Skynet',
]


def _build_tracking_companies():
    seen = set()
    companies = []
    for name in SHOPIFY_TRACKING_COMPANIES_GLOBAL + SHOPIFY_TRACKING_COMPANIES_BY_COUNTRY:
        if name not in seen:
            seen.add(name)
            companies.append(name)
    return tuple(companies)


SHOPIFY_TRACKING_COMPANIES = _build_tracking_companies()

SHOPIFY_TRACKING_COMPANY_SELECTION = (
    [(company, company) for company in SHOPIFY_TRACKING_COMPANIES] +
    [(SHOPIFY_TRACKING_COMPANY_OTHER, 'Other')]
)

SHOPIFY_TRACKING_COMPANY_BY_LOWER = {
    company.lower(): company for company in SHOPIFY_TRACKING_COMPANIES
}


def normalize_shopify_tracking_company(value: str):
    """Map a free-text value to a supported selection key or ``other``."""
    if not value or not isinstance(value, str):
        return ''

    value = value.strip()
    if value not in SHOPIFY_TRACKING_COMPANIES:
        return SHOPIFY_TRACKING_COMPANY_OTHER

    if value in SHOPIFY_TRACKING_COMPANIES:
        return value

    return SHOPIFY_TRACKING_COMPANY_BY_LOWER.get(value.lower(), SHOPIFY_TRACKING_COMPANY_OTHER)
