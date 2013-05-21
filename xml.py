'''
Created on May 17, 2013
@author: Daniel Lee, DWD
'''

import logging
import os
try:
    from lxml import etree
except ImportError:
    import xml.etree.ElementTree as etree


class XML(object):
    """
    An XML file container.

    The XML structure is hidden from the user so that element content can be
    set as if it was a flat field. The hierarchy is stored in the class'
    fields. Missing fields are created when looked up.

    XML is designed as an abstract class. The fields necessary to use it should
    be set in subclasses.

    Fields:
        _namespace: The namespace the XML document should work in
        _root_name: The XML document's root tag
        _unique_tags: Unique tags that can occur in the document
        _unique_tag_attributes: Possible unique attributes that can be placed
                                on tags with the tag that should contain them.
                                Organized thusly:
                                    {attribute_identifier:
                                        (tag, xml_attribute_name)}
        _tag_hierarchy: A tag hierarchy organized as a dictionary. This is used
                        to place tags when they are generated. It is also used
                        to dynamically generate parent elements that may not
                        exist when creating child elements.
                        Organized thusly:
                            {tag_identifier: (parent, xml_tagname)}
                        Note:
                        After describing the field tags, this dictionary is
                        updated to contain the hierarchy of field tags, which
                        are all children of the unique select tag.

    Methods:
        __init__: Either read a given XML file or create a root XML tag and
                  store it internally
        __str__: Use etree's tostring() method to convert the object's internal
                 data into a prettily printed standalone XML file with XML
                 declaration and character encoding
        __repr__: Return initialization string
        __getattr__: Overridden to force interaction with XML tree
        __setattr__: Overridden to force interaction with XML tree
        _get_or_create_tag: Return a tag, creating it if needed.
        export: Export XML query as file
    """

    _namespace = None
    _root_name = None
    _unique_tags = None
    _unique_tag_attributes = None
    _tag_hierarchy = None

    def __init__(self, xml=""):
        """Parse input XML file. If none is provided, make XML structure."""
        if xml:
            self.source_file = xml
            self.tree = etree.parse(self.source_file)
            self.root = self.tree.getroot()
        else:
            self.source_file = ""
            self.root = etree.Element(self._root_name,
                                      nsmap={None: self._namespace})
            self.tree = etree.ElementTree(self.root)
            self.reference_date = ""
        self.ns = "{" + self.root.nsmap[None] + "}"

    def __str__(self):
        """
        The query string has to use single quotation marks in the first line,
        otherwise the parser used in SKY rejects it.
        """
        string = etree.tostring(self.root,
                                xml_declaration=True,
                                encoding="UTF-8",
                                pretty_print=True,
                                standalone=True)
        lines = string.splitlines()
        lines[0] = (lines[0].replace("'", '"'))
        return "\n".join(lines)

    def __repr__(self):
        return 'XML("{}")'.format(self.source_file)

    def __getattr__(self, key):
        """
        Getters are used here in order to ensure that the simple fields exposed
        to the user are synchronized with the internally stored XML elements
        """
        _attribute_error_string = ("{} instance has no attribute "
                              "'{}'".format(self.__class__.__name__, key))

        # If key is in field hierarchy, get it or create it
        if key in self._tag_hierarchy:
            return self._get_or_create_tag(key)

        # If key is attribute, get attribute value
        if key in self._unique_tag_attributes:
            logging.info("Key {} is a unique tag attribute.".format(key))
            tag_name = self._unique_tag_attributes[key][0]
            parent_tag = self._get_or_create_tag(tag_name)
            logging.info("{} is a tag attribute that belongs to tag {}"
                         ".".format(key, parent_tag))
            attribute = parent_tag.get(self._unique_tag_attributes[key][1])
            return attribute

        raise AttributeError(_attribute_error_string)

    def __setattr__(self, name, value):
        """
        Setters are used for the same reason as the getters - to ensure that
        what the user sets is reflected in the object's internal XML elements

        If field is known as a special case, it is assigned using the setter.
        Otherwise it is assigned normally as an object field.

        @param name: Name of attribute to be set
        @type name: String
        @param value: Value to be assigned
        """

        # name is a tag attribute
        if name in self._unique_tag_attributes:
            tag_name = self._unique_tag_attributes[name][0]
            logging.info("{} is an attribute of {} tag.".format(name,
                                                                tag_name))
            tag = self._get_or_create_tag(tag_name)
            tag.set(self._unique_tag_attributes[name][1], value)
        else:
            self.__dict__[name] = value

    def _locate_in_hierarchy(self, tag_name):
        """
        Given a tag, return its parent and the tag's XML name.

        Nonexistent parents are created recursively.

        @param tag_name: The tag's code identifier.
        @return: parent tag, tag's XML name
        @rtype: XML tag, string
        """
        # Does element exist in hierarchy?
        try:
            parent_name = self._tag_hierarchy[tag_name][0]
        except KeyError:
            _attribute_error_string = ("{} instance has no attribute "
                              "'{}'".format(self.__class__.__name__, tag_name))
            raise AttributeError(_attribute_error_string)
        # Does parent exist?
        try:
            logging.info("Looking for {}'s parent.".format(tag_name))
            parent = self.__dict__[parent_name]
        # If not, create and retrieve parent
        except KeyError:
            logging.info("KeyError. Making parent {}.".format(parent_name))
            self.__dict__[parent_name] = self._get_or_create_tag(parent_name)
            parent = self.__dict__[parent_name]
        # Check if element exists
        child_name = self._tag_hierarchy[tag_name][1]
        logging.info("Parent {} exists. {}'s XML name is {}.".
                     format(parent, tag_name, child_name))
        return parent, child_name

    def _get_or_create_tag(self, tag_name):
        """
        Get or create a tag.

        Check if parent exists. If needed, the call method recursively until
        all parent elements are created. The requested element is
        created, if necessary, and then returned.

        @param tag_name: The name of the element
        @param type: String
        """
        parent, child_name = self._locate_in_hierarchy(tag_name)
        elements = parent.getchildren()
        element = None

        # If children are found and element child element is not found field
        if elements and child_name != "field":
            logging.info("{} has children: {}. ".format(parent, elements))
            # Check if I can find the element the easy way
            element = parent.find(child_name)
            if element is not None:
                logging.info("Found tag the easy way. "
                             "It's {}.".format(element))
                return element
            # Otherwise search for it with full namespace
            else:
                element = parent.find("{ns}{element}".
                                      format(ns=self.ns, element=child_name))
                logging.info("Found tag with namespace. "
                             "It's {}.".format(element))
        # If I found the element, return it
        if element is not None:
            logging.info("Found tag. It's {}.".format(element))
            return element

        # Otherwise create it
        element_name = self._tag_hierarchy[tag_name][1]
        logging.info("Creating {} as {}.".format(tag_name, element_name))
        tag = etree.SubElement(parent, child_name)
        # If it's a field element, set its name
        if child_name == "field":
            tag.set("name", self._field_tag_attribute_map[tag_name])
        return tag

    def export(self, path):
        """Writes query to XML file

        @param path: An output path
        """

        if os.path.isfile(path):
            overwrite = ""
            while overwrite != "y" and overwrite != "n":
                prompt = "File already exists. Overwrite? (y/n)\n"
                overwrite = raw_input(prompt)
                overwrite = overwrite.lower()
            if overwrite == "n":
                print("Please enter a new file name.")
                return

        with open(path, "w") as output_file:
            output_file.write(str(self))
