from lxml import etree, objectify


class NullObjectifiedElement(objectify.ObjectifiedElement):
    def __getattr__(self, tag):
        try:
            return super().__getattr__(tag)
        except AttributeError:
            return NullObjectifiedElement()


def get_ksef_xml_parser():
    parser = etree.XMLParser(
        remove_blank_text=True,
    )
    parser.set_element_class_lookup(
        objectify.ObjectifyElementClassLookup(
            tree_class=NullObjectifiedElement,
            empty_data_class=NullObjectifiedElement,
        )
    )
    return parser


def parse_ksef_xml(xml_data):
    parser = get_ksef_xml_parser()

    if isinstance(xml_data, str):
        xml_data = xml_data.encode()

    return objectify.fromstring(xml_data, parser=parser)
