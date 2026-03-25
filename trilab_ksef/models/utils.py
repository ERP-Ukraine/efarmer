try:
    from enum import StrEnum
except ImportError:
    from enum import Enum

    class StrEnum(str, Enum):
        def __str__(self) -> str:
            return str(self.value)


def find_xml_value(xpath, xml_element, namespaces=None):
    element = xml_element.xpath(xpath, namespaces=namespaces)
    return element[0].text if element else None
